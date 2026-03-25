from __future__ import annotations

from podcast_search.sharding.router import Router


def test_router_selects_owner_deterministically() -> None:
    # Router ownership should be stable for the same feed id.
    router = Router(nodes=["w1", "w2", "w3"], virtual_nodes_per_node=20, local_node_id="w1")

    feed_id = "22543618f282e8f41f598859"
    o1 = router.get_owner(feed_id)
    o2 = router.get_owner(feed_id)

    assert o1 == o2
    assert o1 in {"w1", "w2", "w3"}


def test_router_dispatch_calls_owner_callback() -> None:
    # Dispatch should invoke owner callback when present, otherwise local fallback.
    calls: dict[str, int] = {"owner_cb": 0, "fallback_cb": 0}

    def owner_cb(*, feed_id: str, owner: str, **kwargs):
        calls["owner_cb"] += 1
        return f"owner:{owner}"

    def fallback_cb(*, feed_id: str, owner: str, **kwargs):
        calls["fallback_cb"] += 1
        return f"fallback:{owner}"

    router = Router(
        nodes=["w1", "w2"],
        virtual_nodes_per_node=10,
        local_node_id="w1",
        node_callbacks={"w2": owner_cb, "w1": fallback_cb},
    )

    feed_id = "feed_for_dispatch"
    owner = router.get_owner(feed_id)
    res = router.route_action(feed_id=feed_id, action=lambda: "local")

    assert res.owner == owner
    if owner == "w2":
        assert calls["owner_cb"] == 1
        assert res.result.startswith("owner:")
    else:
        assert calls["fallback_cb"] == 1
        assert res.result.startswith("fallback:")

