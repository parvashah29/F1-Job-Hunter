"""
role_matcher.py — Keyword-based tier classifier for job titles.
Pre-filters job titles before sending to the AI (saves LLM calls).
Also filters out senior/experienced roles not appropriate for a new grad.
"""

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Seniority blocklist — roles with these prefixes/keywords are excluded.
# Keeps the output relevant for a new grad graduating May 2027.
# ---------------------------------------------------------------------------

SENIORITY_BLOCKLIST = [
    "senior", "sr", "staff", "principal", "distinguished",
    "lead", "tech lead", "team lead",
    "director", "vp", "vice president",
    "head of", "manager", "chief",
    "architect", "ii", "iii", "iv", "intern", "internship", "co-op",
    # Contract/consulting markers
    "(contract)", "contractor", "freelance",
    # Over-qualified research
    "postdoc", "post-doc", "phd researcher",
]

# ---------------------------------------------------------------------------
# Master keyword map — ordered by priority (tier 1 checked first)
# Lowercased for case-insensitive matching
# ---------------------------------------------------------------------------

TIER_KEYWORDS = {
    "1": [
        "data scientist", "associate data scientist", "junior data scientist",
        "new grad data scientist", "data engineer", "associate data engineer",
        "junior data engineer", "new grad data engineer",
        "machine learning engineer", "ml engineer", "associate machine learning",
        "junior machine learning", "ai engineer", "applied ai engineer",
        "software engineer", "associate software engineer",
        "new grad software engineer", "software developer",
        "backend software engineer", "ai software engineer",
    ],
    "2": [
        "analytics engineer", "data analyst", "product data analyst",
        "business intelligence analyst", "bi analyst", "bi engineer",
        "business intelligence engineer", "decision scientist",
        "applied scientist", "research engineer", "computer vision engineer",
        "mlops engineer", "ml ops engineer", "ai platform engineer",
        "ml platform engineer", "data platform engineer",
        "cloud data engineer", "big data engineer",
    ],
    "3": [
        "ai developer", "machine learning developer", "data analytics engineer",
        "ai solutions engineer", "ai consultant", "data consultant",
        "cloud engineer", "python developer", "backend engineer",
        "full stack engineer", "fullstack engineer",
        "software development engineer", "sde i", "sde-i",
        "systems engineer", "quantitative analyst", "operations research analyst",
    ],
}

# Early career signals — if ANY of these appear in the title alongside a role
# keyword above, treat the match as confirmed (even partial title matches)
EARLY_CAREER_SIGNALS = [
    "new grad", "university graduate", "university hire", "campus hire",
    "graduate program", "graduate engineer", "graduate software",
    "graduate data", "early career", "early talent", "entry level",
    "associate", "junior", "level i", "engineer i", "sde i", "sde-i",
    "residency", "rotational program", "development program",
]

# Company-specific titles (used at BigTech) — always treated as Tier 1
COMPANY_SPECIFIC_TITLES = [
    "university graduate – ai", "university graduate – data",
    "university graduate – software", "ai residency",
    "machine learning residency", "technology analyst program",
    "engineering rotational", "data science rotational",
    "software engineering rotational",
]



def _compile(keywords):
    return [(kw, re.compile(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])")) for kw in keywords]


_TECH_HINTS = ["engineer", "developer", "scientist", "analyst", "data", "ai", "ml",
               "software", "cloud", "platform"]

_state = {}


def _build(tier_keywords=None, blocklist=None, early=None, company_specific=None):
    _state["blocklist"] = _compile([k.lower() for k in (blocklist or SENIORITY_BLOCKLIST)])
    _state["tiers"] = {t: _compile([k.lower() for k in kws])
                       for t, kws in (tier_keywords or TIER_KEYWORDS).items()}
    _state["early"] = _compile([k.lower() for k in (early or EARLY_CAREER_SIGNALS)])
    _state["company"] = _compile([k.lower() for k in (company_specific or COMPANY_SPECIFIC_TITLES)])
    _state["hints"] = _compile(_TECH_HINTS)


def configure(config: dict):
    """Use the `roles:` section of config.yaml (tier1/2/3, early_career_keywords, company_specific)."""
    roles = (config or {}).get("roles") or {}
    tiers = {t: roles[f"tier{t}"] for t in ("1", "2", "3") if roles.get(f"tier{t}")}
    blocklist = list(SENIORITY_BLOCKLIST) + [k for k in roles.get("exclude_keywords", []) or []]
    _build(tiers or None, blocklist, roles.get("early_career_keywords") or None,
           [k for k in (roles.get("company_specific") or [])] or None)


def _any(compiled, text):
    return any(rx.search(text) for _, rx in compiled)


def is_senior(title: str) -> bool:
    """True if the title carries seniority/level markers inappropriate for a new grad."""
    return _any(_state["blocklist"], title.lower().strip())


def classify_tier(title: str) -> Optional[str]:
    """Return '1'/'2'/'3' if the title matches a target role and is not senior, else None."""
    lowered = title.lower().strip()
    if not lowered or is_senior(lowered):
        return None
    if _any(_state["company"], lowered):
        return "1"
    for tier in ("1", "2", "3"):
        if _any(_state["tiers"].get(tier, []), lowered):
            return tier
    if _any(_state["early"], lowered) and _any(_state["hints"], lowered):
        return "3"
    return None


def is_relevant(title: str) -> bool:
    return classify_tier(title) is not None


_build()
