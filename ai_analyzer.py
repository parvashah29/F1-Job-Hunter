"""
ai_analyzer.py — Ollama LLM wrapper for F-1 Job Hunter Agent
Sends job descriptions to a local Ollama model and returns YES/NO on whether
an F-1 OPT new grad (graduating May 2027) can apply.
"""

import requests
import logging
import re
import time

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """You are an expert US immigration-aware technical recruiter reviewing a job description on behalf of a new graduate on an F-1 visa (OPT, graduating May 2027, 0 years of full-time experience).

Your task: Return "YES" only if BOTH conditions below are true. Otherwise return "NO".

CONDITION 1 — VISA ELIGIBILITY:
✅ Return YES if the posting does NOT mention citizenship restrictions, OR explicitly offers visa sponsorship.
❌ Return NO if the posting requires:
   - US Citizenship or Green Card / Permanent Residency
   - Security Clearance (Secret, TS, TS/SCI, etc.)
   - "No sponsorship" / "No C2C" / "No visa sponsorship"

CONDITION 2 — EXPERIENCE LEVEL:
✅ Return YES if the posting is entry-level, new grad, university hire, associate, or junior level (0-2 years YOE).
✅ Return YES if no experience requirement is mentioned (benefit of the doubt — new grads can apply).
❌ Return NO if the posting explicitly requires:
   - 3 or more years of experience (e.g., "3+ years", "5 years", "minimum 4 years")
   - Extensive industry experience clearly beyond what a new grad has
   - A PhD or postdoctoral requirement (unless it says "or equivalent")

IMPORTANT: If BOTH conditions are unclear or not mentioned, return YES (user will manually review).
Only return YES or NO — no explanation.

Job Description:
---
{description}
---

Answer (YES or NO only):"""

# Fast regex patterns that identify high-YOE requirements — used BEFORE calling Ollama
# If matched, we can skip the LLM entirely and return NO immediately
_YOE_PATTERNS = [
    # e.g. "3+ years", "5 years of experience", "10+ years"
    r'\b([3-9]|\d{2})\+?\s*(?:or more\s*)?years?\s+(?:of\s+)?(?:professional\s+)?(?:industry\s+)?(?:relevant\s+)?experience',
    # e.g. "minimum 4 years", "at least 5 years"
    r'(?:minimum|at least|min\.?)\s+([3-9]|\d{2})\s+years?',
    # e.g. "5-7 years experience", "7-10 years of data science experience"
    r'\b([3-9]|\d{2})\s*[-–]\s*\d+\s+years?(?:\s+of\s+\w+(?:\s+\w+)*)?\s+experience',
]
_YOE_RE = [re.compile(p, re.IGNORECASE) for p in _YOE_PATTERNS]

# Seniority phrases that appear in the body of a JD (not just the title)
_BODY_SENIORITY = re.compile(
    r'\b(senior|staff|principal|lead\s+engineer|lead\s+scientist|director|'
    r'manager|architect|distinguished|head\s+of)\b',
    re.IGNORECASE
)


def check_yoe_in_description(description: str) -> bool:
    """
    Fast pre-filter — returns True if the description explicitly requires 3+ years.
    If True, skip Ollama and return NO immediately.
    """
    text = description[:3000]
    return any(pattern.search(text) for pattern in _YOE_RE)



def analyze_job(description: str, model: str = "llama3.2", timeout: int = 45) -> str:
    """
    Send a job description to the local Ollama instance.
    Returns 'YES' or 'NO'. Defaults to 'YES' on error or ambiguity.
    Retries once on timeout.
    """
    truncated = description[:4000].strip()
    if not truncated:
        return "YES"  # No description to analyze — let user decide

    prompt = PROMPT_TEMPLATE.format(description=truncated)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,   # Deterministic — we want a strict YES/NO
            "num_predict": 10,    # We only need 1 token back
        }
    }

    for attempt in range(2):  # Try twice before defaulting to YES
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            raw = response.json().get("response", "").strip().upper()

            # Parse strictly — look for YES or NO anywhere in the response
            if "NO" in raw and "YES" not in raw:
                return "NO"
            elif "YES" in raw:
                return "YES"
            else:
                logger.warning(f"Ambiguous LLM response: '{raw}' — defaulting to YES")
                return "YES"

        except requests.exceptions.Timeout:
            logger.warning(f"Ollama timeout on attempt {attempt + 1}")
            if attempt == 0:
                time.sleep(2)
            continue
        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Ollama. Is it running? Try: ollama serve")
            return "YES"
        except Exception as e:
            logger.error(f"Unexpected error calling Ollama: {e}")
            return "YES"

    logger.warning("Both Ollama attempts timed out — defaulting to YES")
    return "YES"


def is_ollama_running() -> bool:
    """Quick health check — returns True if Ollama is reachable."""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        return r.status_code == 200
    except Exception:
        return False
