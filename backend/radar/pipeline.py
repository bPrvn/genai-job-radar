"""The daily run: jobs -> web leads -> research -> keyword snapshot -> summary."""

from __future__ import annotations

import json
import logging
import re
import time

from . import config, llm, research, scoring
from .db import ROUNDS, connect, now_iso, today
from .sources import ADAPTERS, client

log = logging.getLogger("radar")

SEED_QUESTIONS = [
    ("Coding (DSA)", "Implement an LRU cache with O(1) get and put."),
    ("Coding (DSA)", "Return the top-K frequent elements of an array."),
    ("Coding (DSA)", "Write a text chunker that splits a document into overlapping token windows."),
    ("Coding (DSA)", "Given query and document embeddings, return the top-k documents by cosine similarity efficiently."),
    ("GenAI depth", "When would you choose RAG over fine-tuning, and when prompting alone?"),
    ("GenAI depth", "Compare fixed-size, recursive and semantic chunking. How does chunk size affect retrieval recall?"),
    ("GenAI depth", "How does hybrid search (BM25 + dense vectors) work, and how do you fuse and re-rank the results?"),
    ("GenAI depth", "What techniques reduce hallucinations in a production LLM application?"),
    ("GenAI depth", "Explain LoRA and QLoRA. Why do they make fine-tuning cheaper?"),
    ("GenAI depth", "What is the KV-cache and how does it speed up autoregressive generation?"),
    ("GenAI depth", "Why is self-attention O(n^2) in sequence length, and what are the common workarounds?"),
    ("LLM system design", "Design an enterprise knowledge assistant over 10M documents with per-user access control."),
    ("LLM system design", "Design a multilingual RAG support chatbot with p95 latency under 2 seconds."),
    ("LLM system design", "Design an agent that calls internal APIs safely: planning, retries, guardrails and audit."),
    ("LLM system design", "How would you cut LLM serving cost 5x without hurting quality?"),
    ("Evaluation", "How do you evaluate a RAG pipeline end to end (retrieval recall@k, MRR, faithfulness, answer relevance)?"),
    ("Evaluation", "What are the biases of LLM-as-judge and how do you calibrate it?"),
    ("Evaluation", "How do you regression-test prompts and models in CI before a release?"),
    ("Backend", "Design a streaming LLM API (SSE or websockets) that handles 1,000 requests per second."),
    ("Backend", "How do you add caching, rate limiting and idempotency to an LLM gateway?"),
    ("Behavioural", "Why Apple, and why now?"),
    ("Behavioural", "Tell me about a production incident you owned end to end."),
    ("Behavioural", "Tell me about a time you disagreed with an architecture decision."),
]


def _seed(conn):
    if conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]:
        return
    ts = now_iso()
    conn.executemany(
        "INSERT OR IGNORE INTO questions(text, round, company, source, source_url, first_seen) VALUES (?,?,?,?,?,?)",
        [(q, r, None, "Curated", "", ts) for r, q in SEED_QUESTIONS])


# ---------------------------------------------------------------- jobs
def collect_jobs(conn, errors: list[str]) -> tuple[int, int]:
    ts, new, seen = now_iso(), 0, 0
    with client() as c:
        for src in config.SOURCES:
            company = src["company"]
            try:
                listings = ADAPTERS[src["kind"]](c, src)
            except Exception as ex:
                errors.append(f"{company}: {type(ex).__name__}: {str(ex)[:160]}")
                log.warning("source %s failed: %s", company, ex)
                continue
            seen_ids = []
            for l in listings:
                if not (scoring.title_relevant(l.title) and scoring.location_ok(l.location)):
                    continue
                jid = f"{src['kind']}:{company}:{l.ext_id}"
                seen_ids.append(jid)
                if conn.execute("SELECT 1 FROM jobs WHERE id=?", (jid,)).fetchone():
                    conn.execute("UPDATE jobs SET last_seen=?, active=1 WHERE id=?", (ts, jid))
                    continue
                desc = l.description or ""
                if not desc and l.detail:
                    try:
                        desc = l.detail()
                        time.sleep(0.3)  # be gentle with careers sites
                    except Exception as ex:
                        errors.append(f"{company} detail: {str(ex)[:100]}")
                years = scoring.min_years(desc)
                conn.execute(
                    """INSERT INTO jobs(id, company, source, title, location, url, posted_at, description,
                                        min_years, fit_score, keywords, first_seen, last_seen)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (jid, company, "api", l.title, l.location, l.url, l.posted_at, desc, years,
                     scoring.fit_score(l.title, l.location, desc, years),
                     json.dumps(scoring.keywords(l.title + "\n" + desc)), ts, ts))
                new += 1
            seen += len(seen_ids)
            # Roles from a source that answered but no longer lists them are closed.
            conn.execute(
                f"UPDATE jobs SET active=0 WHERE company=? AND source='api' AND id NOT IN ({','.join('?' * len(seen_ids)) or 'NULL'})",
                (company, *seen_ids))
            log.info("%-12s %3d listings, %3d relevant", company, len(listings), len(seen_ids))
    return new, seen


def collect_web_leads(conn, errors: list[str]) -> int:
    ts, new = now_iso(), 0
    known = {r[0] for r in conn.execute("SELECT url FROM jobs")}
    # (lead, source tag, whether an India/remote location is required)
    batches = [(research.web_job_leads(errors), "web", True),
               (research.rss_job_leads(errors), "rss", config.JOB_RSS_REQUIRE_INDIA)]
    for leads, src, require_india in batches:
        for lead in leads:
            india = scoring.location_ok(f"{lead['title']} {lead['snippet']} {lead['url']}")
            listing_page = re.search(config.WEB_LEAD_EXCLUDE, lead["title"], re.I)
            if (lead["url"] in known or listing_page or not scoring.title_relevant(lead["title"])
                    or (require_india and not india)):
                continue
            known.add(lead["url"])
            years = scoring.min_years(lead["snippet"])
            conn.execute(
                """INSERT OR IGNORE INTO jobs(id, company, source, title, location, url, description, min_years,
                                              fit_score, keywords, first_seen, last_seen)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (f"{src}:{lead['company']}:{lead['ext_id']}", lead["company"], src, lead["title"][:200], "",
                 lead["url"], lead["snippet"], years,
                 scoring.fit_score(lead["title"], lead["snippet"], lead["snippet"], years) - 10,  # unverified
                 json.dumps(scoring.keywords(lead["title"] + " " + lead["snippet"])), ts, ts))
            new += 1
    return new


# ---------------------------------------------------------------- research
def collect_research(conn, errors: list[str]) -> tuple[int, int]:
    known = {r[0] for r in conn.execute("SELECT url FROM articles")}
    articles, questions = research.collect(known, errors)
    ts = now_iso()
    per_url: dict[str, int] = {}
    new_q = 0
    for q in research.dedupe(questions):
        cur = conn.execute(
            "INSERT OR IGNORE INTO questions(text, round, company, source, source_url, first_seen) VALUES (?,?,?,?,?,?)",
            (q.text, q.round if q.round in ROUNDS else research.classify(q.text),
             q.company, q.source, q.source_url, ts))
        if cur.rowcount:
            new_q += 1
            per_url[q.source_url] = per_url.get(q.source_url, 0) + 1
    for a in articles:
        conn.execute(
            "INSERT OR IGNORE INTO articles(url, title, source, published, use, first_seen, questions) VALUES (?,?,?,?,?,?,?)",
            (a.url, a.title[:300], a.source, a.published, a.use, ts, per_url.get(a.url, 0)))
    return new_q, sum(1 for a in articles if a.use == "blog")


# ---------------------------------------------------------------- keywords
def snapshot_keywords(conn):
    rows = conn.execute("SELECT keywords FROM jobs WHERE active=1 AND source='api'").fetchall()
    total = len(rows) or 1
    counts: dict[str, int] = {}
    for (kw,) in rows:
        for k in json.loads(kw or "[]"):
            counts[k] = counts.get(k, 0) + 1
    day = today()
    conn.execute("DELETE FROM keyword_snapshots WHERE day=?", (day,))
    conn.executemany("INSERT INTO keyword_snapshots(day, keyword, count, share) VALUES (?,?,?,?)",
                     [(day, k, v, round(v / total, 4)) for k, v in counts.items()])


# ---------------------------------------------------------------- summary
def _facts(conn, run_started: str) -> dict:
    new_jobs = [dict(r) for r in conn.execute(
        """SELECT company, title, location, url, fit_score, min_years, source FROM jobs
           WHERE first_seen >= ? ORDER BY fit_score DESC LIMIT 12""", (run_started,))]
    days = [r[0] for r in conn.execute("SELECT DISTINCT day FROM keyword_snapshots ORDER BY day DESC LIMIT 8")]
    cur = {r[0]: r[1] for r in conn.execute("SELECT keyword, share FROM keyword_snapshots WHERE day=?", (days[0],))} if days else {}
    old = {r[0]: r[1] for r in conn.execute("SELECT keyword, share FROM keyword_snapshots WHERE day=?", (days[-1],))} if len(days) > 1 else {}
    top_kw = sorted(cur.items(), key=lambda kv: -kv[1])[:10]
    return {
        "date": today(),
        "active_roles": conn.execute("SELECT COUNT(*) FROM jobs WHERE active=1").fetchone()[0],
        "new_roles_count": conn.execute("SELECT COUNT(*) FROM jobs WHERE first_seen >= ?", (run_started,)).fetchone()[0],
        "new_roles": new_jobs,
        "top_keywords": [{"keyword": k, "share_pct": round(v * 100), "change_pts": round((v - old.get(k, v)) * 100)} for k, v in top_kw],
        "new_questions": [dict(r) for r in conn.execute(
            "SELECT text, round, company FROM questions WHERE first_seen >= ? LIMIT 12", (run_started,))],
        "practice_today": [dict(r) for r in conn.execute(
            "SELECT text, round FROM questions WHERE practiced=0 ORDER BY RANDOM() LIMIT 5")],
        "new_reading": [dict(r) for r in conn.execute(
            "SELECT title, source, url FROM articles WHERE use='blog' AND first_seen >= ? LIMIT 6", (run_started,))],
    }


def _template_summary(f: dict) -> str:
    lines = [f"## Daily brief, {f['date']}", "",
             f"{f['new_roles_count']} new roles today, {f['active_roles']} open in total.", "", "### Roles to act on"]
    lines += [f"- [{j['company']}: {j['title']}]({j['url']}), fit {j['fit_score']}" for j in f["new_roles"][:6]] or ["- None new today."]
    lines += ["", "### Skills employers ask for"]
    lines += [f"- {k['keyword']}: {k['share_pct']}% of roles" + (f" ({k['change_pts']:+d} pts this week)" if k["change_pts"] else "") for k in f["top_keywords"][:6]]
    lines += ["", "### Practise today"] + [f"- ({q['round']}) {q['text']}" for q in f["practice_today"]]
    if f["new_reading"]:
        lines += ["", "### Reading"] + [f"- [{a['title']}]({a['url']}), {a['source']}" for a in f["new_reading"]]
    return "\n".join(lines)


def write_summary(conn, run_started: str, errors: list[str]) -> str:
    f = _facts(conn, run_started)
    text, model = None, "template"
    if llm.available():
        try:
            text = llm.chat(
                "You are a career coach for a GenAI engineer in India with ~5 years of experience in production "
                "RAG, agents and backend work, aiming for Senior GenAI / Applied AI roles at product companies such as Apple. "
                "Write a crisp daily brief in Markdown. Use only the facts given; never invent roles, links or numbers.",
                "Facts for today as JSON:\n" + json.dumps(f, ensure_ascii=False) +
                "\n\nWrite these sections: '## Daily brief, <date>' with a one-line headline; "
                "'### Roles to act on' (best 3-6 new roles with links and one line on why each fits; say if a "
                "role is a web lead to verify); '### Skill trends' (what is rising and what to add to the resume); "
                "'### Practise today' (the 5 practice questions, each with a one-line hint on what a strong answer covers); "
                "'### Reading' (only if there is new reading). Under 350 words.",
                max_tokens=900, temperature=0.3)
            model = llm.model()
        except Exception as ex:
            errors.append(f"NIM summary: {str(ex)[:160]}")
    text = text or _template_summary(f)
    conn.execute("INSERT OR REPLACE INTO summaries(day, markdown, model) VALUES (?,?,?)", (f["date"], text, model))
    return text


# ---------------------------------------------------------------- entry point
def run(skip_web: bool = False) -> dict:
    started = now_iso()
    errors: list[str] = []
    with connect() as conn:
        _seed(conn)
        run_id = conn.execute("INSERT INTO runs(started_at) VALUES (?)", (started,)).lastrowid
        conn.commit()
        new_jobs, seen = collect_jobs(conn, errors)
        conn.commit()
        if not skip_web:
            new_jobs += collect_web_leads(conn, errors)
            conn.commit()
        new_q, new_blogs = collect_research(conn, errors) if not skip_web else (0, 0)
        snapshot_keywords(conn)
        write_summary(conn, started, errors)
        conn.execute("UPDATE runs SET finished_at=?, new_jobs=?, seen_jobs=?, new_questions=?, errors=? WHERE id=?",
                     (now_iso(), new_jobs, seen, new_q, json.dumps(errors), run_id))
    result = {"new_jobs": new_jobs, "seen_jobs": seen, "new_questions": new_q, "new_blogs": new_blogs, "errors": errors}
    log.info("run done: %s", {k: v for k, v in result.items() if k != "errors"})
    for e in errors:
        log.warning("  %s", e)
    return result
