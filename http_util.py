"""http_util.py - shared polite HTTP session: identifying User-Agent, timeouts, retries with backoff."""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = (
    "F1-Job-Hunter/1.0 (personal job-search script; "
    "+https://github.com/parvashah29/F1-Job-Hunter)"
)
DEFAULT_TIMEOUT = 20


def make_session(retries: int = 3, backoff: float = 1.0) -> requests.Session:
    """Session that retries 429/5xx (honouring Retry-After) with exponential backoff."""
    session = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return session
