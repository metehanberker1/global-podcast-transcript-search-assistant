from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import chromadb
import pytest

from app.config import settings
from podcast_search.ingest.service import ingest_feed
from podcast_search.indexing.index_handle_cache import clear_cache
from podcast_search.ingest import service as ingest_service_mod
from podcast_search.registry.normalize_url import feed_id_from_normalized_url, normalize_url
from podcast_search.search import service as search_service_mod
from podcast_search.search.service import search
from podcast_search.sharding.router import Router
from fixtures.factories import setup_isolated_storage


def _fake_embed_texts(texts: list[str], *args: Any, **kwargs: Any) -> list[list[float]]:
    # Deterministic vectors keep similarity behavior stable across runs.
    out: list[list[float]] = []
    for t in texts:
        h = sum(ord(c) for c in (t or "")) % 1000
        out.append([float(h), float(h + 1), float(h + 2), float(h + 3), float(h + 4)])
    return out


def _fake_plan_query_text(q: str) -> str:
    return q


def _rss_with_title(title: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{title}</title>
    <item><title>{title}</title><link>http://example.com/{title}</link></item>
  </channel>
</rss>"""


def test_distributed_storage_isolation_and_load_simulation(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    # Use a two-node shard layout.
    monkeypatch.setattr(settings, "shard_nodes", "nodeA,nodeB")
    monkeypatch.setattr(settings, "local_node_id", "nodeA")
    monkeypatch.setattr(settings, "consistent_hash_virtual_nodes", 25)

    setup_isolated_storage(monkeypatch, tmp_path)

    # Keep test deterministic by stubbing external model calls.
    monkeypatch.setattr(ingest_service_mod, "embed_texts", _fake_embed_texts)
    monkeypatch.setattr(search_service_mod, "embed_texts", _fake_embed_texts)
    monkeypatch.setattr(search_service_mod, "plan_query_text", _fake_plan_query_text)
    monkeypatch.setattr(ingest_service_mod, "discover_related_feed_urls", lambda _xml: [])

    router = Router(nodes=["nodeA", "nodeB"], virtual_nodes_per_node=settings.consistent_hash_virtual_nodes)

    # Pick two feeds that map to different shard owners.
    feed_url_a = "http://example.com/feedA"
    feed_id_a = feed_id_from_normalized_url(normalize_url(feed_url_a))
    owner_a = router.get_owner(feed_id_a)

    feed_url_b = None
    feed_id_b = None
    owner_b = None
    for i in range(1, 200):
        candidate = f"http://example.com/feedB{i}"
        cid = feed_id_from_normalized_url(normalize_url(candidate))
        co = router.get_owner(cid)
        if co != owner_a:
            feed_url_b = candidate
            feed_id_b = cid
            owner_b = co
            break

    assert feed_url_b is not None and feed_id_b is not None and owner_b is not None

    rss_a = _rss_with_title("EpisodeA1")
    rss_b = _rss_with_title("EpisodeB1")

    ingest_feed(conn=None, feed_url=feed_url_a, feed_xml=rss_a, http=None, episode_limit=10)
    ingest_feed(conn=None, feed_url=feed_url_b, feed_xml=rss_b, http=None, episode_limit=10)

    # Collections should exist only on their owning shard storage paths.
    base = settings.chroma_persist_dir
    persist_a = f"{base}/{owner_a}"
    persist_b = f"{base}/{owner_b}"

    client_a = chromadb.PersistentClient(path=persist_a)
    client_b = chromadb.PersistentClient(path=persist_b)

    col_a = f"feed_{feed_id_a}"
    col_b = f"feed_{feed_id_b}"

    names_a = {c.name for c in client_a.list_collections()}
    names_b = {c.name for c in client_b.list_collections()}

    assert col_a in names_a
    assert col_a not in names_b
    assert col_b in names_b
    assert col_b not in names_a

    # Search should be scoped to the most recently ingested feed.
    clear_cache()
    hits = search(conn=None, query="EpisodeB1", k=5)
    assert hits
    assert all(h.episode_title == "EpisodeB1" for h in hits)

    # Repeated search requests should not mutate stored document counts.
    collection_b = client_b.get_collection(col_b)
    before = collection_b.count()

    def _do_search() -> list[str]:
        hs = search(conn=None, query="EpisodeB1", k=5)
        return [h.episode_title for h in hs]

    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(lambda _: _do_search(), range(10)))

    assert results  # non-empty batch
    assert all(titles and all(t == "EpisodeB1" for t in titles) for titles in results)

    after = collection_b.count()
    assert after == before


def test_non_owner_shard_is_never_touched_in_search(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "shard_nodes", "nodeA,nodeB")
    monkeypatch.setattr(settings, "local_node_id", "nodeA")
    monkeypatch.setattr(settings, "consistent_hash_virtual_nodes", 25)
    setup_isolated_storage(monkeypatch, tmp_path)

    monkeypatch.setattr(ingest_service_mod, "embed_texts", _fake_embed_texts)
    monkeypatch.setattr(ingest_service_mod, "discover_related_feed_urls", lambda _xml: [])
    monkeypatch.setattr(search_service_mod, "embed_texts", _fake_embed_texts)
    monkeypatch.setattr(search_service_mod, "plan_query_text", _fake_plan_query_text)

    router = Router(nodes=["nodeA", "nodeB"], virtual_nodes_per_node=settings.consistent_hash_virtual_nodes)

    feed_url_b = None
    feed_id_b = None
    for i in range(1, 300):
        candidate = f"http://example.com/feedB{i}"
        cid = feed_id_from_normalized_url(normalize_url(candidate))
        if router.get_owner(cid) == "nodeB":
            feed_url_b = candidate
            feed_id_b = cid
            break
    assert feed_url_b is not None and feed_id_b is not None

    ingest_feed(conn=None, feed_url=feed_url_b, feed_xml=_rss_with_title("EpisodeB1"), http=None, episode_limit=10)

    base = settings.chroma_persist_dir
    client_a = chromadb.PersistentClient(path=f"{base}/nodeA")
    client_b = chromadb.PersistentClient(path=f"{base}/nodeB")
    col_b = f"feed_{feed_id_b}"

    names_a_initial = {c.name for c in client_a.list_collections()}
    assert col_b not in names_a_initial

    clear_cache()
    before_b_count = client_b.get_collection(col_b).count()

    def _do_search() -> list[str]:
        hits = search(conn=None, query="EpisodeB1", k=5)
        return [h.episode_title for h in hits]

    with ThreadPoolExecutor(max_workers=4) as ex:
        all_titles = list(ex.map(lambda _: _do_search(), range(12)))

    assert all(all(t == "EpisodeB1" for t in titles) for titles in all_titles if titles)
    after_b_count = client_b.get_collection(col_b).count()
    assert after_b_count == before_b_count
    assert {c.name for c in client_a.list_collections()} == names_a_initial


def test_owner_callback_invoked_only_for_owner(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "shard_nodes", "nodeA,nodeB")
    monkeypatch.setattr(settings, "local_node_id", "nodeA")
    monkeypatch.setattr(settings, "consistent_hash_virtual_nodes", 25)
    setup_isolated_storage(monkeypatch, tmp_path)

    monkeypatch.setattr(ingest_service_mod, "embed_texts", _fake_embed_texts)
    monkeypatch.setattr(search_service_mod, "embed_texts", _fake_embed_texts)
    monkeypatch.setattr(search_service_mod, "plan_query_text", _fake_plan_query_text)
    monkeypatch.setattr(ingest_service_mod, "discover_related_feed_urls", lambda _xml: [])

    calls: dict[str, int] = {"nodeA": 0, "nodeB": 0}

    def node_cb(*, feed_id: str, owner: str, action, **kwargs: Any):
        calls[owner] += 1
        return action()

    router_instance = Router(
        nodes=["nodeA", "nodeB"],
        virtual_nodes_per_node=settings.consistent_hash_virtual_nodes,
        local_node_id="nodeA",
        node_callbacks={"nodeA": node_cb, "nodeB": node_cb},
    )
    monkeypatch.setattr(ingest_service_mod, "Router", lambda: router_instance)
    monkeypatch.setattr(search_service_mod, "Router", lambda: router_instance)

    feed_url_b = None
    for i in range(1, 300):
        candidate = f"http://example.com/feedB{i}"
        fid = feed_id_from_normalized_url(normalize_url(candidate))
        if router_instance.get_owner(fid) == "nodeB":
            feed_url_b = candidate
            break
    assert feed_url_b

    ingest_feed(conn=None, feed_url=feed_url_b, feed_xml=_rss_with_title("EpisodeB1"), http=None, episode_limit=10)
    clear_results = search(conn=None, query="EpisodeB1", k=5)
    assert clear_results
    assert calls["nodeB"] >= 1
    assert calls["nodeA"] == 0

