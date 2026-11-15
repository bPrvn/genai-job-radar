"""SQLite storage. One file at data/radar.db, created on first use."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id            TEXT PRIMARY KEY,          -- source:company:external id
    company       TEXT NOT NULL,
    source        TEXT NOT NULL DEFAULT 'api', -- "api" (careers site) | "web" (search lead, unverified)
    title         TEXT NOT NULL,
    location      TEXT,
    url           TEXT,
    posted_at     TEXT,                      -- ISO date, when the source gives one
    description   TEXT,
    min_years     INTEGER,
    fit_score     INTEGER,
    keywords      TEXT,                      -- JSON list of keyword labels
    first_seen    TEXT NOT NULL,
    last_seen     TEXT NOT NULL,
    active        INTEGER NOT NULL DEFAULT 1,
    status        TEXT NOT NULL DEFAULT 'New',
    notes         TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS jobs_active ON jobs(active, first_seen);

CREATE TABLE IF NOT EXISTS questions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    text        TEXT NOT NULL UNIQUE,
    round       TEXT NOT NULL,
    company     TEXT,
    source      TEXT,
    source_url  TEXT,
    first_seen  TEXT NOT NULL,
    practiced   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS keyword_snapshots (
    day      TEXT NOT NULL,
    keyword  TEXT NOT NULL,
    count    INTEGER NOT NULL,
    share    REAL NOT NULL,                  -- fraction of active jobs mentioning it
    PRIMARY KEY (day, keyword)
);

CREATE TABLE IF NOT EXISTS articles (
    url         TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    source      TEXT,
    published   TEXT,
    use         TEXT NOT NULL,               -- "questions" (mined) | "blog" (reading list)
    first_seen  TEXT NOT NULL,
    questions   INTEGER NOT NULL DEFAULT 0   -- how many questions it yielded
);

CREATE TABLE IF NOT EXISTS summaries (
    day         TEXT PRIMARY KEY,
    markdown    TEXT NOT NULL,
    model       TEXT                         -- NIM model id, or "template" without a key
);

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    new_jobs    INTEGER DEFAULT 0,
    seen_jobs   INTEGER DEFAULT 0,
    new_questions INTEGER DEFAULT 0,
    errors      TEXT DEFAULT '[]'            -- JSON list of "source: message"
);
"""

STATUSES = ["New", "Shortlisted", "Referral asked", "Applied", "Interviewing", "Offer", "Rejected", "Not a fit"]
ROUNDS = ["Coding (DSA)", "GenAI depth", "LLM system design", "Evaluation", "Backend", "Behavioural", "General"]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


@contextmanager
def connect(path=None):
    path = path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row) -> dict:
    d = dict(row)
    if "keywords" in d and isinstance(d["keywords"], str):
        d["keywords"] = json.loads(d["keywords"] or "[]")
    return d
