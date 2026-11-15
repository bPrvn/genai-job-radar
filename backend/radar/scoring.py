"""Relevance filter, experience parsing, keyword tagging and a 0-100 fit score."""

import re

from .config import (KEYWORDS, LOCATION_WORDS, PREFERRED_CITIES, PROFILE,
                     TITLE_EXCLUDE, TITLE_INCLUDE)

_INC = [re.compile(p, re.I) for p in TITLE_INCLUDE]
_EXC = [re.compile(p, re.I) for p in TITLE_EXCLUDE]
_KW = {label: re.compile("|".join(pats), re.I) for label, pats in KEYWORDS.items()}
_YEARS = re.compile(r"(\d{1,2})\s*(?:\+|-\s*\d{1,2}|to\s*\d{1,2})?\s*\+?\s*(?:years|yrs)", re.I)


def title_relevant(title: str) -> bool:
    return any(p.search(title) for p in _INC) and not any(p.search(title) for p in _EXC)


def location_ok(location: str) -> bool:
    loc = (location or "").lower()
    return any(w in loc for w in LOCATION_WORDS)


def min_years(text: str) -> int | None:
    """The first 'N years' figure: JDs state the overall requirement first
    ('8 years in software development', then '5 years with ML')."""
    for m in _YEARS.finditer(text or ""):
        if int(m.group(1)) <= 20:
            return int(m.group(1))
    return None


def keywords(text: str) -> list[str]:
    return [label for label, rx in _KW.items() if rx.search(text or "")]


def fit_score(title: str, location: str, description: str, years: int | None) -> int:
    t = title.lower()
    score = 40
    if re.search(r"gen ?ai|generative|llm|applied ai", t):
        score += 20
    elif re.search(r"machine learning|\bml\b|\bai\b", t):
        score += 12
    if re.search(r"\bstaff\b|principal|distinguished|architect", t):
        score -= 10          # usually 8+ years
    elif re.search(r"senior|\bsr\b|\blead\b|\bii\b|\b3\b", t):
        score += 5
    if any(c in (location or "").lower() for c in PREFERRED_CITIES):
        score += 5
    if years is not None:
        if PROFILE["min_years"] <= years <= PROFILE["years"] + 1:
            score += 15
        elif years > PROFILE["max_years"]:
            score -= 20
        elif years < PROFILE["min_years"]:
            score -= 5
    desc = (description or "").lower()
    score += min(15, 2 * sum(1 for s in PROFILE["skills"] if s in desc))
    return max(0, min(100, score))
