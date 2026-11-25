"""
location_filter.py - decide whether a job location is usable for a US-based search.

A location string may list several offices ("New York, NY | Toronto, Canada"); the job is
kept if ANY listed office is US or an unqualified remote. "Remote - Canada" is rejected.
"""

import re

US_STATES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut",
    "delaware", "florida", "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa",
    "kansas", "kentucky", "louisiana", "maine", "maryland", "massachusetts", "michigan",
    "minnesota", "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "new york", "north carolina",
    "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island",
    "south carolina", "south dakota", "tennessee", "texas", "utah", "vermont",
    "virginia", "washington", "west virginia", "wisconsin", "wyoming",
    "district of columbia",
}
STATE_ABBR = {
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id", "il", "in",
    "ia", "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv",
    "nh", "nj", "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc", "sd", "tn",
    "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy", "dc",
}
US_CITIES = {
    "san francisco", "new york city", "nyc", "seattle", "chicago", "los angeles",
    "boston", "austin", "denver", "atlanta", "miami", "bay area", "silicon valley",
    "palo alto", "mountain view", "menlo park", "redwood city", "san jose", "sunnyvale",
    "santa clara", "cupertino", "portland", "minneapolis", "nashville", "charlotte",
    "raleigh", "philadelphia", "pittsburgh", "detroit", "phoenix", "las vegas",
    "salt lake city", "san diego", "houston", "dallas", "brooklyn", "cambridge",
    "bellevue", "kirkland", "redmond", "boulder", "irvine", "durham", "columbus",
}
US_COUNTRY = {"united states", "united states of america", "usa", "u.s.a", "u.s.", "us", "u.s"}

FOREIGN = {
    "london", "united kingdom", "uk", "england", "scotland", "wales", "ireland", "dublin",
    "berlin", "germany", "munich", "frankfurt", "hamburg", "paris", "france", "lyon",
    "amsterdam", "netherlands", "stockholm", "sweden", "oslo", "norway", "copenhagen",
    "denmark", "zurich", "switzerland", "geneva", "vienna", "austria", "madrid", "spain",
    "barcelona", "lisbon", "portugal", "rome", "italy", "milan", "warsaw", "poland",
    "prague", "helsinki", "finland", "brussels", "belgium", "bucharest", "romania",
    "budapest", "hungary", "athens", "greece", "rotterdam", "emea", "europe", "apac",
    "latam", "tel aviv", "israel", "dubai", "uae", "united arab emirates", "abu dhabi",
    "qatar", "riyadh", "saudi arabia", "bangalore", "bengaluru", "india", "mumbai",
    "delhi", "hyderabad", "pune", "chennai", "gurgaon", "noida", "singapore", "tokyo",
    "japan", "osaka", "beijing", "shanghai", "china", "hong kong", "seoul", "south korea",
    "korea", "taipei", "taiwan", "bangkok", "thailand", "kuala lumpur", "malaysia",
    "jakarta", "indonesia", "manila", "philippines", "vietnam", "sydney", "australia",
    "melbourne", "brisbane", "auckland", "new zealand", "toronto", "canada", "vancouver",
    "montreal", "ottawa", "calgary", "mexico city", "mexico", "brazil", "sao paulo",
    "são paulo", "buenos aires", "argentina", "colombia", "chile", "nairobi", "kenya",
    "lagos", "nigeria", "cape town", "south africa", "egypt", "turkey", "istanbul",
    "kuwait", "kuwait city", "bahrain", "oman", "pakistan", "bangladesh", "sri lanka", "nepal",
    "morocco", "ghana", "peru", "uruguay", "costa rica", "panama", "luxembourg",
    "cyprus", "malta", "slovakia", "slovenia", "czech republic", "czechia", "ukraine", "serbia", "croatia", "bulgaria", "estonia", "latvia", "lithuania",
}

_SPLIT = re.compile(r"\s*(?:\||;|\n|/)\s*", re.I)


def _contains_phrase(text: str, phrases) -> bool:
    return any(re.search(rf"(?<![a-z]){re.escape(p)}(?![a-z])", text) for p in phrases)


def _has_abbr(text: str) -> bool:
    """State abbreviation as its own token after a comma/space, e.g. 'Austin, TX' / 'Remote - CA'."""
    for m in re.finditer(r"(?:,|\s|-)\s*([A-Z]{2})(?![A-Za-z])", text):
        if m.group(1).lower() in STATE_ABBR:
            return True
    return False


def _strip_states(low: str) -> str:
    for st in sorted(US_STATES, key=len, reverse=True):
        low = re.sub(rf"(?<![a-z]){re.escape(st)}(?![a-z])", " ", low)
    return low


def _part_is_foreign(part: str) -> bool:
    return _contains_phrase(_strip_states(part.lower()), FOREIGN)


def _part_is_us(part: str) -> bool:
    low = part.lower()
    if _contains_phrase(low, US_COUNTRY):
        return True
    if _part_is_foreign(part):      # "Toronto, CA" / "Berlin, DE": foreign city beats ambiguous abbreviation
        return False
    return (_contains_phrase(low, US_STATES) or _contains_phrase(low, US_CITIES)
            or _has_abbr(part))


def is_us_or_remote(location: str) -> bool:
    """
    True for US locations and for remote/unspecified locations with no foreign qualifier.
    Examples: "Remote - US" True, "Hybrid - New York" True, "Remote" True, "" True,
    "Remote - Canada" False, "London, UK" False, "Toronto | New York, NY" True.
    """
    if not location or not location.strip():
        return True
    parts = [p for p in _SPLIT.split(location) if p and p.strip()]
    if not parts:
        return True
    if any(_part_is_us(p) for p in parts):
        return True
    # No US signal anywhere: reject if any foreign signal, otherwise generic remote/unknown -> keep
    return not any(_part_is_foreign(p) for p in parts)


def clean_location(location: str) -> str:
    if not location or not location.strip():
        return "Remote / United States"
    return re.sub(r"\s+", " ", location.strip())
