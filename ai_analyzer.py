"""
ai_analyzer.py — Ollama LLM wrapper for F-1 Job Hunter Agent
Sends job descriptions to a local Ollama model and returns YES/NO on whether
an F-1 OPT new grad can apply. Optional: rules in eligibility.py always run first.
"""

import requests
import logging
import time

import eligibility

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """You are an expert US immigration-aware technical recruiter reviewing a job description on behalf of a new graduate on an F-1 visa (OPT, 0 years of full-time experience).

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

DEFAULT_OLLAMA_URL = "http://localhost:11434"


def check_yoe_in_description(description: str) -> bool:
    """True if the description explicitly requires 3+ years of experience."""
    return eligibility.check_yoe(description)


def analyze_job(description: str, model: str = "llama3.2", timeout: int = 45,
                base_url: str = DEFAULT_OLLAMA_URL):
    """
    Ask the local Ollama model. Returns 'YES', 'NO', or None when the model could not
    be reached / gave an unusable answer (callers treat None as 'no opinion').
    """
    truncated = (description or "")[:4000].strip()
    if not truncated:
        return None
    payload = {
        "model": model,
        "prompt": PROMPT_TEMPLATE.format(description=truncated),
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 10},
    }
    for attempt in range(2):
        try:
            response = requests.post(f"{base_url}/api/generate", json=payload, timeout=timeout)
            response.raise_for_status()
            raw = response.json().get("response", "").strip().upper()
            if "NO" in raw and "YES" not in raw:
                return "NO"
            if "YES" in raw:
                return "YES"
            logger.warning(f"Ambiguous LLM response: {raw!r} - ignoring")
            return None
        except requests.exceptions.Timeout:
            logger.warning(f"Ollama timeout on attempt {attempt + 1}")
            if attempt == 0:
                time.sleep(2)
        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Ollama (is `ollama serve` running?) - using rules only")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling Ollama: {type(e).__name__}")
            return None
    return None


def is_ollama_running(base_url: str = DEFAULT_OLLAMA_URL) -> bool:
    try:
        return requests.get(f"{base_url}/api/tags", timeout=5).status_code == 200
    except Exception:
        return False


def decide(description: str, ai_cfg: dict = None, use_llm: bool = True) -> tuple:
    """
    Final eligibility decision -> (verdict, reason).
    Rules run first. If they say YES and the LLM is enabled+reachable, the LLM may
    still veto (NO). With the LLM off or unreachable we fall back to rules only.
    """
    verdict, reason = eligibility.evaluate(description)
    ai_cfg = ai_cfg or {}
    if verdict == "NO" or not use_llm or not ai_cfg.get("enabled", False):
        return verdict, reason
    llm = analyze_job(
        description,
        model=ai_cfg.get("model", "llama3.2"),
        timeout=ai_cfg.get("timeout_seconds", 45),
        base_url=ai_cfg.get("ollama_url", DEFAULT_OLLAMA_URL),
    )
    if llm == "NO":
        return "NO", "llm:no"
    return "YES", reason + ("+llm:yes" if llm == "YES" else "")
