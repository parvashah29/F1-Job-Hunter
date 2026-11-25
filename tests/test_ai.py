import requests

import ai_analyzer


class Resp:
    def __init__(self, text): self._t = text
    def raise_for_status(self): pass
    def json(self): return {"response": self._t}


def test_llm_disabled_uses_rules_only(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no call")))
    assert ai_analyzer.decide("Python role", {"enabled": False})[0] == "YES"


def test_llm_can_veto(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: Resp("NO"))
    assert ai_analyzer.decide("Python role", {"enabled": True}) == ("NO", "llm:no")


def test_llm_unreachable_falls_back_to_rules(monkeypatch):
    def boom(*a, **k): raise requests.exceptions.ConnectionError()
    monkeypatch.setattr(requests, "post", boom)
    assert ai_analyzer.decide("Python role", {"enabled": True})[0] == "YES"


def test_rules_no_is_final_without_llm_call(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no call")))
    assert ai_analyzer.decide("US citizens only", {"enabled": True})[0] == "NO"


def test_ollama_health_false_when_down(monkeypatch):
    def boom(*a, **k): raise requests.exceptions.ConnectionError()
    monkeypatch.setattr(requests, "get", boom)
    assert ai_analyzer.is_ollama_running() is False
