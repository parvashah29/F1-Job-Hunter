"""
role_matcher.py — Keyword-based tier classifier for job titles.
Pre-filters job titles before sending to the AI (saves LLM calls).
Also filters out senior/experienced roles not appropriate for a May 2027 new grad.
"""

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Seniority blocklist — roles with these prefixes/keywords are excluded.
# Keeps the output relevant for a new grad graduating May 2027.
# ---------------------------------------------------------------------------

SENIORITY_BLOCKLIST = [
    "senior", "sr.", "sr ",
    "staff", "principal", "distinguished",
    "lead ", "tech lead", "team lead",
    "director", "vp ", "vice president",
    "head of", "manager", "chief",
    "architect",
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


def is_senior(title: str) -> bool:
    """
    Return True if the title contains seniority markers that indicate
    this role is NOT appropriate for a May 2027 new grad.
    """
    lowered = title.lower().strip()
    return any(marker in lowered for marker in SENIORITY_BLOCKLIST)


def classify_tier(title: str) -> Optional[str]:
    """
    Return the tier ('1', '2', '3') if the job title matches our role keywords,
    or None if the job is completely unrelated OR is a senior-level role.
    """
    lowered = title.lower().strip()

    # Immediately reject senior/experienced roles
    if is_senior(title):
        return None

    # Check company-specific titles first (always tier 1)
    for kw in COMPANY_SPECIFIC_TITLES:
        if kw in lowered:
            return "1"

    # Check tiers 1 → 2 → 3 in order
    for tier, keywords in TIER_KEYWORDS.items():
        for kw in keywords:
            if kw in lowered:
                return tier

    # Fallback: check early-career signals alone — might still be relevant
    for signal in EARLY_CAREER_SIGNALS:
        if signal in lowered:
            # Only pass through if it's even vaguely tech-related
            tech_hints = ["engineer", "developer", "scientist", "analyst",
                          "data", "ai", "ml", "software", "cloud", "platform"]
            if any(h in lowered for h in tech_hints):
                return "3"  # Conservative — mark as tier 3

    return None  # Not in our target role set — skip


def is_relevant(title: str) -> bool:
    """Returns True if the job title is worth processing (relevant + not senior)."""
    return classify_tier(title) is not None
