import pytest

import eligibility
import location_filter as lf
import role_matcher as rm


@pytest.mark.parametrize("loc,expected", [
    ("Remote - US", True), ("Remote, United States", True), ("Hybrid - New York", True),
    ("San Francisco, CA", True), ("Austin, TX", True), ("Portland, OR", True),
    ("Santa Fe, New Mexico", True), ("Washington, DC", True), ("Remote", True), ("", True),
    ("Toronto | New York, NY", True), ("US/Canada Remote", True),
    ("Remote - Canada", False), ("London, UK", False), ("Berlin, DE", False),
    ("Bengaluru, India", False), ("Remote, Mexico", False), ("Kuwait City, Kuwait", False),
])
def test_location(loc, expected):
    assert lf.is_us_or_remote(loc) is expected


@pytest.mark.parametrize("text", [
    "We are unable to provide visa sponsorship.",
    "No sponsorship available for this role.",
    "This position does not offer visa sponsorship.",
    "We will not sponsor employment visas.",
    "Candidates must be authorized to work without sponsorship now or in the future.",
    "US citizens only.", "Must be a U.S. citizen.", "U.S. citizenship is required.",
    "Requires an active TS/SCI clearance.", "Active Top Secret clearance required.",
    "Ability to obtain a security clearance.", "Polygraph required.",
    "5+ years of experience in data engineering.", "Minimum 4 years of Python.",
    "3-5 years of professional experience.",
])
def test_eligibility_rejects(text):
    assert eligibility.evaluate(text)[0] == "NO"


@pytest.mark.parametrize("text", [
    "", "We sponsor visas for eligible candidates.", "0-2 years of experience.",
    "No security clearance required.", "1-3 years of experience with SQL.",
    "Experience with Python. Equal opportunity employer.",
])
def test_eligibility_accepts(text):
    assert eligibility.evaluate(text)[0] == "YES"


def test_eligibility_reason_is_explainable():
    verdict, reason = eligibility.evaluate("Requires TS/SCI clearance")
    assert verdict == "NO" and reason.startswith("rules:clearance")


@pytest.mark.parametrize("title,tier", [
    ("Data Scientist, Growth", "1"), ("Software Engineer, New Grad", "1"),
    ("Analytics Engineer", "2"), ("Python Developer", "3"),
    ("Senior Data Scientist", None), ("Staff Software Engineer", None),
    ("Software Engineer II", None), ("Data Engineering Manager", None),
    ("Machine Learning Engineer Intern", None), ("Staffing Coordinator", None),
    ("Maintenance Technician", None), ("Office Manager", None),
])
def test_role_tiers(title, tier):
    assert rm.classify_tier(title) == tier


def test_role_matcher_uses_config():
    try:
        rm.configure({"roles": {"tier1": ["quantum chef"], "exclude_keywords": ["sous"]}})
        assert rm.classify_tier("Quantum Chef") == "1"
        assert rm.classify_tier("Sous Quantum Chef") is None
        assert rm.classify_tier("Data Scientist") is None
    finally:
        rm._build()
