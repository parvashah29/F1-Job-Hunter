"""
eligibility.py - deterministic, explainable eligibility rules for an F-1/OPT new grad.

evaluate(text) -> (verdict, reason), verdict in {"YES", "NO"}.
NO only for explicit red flags: no sponsorship, citizenship/PR required, security
clearance, or 3+ years of required experience. Anything unclear stays YES (human review).
"""

import re

_I = re.IGNORECASE

# Phrases that negate a clearance/citizenship mention ("no clearance required").
_NEGATED_CLEARANCE = re.compile(
    r"\b(?:no|not|without)\b[^.\n]{0,25}\b(?:security\s+)?clearance\b", _I)

SPONSORSHIP_NO = [re.compile(p, _I) for p in [
    r"\b(?:will|would|do|does|can|could|may)\s*(?:not|n't)\s+(?:be\s+able\s+to\s+)?(?:provide\s+|offer\s+)?(?:\w+\s+){0,3}?sponsor",
    r"\b(?:unable|not\s+able|not\s+in\s+a\s+position)\s+to\s+(?:provide\s+|offer\s+)?(?:\w+\s+){0,3}?sponsor",
    r"\bno\s+(?:visa\s+|work\s+visa\s+|immigration\s+|employment\s+)?sponsorship\b",
    r"\bsponsorship\s+(?:is\s+)?(?:not\s+(?:available|offered|provided)|unavailable)",
    r"\bnot\s+(?:eligible|available)\s+for\s+(?:visa\s+|immigration\s+)?sponsorship",
    r"\bwithout\s+(?:the\s+need\s+for\s+|requiring\s+|needing\s+|any\s+)?(?:current\s+or\s+future\s+|now\s+or\s+in\s+the\s+future\s+)?(?:visa\s+|employer\s+|immigration\s+)?sponsorship",
    r"\b(?:not|never)\s+require\s+(?:\w+\s+){0,2}sponsorship",
    r"\bdoes\s+not\s+(?:offer|provide)\s+(?:\w+\s+){0,2}(?:visa|sponsorship)",
    r"\bno\s+c2c\b",
    r"\bnot\s+(?:be\s+)?(?:able\s+to\s+)?(?:sponsor|sponsoring)\s+(?:\w+\s+){0,2}visa",
]]

CITIZENSHIP = [re.compile(p, _I) for p in [
    r"\bu\.?s\.?\s+citizen(?:ship)?s?\s+(?:only|required|is\s+required|status\s+required)",
    r"\bcitizens?\s+only\b",
    r"\bmust\s+be\s+(?:a\s+)?(?:u\.?s\.?|united\s+states|american)\s+citizen",
    r"\b(?:requires?|requiring|require)\s+(?:u\.?s\.?\s+|united\s+states\s+)?citizenship",
    r"\bunited\s+states\s+citizen(?:ship)?\s+(?:is\s+)?required",
    r"\bu\.?s\.?\s+citizens?\s+(?:or|and)\s+(?:lawful\s+)?(?:permanent\s+residents?|green\s+card)",
    r"\bgreen\s+card\s+(?:holders?\s+)?(?:only|required)",
    r"\bmust\s+be\s+a\s+u\.?s\.?\s+person\b",
    r"\bitar\b[^.\n]{0,80}\b(?:citizen|u\.?s\.?\s+person)",
]]

CLEARANCE = [re.compile(p, _I) for p in [
    r"\bts\s*/\s*sci\b",
    r"\btop\s+secret\b",
    r"\b(?:active\s+|current\s+|valid\s+|interim\s+)?(?:secret|dod|government)\s+(?:security\s+)?clearance",
    r"\bsecurity\s+clearance\b",
    r"\bpolygraph\b",
    r"\bability\s+to\s+obtain\s+(?:a\s+)?(?:u\.?s\.?\s+)?(?:government\s+)?clearance",
]]

YOE = [re.compile(p, _I) for p in [
    r"(?<![\d\-\u2013.])\b([3-9]|\d{2})\+?\s*(?:or\s+more\s*)?years?\s+(?:of\s+)?(?:\w+\s+){0,4}?(?:experience|expertise)",
    r"(?:minimum|at\s+least|min\.?)\s+(?:of\s+)?([3-9]|\d{2})\s+years?",
    r"\b([3-9]|\d{2})\s*[-–]\s*\d+\s+years?\s+(?:of\s+)?(?:\w+\s+){0,4}?(?:experience|expertise)",
]]


def _first(patterns, text):
    for p in patterns:
        m = p.search(text)
        if m:
            return m.group(0).strip()
    return None


def check_yoe(text: str) -> bool:
    """True if the text explicitly requires 3+ years of experience."""
    return _first(YOE, (text or "")[:6000]) is not None


def evaluate(text: str) -> tuple:
    """Return (verdict, reason). reason is a short machine+human readable label."""
    text = (text or "").strip()
    if not text:
        return "YES", "rules:no-description"
    cleaned = _NEGATED_CLEARANCE.sub(" ", text)
    hit = _first(SPONSORSHIP_NO, cleaned)
    if hit:
        return "NO", f"rules:no-sponsorship ({hit[:60]})"
    hit = _first(CITIZENSHIP, cleaned)
    if hit:
        return "NO", f"rules:citizenship ({hit[:60]})"
    hit = _first(CLEARANCE, cleaned)
    if hit:
        return "NO", f"rules:clearance ({hit[:60]})"
    hit = _first(YOE, cleaned[:6000])
    if hit:
        return "NO", f"rules:experience ({hit[:60]})"
    return "YES", "rules:ok"
