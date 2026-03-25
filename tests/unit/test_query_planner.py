from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.config import settings
from podcast_search.search.query_planner import plan_query_text


def test_plan_query_text_fallback_when_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # Without credentials, planner should return the original query unchanged.
    monkeypatch.setattr(settings, "openai_api_key", "")
    assert plan_query_text("hello") == "hello"


def test_plan_query_text_parses_json(monkeypatch: pytest.MonkeyPatch) -> None:
    # Planner should extract `query_text` from model JSON output.
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    class FakeChat:
        class completions:
            @staticmethod
            def create(model: str, messages: list[dict[str, str]], temperature: float, response_format: Any) -> Any:
                import json

                payload = {"query_text": "structured query text", "filters": []}
                content = f"prefix\n{json.dumps(payload)}\nsuffix"
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    class FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.chat = FakeChat()

    import openai as openai_mod

    monkeypatch.setattr(openai_mod, "OpenAI", FakeOpenAI)
    assert plan_query_text("find trump mentions") == "structured query text"


def test_plan_query_text_falls_back_when_query_text_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    # Missing `query_text` should trigger safe fallback to user query.
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    class FakeChat:
        class completions:
            @staticmethod
            def create(model: str, messages: list[dict[str, str]], temperature: float, response_format: Any) -> Any:
                import json

                payload = {"filters": []}
                content = f"prefix\n{json.dumps(payload)}\nsuffix"
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    class FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            self.chat = FakeChat()

    import openai as openai_mod

    monkeypatch.setattr(openai_mod, "OpenAI", FakeOpenAI)
    assert plan_query_text("raw query should win") == "raw query should win"


def test_plan_query_text_returns_user_query_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    # Any planner exception should degrade gracefully to raw query text.
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    class FakeOpenAI:
        def __init__(self, api_key: str | None = None) -> None:
            raise RuntimeError("boom")

    import openai as openai_mod

    monkeypatch.setattr(openai_mod, "OpenAI", FakeOpenAI)
    assert plan_query_text("query") == "query"

