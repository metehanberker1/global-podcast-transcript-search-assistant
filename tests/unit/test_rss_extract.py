from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from podcast_search.ingest.rss_extract import discover_related_feed_urls, extract_episode_items


def test_rss_extract_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    # Parser should capture rich text fields and fall back to title when needed.
    class FakeEntry(dict):
        pass

    def fake_parse(_xml: str) -> Any:
        entries = [
            FakeEntry(
                {
                    "title": "T1",
                    "published": "2020-01-01",
                    "link": "http://ep1",
                    "guid": "g1",
                    "summary": "sum1",
                    "description": "desc1",
                    "content": [{"value": "encoded1"}],
                }
            ),
            FakeEntry({"title": "T2", "link": "http://ep2", "guid": "g2"}),
        ]
        return SimpleNamespace(entries=entries)

    import feedparser as feedparser_mod

    monkeypatch.setattr(feedparser_mod, "parse", fake_parse)
    items = extract_episode_items("<rss/>", episode_limit=10)
    assert len(items) == 2
    assert items[0].episode_id == "g1"
    assert "sum1" in items[0].text
    assert "desc1" in items[0].text
    assert "encoded1" in items[0].text
    assert items[0].published_at == "2020-01-01"
    assert items[1].episode_id == "g2"
    assert items[1].text.strip() == "T2"


def test_discover_related_feed_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    # Related feed URL discovery should support both dict and attribute link forms.
    import feedparser as feedparser_mod

    def fake_parse(_xml: str) -> Any:
        return SimpleNamespace(
            feed=SimpleNamespace(
                links=[
                    {"href": "http://alt1"},
                    SimpleNamespace(href="http://alt2"),
                    {"nope": "x"},
                ]
            )
        )

    monkeypatch.setattr(feedparser_mod, "parse", fake_parse)
    urls = discover_related_feed_urls("<rss/>")
    assert urls == ["http://alt1", "http://alt2"]
