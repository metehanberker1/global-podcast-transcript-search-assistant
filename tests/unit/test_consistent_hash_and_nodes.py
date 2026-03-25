from __future__ import annotations

import pytest

from podcast_search.sharding.consistent_hash import ConsistentHashRing
from podcast_search.sharding.node_registry import NodeRegistry


def test_consistent_hash_deterministic_mapping() -> None:
    # The same key should always resolve to the same owner for a fixed ring.
    ring = ConsistentHashRing.from_nodes(["n1", "n2", "n3"], virtual_nodes_per_node=10)

    feed_id = "22543618f282e8f41f598859"
    o1 = ring.get_owner(feed_id)
    o2 = ring.get_owner(feed_id)

    assert o1 == o2
    assert o1 in {"n1", "n2", "n3"}


def test_consistent_hash_changes_when_nodes_change() -> None:
    # Owner selection can change when cluster membership changes.
    ring_a = ConsistentHashRing.from_nodes(["n1", "n2", "n3"], virtual_nodes_per_node=10)
    ring_b = ConsistentHashRing.from_nodes(["n1", "n2", "n4"], virtual_nodes_per_node=10)
    feed_id = "some_feed_id"

    o_a = ring_a.get_owner(feed_id)
    o_b = ring_b.get_owner(feed_id)

    assert o_a in {"n1", "n2", "n3"}
    assert o_b in {"n1", "n2", "n4"}


def test_node_registry_requires_non_empty_nodes() -> None:
    # Registry should reject empty node sets.
    with pytest.raises(ValueError):
        _ = NodeRegistry(nodes=[])


def test_node_registry_gets_nodes() -> None:
    # Registry should expose configured nodes and resolve known node info.
    reg = NodeRegistry(nodes=["n1", "n2"])
    assert reg.nodes == ("n1", "n2")
    info = reg.get("n1")
    assert info.node_id == "n1"


def test_node_registry_get_unknown_node_raises() -> None:
    # Unknown node lookups should fail fast.
    reg = NodeRegistry(nodes=["n1"])
    with pytest.raises(KeyError):
        _ = reg.get("missing")

