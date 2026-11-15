"""One adapter per careers-site type. Every adapter uses a public endpoint that the
company's own careers page calls; nothing here logs in or bypasses a block.

Each adapter returns a list of Listing. `detail` is a zero-arg callable that fetches
the full description, used only for listings that pass the relevance filter.
"""

from __future__ import annotations

import html
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

import httpx

from .config import HTTP_TIMEOUT, SEARCH_TERMS, USER_AGENT


@dataclass
class Listing:
    ext_id: str
    company: str
    title: str
    location: str
    url: str
    posted_at: Optional[str] = None
    description: Optional[str] = None
    detail: Optional[Callable[[], str]] = field(default=None, repr=False)


def client() -> httpx.Client:
    return httpx.Client(
        timeout=HTTP_TIMEOUT,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json, text/html;q=0.9"},
        follow_redirects=True,
    )


def strip_html(s: str | None) -> str:
    if not s:
        return ""
    s = html.unescape(s)
    s = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"[ \t ]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n", s).strip()


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def iso_date(value) -> Optional[str]:
    """Accepts epoch seconds/ms, ISO strings, or 'Month D, YYYY'."""
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)):
            if value > 1e11:
                value /= 1000
            return datetime.fromtimestamp(value, tz=timezone.utc).date().isoformat()
        v = str(value).strip()
        if re.match(r"\d{4}-\d{2}-\d{2}", v):
            return v[:10]
        for fmt in ("%B %d, %Y", "%b %d, %Y", "%d %b %Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(v, fmt).date().isoformat()
            except ValueError:
                pass
    except (ValueError, OSError, OverflowError):
        pass
    return None


def workday_posted(text: str | None) -> Optional[str]:
    """Workday gives 'Posted Today' / 'Posted Yesterday' / 'Posted 3 Days Ago' / 'Posted 30+ Days Ago'."""
    if not text:
        return None
    t = text.lower()
    days = 0 if "today" in t else 1 if "yesterday" in t else None
    m = re.search(r"(\d+)\+? days", t)
    if m:
        days = int(m.group(1))
    if days is None:
        return None
    return datetime.fromtimestamp(time.time() - days * 86400, tz=timezone.utc).date().isoformat()


# ---------------------------------------------------------------- Apple
def apple(c: httpx.Client, src: dict) -> list[Listing]:
    out: dict[str, Listing] = {}
    for term in SEARCH_TERMS:
        for page in (1, 2, 3):
            r = c.get("https://jobs.apple.com/en-in/search",
                      params={"search": term, "location": "india-INDC", "page": page})
            r.raise_for_status()
            m = re.search(r'__staticRouterHydrationData = JSON.parse\((".*?")\);', r.text, re.S)
            if not m:
                raise RuntimeError("Apple page layout changed (no hydration data)")
            search = json.loads(json.loads(m.group(1)))["loaderData"].get("search") or {}
            results = search.get("searchResults") or []
            for x in results:
                pid = x.get("positionId") or x.get("id")
                locs = ", ".join(l.get("name", "") for l in x.get("locations", []))
                out[pid] = Listing(
                    ext_id=pid, company=src["company"], title=x.get("postingTitle", ""),
                    location=locs,
                    url=f"https://jobs.apple.com/en-in/details/{pid}/{x.get('transformedPostingTitle', '')}",
                    posted_at=iso_date(x.get("postDateInGMT")),
                    description=x.get("jobSummary"),
                )
            if len(results) < 20:
                break
    return list(out.values())


# ---------------------------------------------------------------- Google
def google(c: httpx.Client, src: dict) -> list[Listing]:
    out: dict[str, Listing] = {}
    for term in SEARCH_TERMS:
        for page in (1, 2):
            r = c.get("https://www.google.com/about/careers/applications/jobs/results",
                      params={"q": term, "location": "India", "page": page})
            r.raise_for_status()
            m = re.search(r"AF_initDataCallback\(\{key: 'ds:1'.*?data:(.*?), sideChannel", r.text, re.S)
            if not m:
                raise RuntimeError("Google page layout changed (no ds:1 block)")
            jobs = json.loads(m.group(1))[0] or []
            for j in jobs:
                jid, title = str(j[0]), j[1]
                locs = ", ".join(l[0] for l in (j[9] or []) if l)
                parts = [j[10][1] if j[10] else "", j[3][1] if j[3] else "", j[4][1] if j[4] else ""]
                posted = j[12][0] if j[12] else None
                out[jid] = Listing(
                    ext_id=jid, company=src["company"], title=title, location=locs,
                    url=f"https://www.google.com/about/careers/applications/jobs/results/{jid}-{slug(title)}",
                    posted_at=iso_date(posted), description=strip_html("\n".join(parts)),
                )
            if len(jobs) < 20:
                break
    return list(out.values())


# ---------------------------------------------------------------- Amazon
def amazon(c: httpx.Client, src: dict) -> list[Listing]:
    out: dict[str, Listing] = {}
    for term in SEARCH_TERMS:
        r = c.get("https://www.amazon.jobs/en/search.json",
                  params={"base_query": term, "loc_query": "India", "result_limit": 100, "sort": "recent"})
        r.raise_for_status()
        for x in r.json().get("jobs", []):
            jid = str(x.get("id_icims") or x.get("id"))
            desc = "\n".join(filter(None, [x.get("description"), x.get("basic_qualifications"),
                                           x.get("preferred_qualifications")]))
            out[jid] = Listing(
                ext_id=jid, company=src["company"], title=x.get("title", ""),
                location=x.get("normalized_location") or x.get("location", ""),
                url="https://www.amazon.jobs" + x.get("job_path", ""),
                posted_at=iso_date(x.get("posted_date")), description=strip_html(desc),
            )
    return list(out.values())


# ---------------------------------------------------------------- Atlassian
def atlassian(c: httpx.Client, src: dict) -> list[Listing]:
    r = c.get("https://www.atlassian.com/endpoint/careers/listings")
    r.raise_for_status()
    out = []
    for x in r.json():
        post = x.get("portalJobPost") or {}
        desc = "\n".join(filter(None, [x.get("overview"), x.get("responsibilities"), x.get("qualifications")]))
        out.append(Listing(
            ext_id=str(x.get("id")), company=src["company"], title=x.get("title", ""),
            location="; ".join(x.get("locations") or []), url=post.get("portalUrl", ""),
            posted_at=iso_date((post.get("updatedDate") or "")[:10]), description=strip_html(desc),
        ))
    return out


# ---------------------------------------------------------------- Workday
def workday(c: httpx.Client, src: dict) -> list[Listing]:
    base = f"https://{src['host']}.myworkdayjobs.com"
    api = f"{base}/wday/cxs/{src['tenant']}/{src['site']}"
    out: dict[str, Listing] = {}
    for term in SEARCH_TERMS:
        for offset in (0, 20, 40):
            r = c.post(f"{api}/jobs", json={"appliedFacets": {}, "limit": 20, "offset": offset,
                                            "searchText": f"{term} India"})
            r.raise_for_status()
            posts = r.json().get("jobPostings", [])
            for p in posts:
                path = p.get("externalPath", "")
                if not path:
                    continue

                def fetch(path=path):
                    d = c.get(f"{api}{path}").json().get("jobPostingInfo", {})
                    return strip_html(d.get("jobDescription", ""))

                out[path] = Listing(
                    ext_id=path.rsplit("_", 1)[-1], company=src["company"], title=p.get("title", ""),
                    # "2 Locations" hides the city; the path segment (/job/Bangalore-India/...) has it.
                    location=" | ".join(filter(None, [p.get("locationsText", ""),
                                                      path.split("/")[2].replace("-", " ") if path.count("/") > 2 else ""])),
                    url=f"{base}/{src['site']}{path}", posted_at=workday_posted(p.get("postedOn")),
                    detail=fetch,
                )
            if len(posts) < 20:
                break
    return list(out.values())


# ---------------------------------------------------------------- SmartRecruiters
def smartrecruiters(c: httpx.Client, src: dict) -> list[Listing]:
    out: dict[str, Listing] = {}
    for term in SEARCH_TERMS:
        r = c.get(f"https://api.smartrecruiters.com/v1/companies/{src['slug']}/postings",
                  params={"q": term, "country": "in", "limit": 100})
        r.raise_for_status()
        for p in r.json().get("content", []):
            loc = p.get("location") or {}

            def fetch(ref=p.get("ref")):
                d = c.get(ref).json()
                secs = (d.get("jobAd") or {}).get("sections") or {}
                return strip_html("\n".join((s or {}).get("text", "") for s in secs.values()))

            out[p["id"]] = Listing(
                ext_id=p["id"], company=src["company"], title=p.get("name", ""),
                location=", ".join(filter(None, [loc.get("city"), loc.get("country")])),
                url=f"https://jobs.smartrecruiters.com/{src['slug']}/{p['id']}",
                posted_at=iso_date(p.get("releasedDate")), detail=fetch,
            )
    return list(out.values())


# ---------------------------------------------------------------- Greenhouse
def greenhouse(c: httpx.Client, src: dict) -> list[Listing]:
    r = c.get(f"https://boards-api.greenhouse.io/v1/boards/{src['slug']}/jobs", params={"content": "true"})
    r.raise_for_status()
    return [Listing(
        ext_id=str(j["id"]), company=src["company"], title=j.get("title", ""),
        location=(j.get("location") or {}).get("name", ""), url=j.get("absolute_url", ""),
        posted_at=iso_date(j.get("first_published") or j.get("updated_at")),
        description=strip_html(j.get("content")),
    ) for j in r.json().get("jobs", [])]


# ---------------------------------------------------------------- Lever
def lever(c: httpx.Client, src: dict) -> list[Listing]:
    r = c.get(f"https://api.lever.co/v0/postings/{src['slug']}", params={"mode": "json"})
    r.raise_for_status()
    out = []
    for j in r.json():
        cats = j.get("categories") or {}
        lists = "\n".join(f"{l.get('text', '')}\n{strip_html(l.get('content'))}" for l in j.get("lists", []))
        out.append(Listing(
            ext_id=j["id"], company=src["company"], title=j.get("text", ""),
            location=", ".join(cats.get("allLocations") or [cats.get("location", "")]),
            url=j.get("hostedUrl", ""), posted_at=iso_date(j.get("createdAt")),
            description="\n".join(filter(None, [j.get("descriptionPlain"), lists, j.get("additionalPlain")])),
        ))
    return out


ADAPTERS = {
    "apple": apple, "google": google, "amazon": amazon, "atlassian": atlassian,
    "workday": workday, "smartrecruiters": smartrecruiters, "greenhouse": greenhouse, "lever": lever,
}
