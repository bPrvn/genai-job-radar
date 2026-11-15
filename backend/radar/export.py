"""Builds the dashboard payload. The same shape is served live by the API and written
to frontend/public/data/snapshot.json for the GitHub Pages build."""

import json

from . import config
from .db import STATUSES, connect, now_iso, row_to_dict


def build(personal: bool = True) -> dict:
    with connect() as conn:
        jobs = []
        for r in conn.execute(
                """SELECT id, company, source, title, location, url, posted_at, substr(description, 1, 700) AS excerpt,
                          min_years, fit_score, keywords, first_seen, last_seen, active, status, notes
                   FROM jobs WHERE active=1 OR status NOT IN ('New', 'Not a fit')
                   ORDER BY first_seen DESC, fit_score DESC"""):
            d = row_to_dict(r)
            d["tier"] = config.TIERS.get(d["company"], "Web lead" if d["source"] == "web" else "Other")
            if not personal:
                d.pop("status"); d.pop("notes")
            jobs.append(d)

        days = [r[0] for r in conn.execute("SELECT DISTINCT day FROM keyword_snapshots ORDER BY day")]
        latest = days[-1] if days else None
        kw_latest = [dict(r) for r in conn.execute(
            "SELECT keyword, count, share FROM keyword_snapshots WHERE day=? ORDER BY count DESC", (latest,))]
        top = [k["keyword"] for k in kw_latest[:6]]
        kw_history = [dict(r) for r in conn.execute(
            f"SELECT day, keyword, share FROM keyword_snapshots WHERE keyword IN ({','.join('?' * len(top)) or 'NULL'}) ORDER BY day",
            top)]

        q_cols = "id, text, round, company, source, source_url, first_seen" + (", practiced" if personal else "")
        questions = [dict(r) for r in conn.execute(f"SELECT {q_cols} FROM questions ORDER BY first_seen DESC, id DESC")]
        reading = [dict(r) for r in conn.execute(
            "SELECT url, title, source, published, first_seen FROM articles WHERE use='blog' "
            "ORDER BY COALESCE(published, first_seen) DESC LIMIT 40")]
        summaries = [dict(r) for r in conn.execute("SELECT day, markdown, model FROM summaries ORDER BY day DESC LIMIT 14")]
        runs = []
        for r in conn.execute("SELECT * FROM runs WHERE finished_at IS NOT NULL ORDER BY id DESC LIMIT 14"):
            d = dict(r)
            d["errors"] = json.loads(d["errors"] or "[]")
            runs.append(d)
        jobs_by_day = [dict(r) for r in conn.execute(
            "SELECT substr(first_seen, 1, 10) AS day, COUNT(*) AS n FROM jobs GROUP BY day ORDER BY day")]

    return {
        "generated_at": now_iso(), "personal": personal, "statuses": STATUSES,
        "jobs": jobs, "keywords": kw_latest, "keyword_history": kw_history, "jobs_by_day": jobs_by_day,
        "questions": questions, "reading": reading, "summaries": summaries, "runs": runs,
    }


def write_snapshot() -> str:
    data = build(personal=config.PUBLISH_PERSONAL_FIELDS)
    config.SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.SNAPSHOT_PATH.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    return str(config.SNAPSHOT_PATH)
