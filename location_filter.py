"""
location_filter.py — US/Remote location validator for F-1 Job Hunter Agent
Filters out international roles before sending to AI — saves LLM calls.
"""

# ---------------------------------------------------------------------------
# US city/state keywords — if ANY appear in location, it's US-eligible
# ---------------------------------------------------------------------------
US_SIGNALS = {
    # Country-level
    "united states", "usa", "u.s.a", "u.s.", "us ",
    # Remote
    "remote", "anywhere", "distributed", "work from home", "wfh",
    # States (common ones)
    "california", "new york", "washington", "texas", "illinois",
    "massachusetts", "georgia", "florida", "colorado", "virginia",
    "north carolina", "pennsylvania", "ohio", "michigan", "arizona",
    "minnesota", "oregon", "tennessee", "missouri", "maryland",
    "new jersey", "connecticut", "nevada", "utah",
    # State abbreviations (space or comma bounded — avoid false matches)
    " ca,", " ny,", " wa,", " tx,", " il,", " ma,", " ga,", " fl,",
    " co,", " va,", " nc,", " pa,", " oh,", " mi,", " az,", " mn,",
    " or,", " tn,", " md,", " nj,", " ct,", " nv,", " ut,",
    # Major cities
    "san francisco", "new york city", "nyc", "seattle", "chicago",
    "los angeles", "boston", "austin", "denver", "atlanta", "miami",
    "washington dc", "dc", "bay area", "silicon valley", "palo alto",
    "mountain view", "menlo park", "redwood city", "san jose",
    "portland", "minneapolis", "nashville", "charlotte", "raleigh",
    "philadelphia", "pittsburgh", "detroit", "phoenix", "las vegas",
    "salt lake city", "san diego", "houston", "dallas",
}

# ---------------------------------------------------------------------------
# International signals — if ANY appear (and no US signal), it's non-US
# ---------------------------------------------------------------------------
INTERNATIONAL_SIGNALS = {
    # Europe
    "london", "united kingdom", "u.k.", " uk,", " uk ",
    "england", "scotland", "wales", "ireland", "dublin",
    "berlin", "germany", "munich", "frankfurt", "hamburg",
    "paris", "france", "lyon", "amsterdam", "netherlands",
    "stockholm", "sweden", "oslo", "norway", "copenhagen", "denmark",
    "zurich", "switzerland", "geneva", "vienna", "austria",
    "madrid", "spain", "barcelona", "lisbon", "portugal",
    "rome", "italy", "milan", "warsaw", "poland", "prague",
    "reykjavik", "iceland", "helsinki", "finland", "brussels", "belgium",
    "bucharest", "romania", "budapest", "hungary", "athens", "greece",
    "amsterdam", "rotterdam",
    # Middle East
    "tel aviv", "israel", "dubai", "uae", "abu dhabi", "qatar",
    "riyadh", "saudi arabia", "amman", "jordan",
    # Asia
    "bangalore", "india", "mumbai", "delhi", "hyderabad", "pune", "chennai",
    "singapore", "tokyo", "japan", "osaka", "beijing", "shanghai", "china",
    "hong kong", "seoul", "south korea", "taipei", "taiwan",
    "bangkok", "thailand", "kuala lumpur", "malaysia", "jakarta", "indonesia",
    # Australia / NZ
    "sydney", "australia", "melbourne", "brisbane", "auckland", "new zealand",
    # Americas (non-US)
    "toronto", "canada", "vancouver", "montreal", "ottawa", "calgary",
    "mexico city", "mexico", "brazil", "são paulo", "buenos aires", "argentina",
    # Africa
    "nairobi", "kenya", "lagos", "nigeria", "cape town", "south africa",
}


def is_us_or_remote(location: str) -> bool:
    """
    Returns True if the job location is in the US or is truly remote (no country specified).
    Empty / blank locations are treated as potentially remote → allowed.
    International 'remote' roles (e.g. 'China - Remote') are blocked.
    """
    if not location or location.strip() == "":
        return True  # Be inclusive — don't reject ambiguous locations

    loc = location.lower().strip()

    # Check US signals first
    if any(signal in loc for signal in US_SIGNALS):
        # Even if US, if it also contains an International signal, block it
        if any(signal in loc for signal in INTERNATIONAL_SIGNALS):
            return False
        return True

    # Check international signals
    if any(signal in loc for signal in INTERNATIONAL_SIGNALS):
        return False

    # Ambiguous (no strong signal either way) — allow it
    return True


def clean_location(location: str) -> str:
    """Normalize location string for display."""
    if not location or location.strip() == "":
        return "Remote / United States"
    return location.strip()
