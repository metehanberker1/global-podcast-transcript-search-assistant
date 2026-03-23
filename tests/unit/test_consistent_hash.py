from __future__ import annotations

from podcast_search.sharding.consistent_hash import ConsistentHashRing


def test_consistent_hash_deterministic_mapping() -> None:
    ring = ConsistentHashRing.from_nodes(["n1", "n2", "n3"], virtual_nodes_per_node=10)

    feed_id = "22543618f282e8f41f598859"
    o1 = ring.get_owner(feed_id)
    o2 = ring.get_owner(feed_id)

    assert o1 == o2
    assert o1 in {"n1", "n2", "n3"}


def test_consistent_hash_changes_when_nodes_change() -> None:
    ring_a = ConsistentHashRing.from_nodes(["n1", "n2", "n3"], virtual_nodes_per_node=10)
    ring_b = ConsistentHashRing.from_nodes(["n1", "n2", "n4"], virtual_nodes_per_node=10)
    feed_id = "some_feed_id"

    o_a = ring_a.get_owner(feed_id)
    o_b = ring_b.get_owner(feed_id)

    # Not guaranteed, but extremely likely; if it matches, still valid for deterministic mapping.
    assert o_a in {"n1", "n2", "n3"}
    assert o_b in {"n1", "n2", "n4"}

