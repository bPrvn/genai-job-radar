"""Research agent: collects interview questions and reading material.

Sources (all public, no logins):
  - RSS feeds (Medium tags, engineering blogs)       -> questions + blog reading list
  - dev.to API and Hacker News (Algolia) API         -> interview write-ups
  - Web search: Tavily API if TAVILY_API_KEY is set, else `ddgs` -> interview write-ups + job leads
Questions are pulled out of each article by NVIDIA NIM when a key is set,
otherwise by a rule-based extractor.
"""

from __future__ import annotations

import hashlib
import os
import re
from concurrent.futures import ThreadPoolExecutor
import time
from dataclasses import dataclass
from typing import Iterable

import feedparser
import httpx

from . import config, llm
from .sources import client, strip_html


@dataclass
class Article:
    url: str
    title: str
    source: str
    published: str | None
    text: str          # body text when we have it (RSS content, dev.to markdown)
    use: str           # "questions" | "blog"
    company: str | None = None


@dataclass
class Question:
    text: str
    round: str
    company: str | None
    source: str
    source_url: str


# ---------------------------------------------------------------- question rounds
ROUND_RULES = [
    ("Behavioural", r"tell me about|a time (when|you)|conflict with|why (do you want|apple|google|this company)|your (strength|weakness)|you failed|disagree|proud of"),
    ("LLM system design", r"\bdesign (a|an|the)\b|how would you (build|architect|design)|at scale|high[- ]level design|end[- ]to[- ]end system"),
    ("Evaluation", r"evaluat|metric|benchmark|judge|precision|recall|a/b|hallucination rate|faithful"),
    ("GenAI depth", r"transformer|attention|embedding|fine[- ]?tun|lora|quantiz|token|hallucinat|\brag\b|retriev|prompt|\bllm|kv[- ]cache|rlhf|vector|chunk|agent|diffusion|context window"),
    ("Coding (DSA)", r"leetcode|array|string|linked list|\btree\b|graph|dynamic programming|\bdp\b|implement|algorithm|complexity|binary search|heap|sort|substring|matrix"),
    ("Backend", r"\bapi\b|database|cache|latency|kafka|queue|microservice|\bsql\b|rest\b|concurren|thread"),
]
_ROUND_RX = [(name, re.compile(rx, re.I)) for name, rx in ROUND_RULES]


def classify(q: str) -> str:
    for name, rx in _ROUND_RX:
        if rx.search(q):
            return name
    return "General"


_Q_WORD = re.compile(r"^(what|why|how|when|which|where|can you|could you|is it|should|do you|does|would)\b", re.I)
_IMPERATIVE = re.compile(r"^(explain|describe|design|implement|write|compare|derive|walk me|tell me|discuss|"
                         r"list|define|differentiate|given)\b", re.I)
_TECH = re.compile(r"model|llm|rag|data|system|design|api|train|embedding|vector|algorithm|array|"
                   r"tree|graph|latency|scale|prompt|token|transformer|attention|evaluat|python|ml\b|"
                   r"agent|fine-?tun|retriev|inference|gpu|cache|database", re.I)
_PREFIX = re.compile(r"^\s*(?:[-*\u2022#>]+\s*)*(?:(?:question|q)\s*\d*\s*[:.)\-]\s*|\d+\s*[.):\-]\s*)*", re.I)


def clean_question(raw: str) -> str:
    s = re.sub(r"[*_`]+", "", raw)          # markdown emphasis / code ticks
    s = _PREFIX.sub("", s).strip(" :-")
    return re.sub(r"\s+", " ", s)


def rule_extract(text: str) -> list[str]:
    """Lines that read like interview questions: a question ending in '?', or an imperative
    prompt ('Explain…', 'Design…'), about a technical topic."""
    out = []
    for raw in re.split(r"\n|(?<=\?)\s+", text):
        s = clean_question(raw)
        if not 25 <= len(s) <= 220 or not _TECH.search(s):
            continue
        if s.endswith("?") and (_Q_WORD.match(s) or _IMPERATIVE.match(s)):
            out.append(s)
        elif _IMPERATIVE.match(s) and not s.endswith(":"):
            out.append(s.rstrip(".") + ".")
    return out


def llm_extract(article: Article, text: str) -> list[dict]:
    system = ("You extract technical interview questions from articles about machine learning, "
              "GenAI / LLM, data and software engineering interviews.")
    user = (f"Article title: {article.title}\nURL: {article.url}\n\n"
            "Return a JSON list of up to 15 objects {\"question\": str, \"round\": str, \"company\": str|null}. "
            "Only questions an interviewer actually asked or that the article lists as interview questions; "
            "rewrite each as one clear standalone question. round is one of: "
            + ", ".join(r for r, _ in ROUND_RULES) + ", General. company = the company interviewing, "
            "if the article says. Return [] if the article has no interview questions.\n\n"
            f"Article text:\n{text[:12000]}")
    items = llm.chat_json(system, user)
    return [i for i in items if isinstance(i, dict) and i.get("question")]


def questions_from(article: Article, text: str, use_llm: bool) -> list[Question]:
    if use_llm:
        try:
            return [Question(text=clean_question(i["question"]), round=i.get("round") or classify(i["question"]),
                             company=i.get("company") or article.company, source=article.source,
                             source_url=article.url) for i in llm_extract(article, text)]
        except Exception:
            pass  # fall through to the rule-based extractor
    return [Question(text=q, round=classify(q), company=article.company, source=article.source,
                     source_url=article.url) for q in rule_extract(text)]


# ---------------------------------------------------------------- page fetch
def fetch_text(c: httpx.Client, url: str) -> str:
    r = c.get(url, headers={"Accept": "text/html"})
    r.raise_for_status()
    h = re.sub(r"(?is)<(script|style|nav|footer|header|noscript|svg)[^>]*>.*?</\1>", " ", r.text)
    m = re.search(r"(?is)<(article|main)[^>]*>(.*)</\1>", h)
    return strip_html(m.group(2) if m else h)[:20000]


# ---------------------------------------------------------------- sources
def rss_articles(c: httpx.Client, errors: list[str]) -> list[Article]:
    out = []
    for feed in config.RSS_FEEDS:
        try:
            resp = c.get(feed["url"], headers={"Accept": "application/rss+xml, application/xml, text/xml, */*"})
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
            if parsed.bozo and not parsed.entries:
                raise RuntimeError(str(parsed.bozo_exception)[:120])
            for e in parsed.entries[:15]:
                body = ""
                if e.get("content"):
                    body = e.content[0].get("value", "")
                body = strip_html(body or e.get("summary", ""))
                pub = e.get("published_parsed") or e.get("updated_parsed")
                out.append(Article(
                    url=e.get("link", ""), title=strip_html(e.get("title", "")), source=feed["name"],
                    published=f"{pub.tm_year:04d}-{pub.tm_mon:02d}-{pub.tm_mday:02d}" if pub else None,
                    text=body, use=feed["use"]))
        except Exception as ex:  # one bad feed never stops the run
            errors.append(f"rss {feed['name']}: {ex}")
    return out


def devto_articles(c: httpx.Client, errors: list[str]) -> list[Article]:
    out, seen = [], set()
    for tag in config.DEVTO_TAGS:
        time.sleep(1)
        try:
            for a in c.get("https://dev.to/api/articles", params={"tag": tag, "per_page": 30, "top": 7}).json():
                if a["id"] in seen or "interview" not in (a.get("title", "") + " ".join(a.get("tag_list", []))).lower():
                    continue
                seen.add(a["id"])
                time.sleep(1)
                body = c.get(f"https://dev.to/api/articles/{a['id']}").json().get("body_markdown", "")
                out.append(Article(url=a["url"], title=a["title"], source="dev.to",
                                   published=(a.get("published_at") or "")[:10], text=body, use="questions"))
        except Exception as ex:
            errors.append(f"dev.to {tag}: {ex}")
    return out


def hn_articles(c: httpx.Client, errors: list[str]) -> list[Article]:
    out = []
    for q in config.QUESTION_QUERIES[:3]:
        try:
            hits = c.get("https://hn.algolia.com/api/v1/search_by_date",
                         params={"query": q, "tags": "story", "hitsPerPage": 10}).json().get("hits", [])
            for h in hits:
                if h.get("url"):
                    out.append(Article(url=h["url"], title=h.get("title", ""), source="Hacker News",
                                       published=(h.get("created_at") or "")[:10], text="", use="questions"))
        except Exception as ex:
            errors.append(f"hn {q}: {ex}")
    return out


def _tavily(query: str, timelimit: str) -> list[dict]:
    r = httpx.post("https://api.tavily.com/search", timeout=30,
                   headers={"Authorization": f"Bearer {os.environ['TAVILY_API_KEY']}"},
                   json={"query": query, "max_results": config.WEB_RESULTS_PER_QUERY,
                         "time_range": {"d": "day", "w": "week", "m": "month", "y": "year"}[timelimit]})
    r.raise_for_status()
    return [{"title": x.get("title", ""), "href": x.get("url", ""), "body": x.get("content", "")}
            for x in r.json().get("results", [])]


def _ddgs(query: str, timelimit: str) -> list[dict]:
    """Free search via ddgs. Tries the primary engine (Yandex), then the fallbacks, and
    returns the first engine that yields results. ddgs raises when an engine finds nothing
    or answers with a bot check, so each engine is guarded."""
    import logging
    import random
    import time
    from ddgs import DDGS
    logging.getLogger("ddgs").setLevel(logging.ERROR)
    engines = [config.WEB_BACKEND, *config.WEB_BACKEND_FALLBACKS]
    last_exc: Exception | None = None
    # Yandex answers automated queries well but soft-rate-limits after rapid calls (returns
    # nothing). Retry the engines a few times with a backoff so a busy run still gets results.
    for attempt in range(config.WEB_RETRIES):
        time.sleep(random.uniform(*config.WEB_PACE_SECONDS))
        for engine in engines:
            try:
                hits = list(DDGS(timeout=config.WEB_HTTP_TIMEOUT).text(
                    query, backend=engine, region="in-en", timelimit=timelimit,
                    max_results=config.WEB_RESULTS_PER_QUERY) or [])
                if hits:
                    return hits
            except Exception as ex:  # "No results found." / bot check / timeout: try the next engine
                last_exc = ex
    if last_exc:
        raise last_exc
    return []


def web_search(query: str, errors: list[str], timelimit: str | None = None) -> list[dict]:
    """Tavily when TAVILY_API_KEY is set (reliable), otherwise free DuckDuckGo-style search via ddgs
    (search engines sometimes answer automated queries with a bot check: then it returns nothing)."""
    timelimit = timelimit or config.WEB_TIMELIMIT
    provider = _tavily if os.environ.get("TAVILY_API_KEY") else _ddgs
    try:
        return provider(query, timelimit)
    except Exception as ex:
        errors.append(f"web search ({provider.__name__[1:]}) '{query[:40]}': {str(ex)[:80]}")
        return []


def fetchable(url: str) -> bool:
    return url.startswith("http") and not any(d in url for d in config.NO_FETCH_DOMAINS)


def web_question_articles(errors: list[str]) -> list[Article]:
    out, seen = [], set()
    for company in config.WEB_QUESTION_COMPANIES:
        for query in config.WEB_QUESTION_QUERIES:
            for r in web_search(query.format(company=company), errors, config.WEB_QUESTION_TIMELIMIT):
                url = r.get("href", "")
                if not fetchable(url) or url in seen:  # skip login-walled sites and duplicates
                    continue
                seen.add(url)
                out.append(Article(url=url, title=r.get("title", ""), source="Web search",
                                   published=None, text="", use="questions", company=company))
    return out


def rss_job_leads(errors: list[str]) -> list[dict]:
    """Parse configured job-board RSS feeds so new roles aren't missed day to day.
    Returns lead dicts shaped like web_job_leads (title, snippet, url, company, ext_id)."""
    import feedparser
    out = []
    with client() as c:
        for feed in config.JOB_RSS_FEEDS:
            try:
                resp = c.get(feed["url"], headers={"Accept": "application/rss+xml, application/xml, text/xml, */*"})
                resp.raise_for_status()
                parsed = feedparser.parse(resp.content)
                if parsed.bozo and not parsed.entries:
                    raise RuntimeError(str(parsed.bozo_exception)[:120])
                for e in parsed.entries[:40]:
                    title = strip_html(e.get("title", ""))
                    url = e.get("link", "")
                    if not title or not url:
                        continue
                    # WeWorkRemotely titles are "Company: Role"; split the company out when present.
                    company, _, role = title.partition(":")
                    if role.strip():
                        company, title = company.strip(), role.strip()
                    else:
                        company = feed["name"]
                    out.append({
                        "title": title, "snippet": strip_html(e.get("summary", ""))[:600],
                        "url": url, "company": company[:60] or feed["name"],
                        "ext_id": hashlib.sha1(url.encode()).hexdigest()[:16],
                    })
            except Exception as ex:  # one bad feed never stops the run
                errors.append(f"job rss {feed['name']}: {ex}")
    return out


def web_job_leads(errors: list[str]) -> list[dict]:
    """Job leads for companies with no public jobs API. Unverified: shown with a 'lead' badge."""
    leads, seen = [], set()
    for company in config.WEB_JOB_COMPANIES:
        token = company.split()[0].lower()          # "walmart", "jpmorgan", "american"...
        token = {"american": "amex", "goldman": "goldman", "sarvam": "sarvam"}.get(token, token)
        results = [r for q in config.WEB_JOB_QUERIES for r in web_search(q.format(company=company), errors)]
        for r in results:
            url = r.get("href", "")
            hay = (r.get("title", "") + " " + url).lower()
            if url in seen or not (token in hay or company.lower() in hay):
                continue
            seen.add(url)
            leads.append({
                "ext_id": hashlib.sha1(url.encode()).hexdigest()[:16], "company": company,
                "title": strip_html(r.get("title", "")), "url": url, "snippet": strip_html(r.get("body", "")),
            })
    return leads


# ---------------------------------------------------------------- orchestration
def collect(known_urls: set[str], errors: list[str]) -> tuple[list[Article], list[Question]]:
    """Returns (blog articles for the reading list, questions extracted from new articles)."""
    use_llm = llm.available()
    with client() as c:
        articles = rss_articles(c, errors) + devto_articles(c, errors) + hn_articles(c, errors) + web_question_articles(errors)
        new = [a for a in articles if a.url and a.url not in known_urls]
        blogs = [a for a in new if a.use == "blog"]
        # Phase 1: gather (article, text) pairs. Kept sequential because it shares the
        # HTTP client and respects the WEB_PAGES_TO_READ page-fetch budget.
        pairs: list[tuple[Article, str]] = []
        fetched = 0
        # Company-tagged web articles first, so they win the page-fetch budget over generic blogs
        # (grouping questions by company is the point).
        q_articles = sorted((a for a in new if a.use == "questions"), key=lambda a: a.company is None)
        for a in q_articles:
            text = a.text
            if len(text) < 400:  # feed gave a teaser only: read the page
                if fetched >= config.WEB_PAGES_TO_READ or not fetchable(a.url):
                    continue
                fetched += 1
                try:
                    text = fetch_text(c, a.url)
                except Exception as ex:
                    errors.append(f"fetch {a.url[:60]}: {ex}")
                    continue
            if "interview" not in (a.title + text[:3000]).lower():
                continue
            pairs.append((a, text))

        # Phase 2: LLM extraction. Parallelise across the available NIM keys so each
        # worker round-robins onto a different key (falls back to serial without a key).
        questions: list[Question] = []
        workers = max(1, min(llm.key_count(), len(pairs))) if use_llm else 1
        if workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for qs in pool.map(lambda p: questions_from(p[0], p[1], use_llm), pairs):
                    questions.extend(qs)
        else:
            for a, text in pairs:
                questions.extend(questions_from(a, text, use_llm))
        return blogs + [a for a in new if a.use == "questions"], questions


def dedupe(questions: Iterable[Question]) -> list[Question]:
    seen, out = set(), []
    for q in questions:
        key = re.sub(r"[^a-z0-9]", "", q.text.lower())[:120]
        if key and key not in seen:
            seen.add(key)
            out.append(q)
    return out
