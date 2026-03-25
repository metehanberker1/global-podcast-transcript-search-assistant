from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.config import settings
from podcast_search.sharding.consistent_hash import ConsistentHashRing


@dataclass(frozen=True)
class RouteResult:
    owner: str
    result: Any


class Router:
    """Deterministic router for feed-scoped sharding.

    Ownership is computed via consistent hashing, and the selected action is
    dispatched via configured callbacks (or locally by default).
    """

    def __init__(
        self,
        *,
        nodes: list[str] | None = None,
        virtual_nodes_per_node: int | None = None,
        local_node_id: str | None = None,
        node_callbacks: dict[str, Callable[..., Any]] | None = None,
    ) -> None:
        raw_nodes = nodes if nodes is not None else [n.strip() for n in settings.shard_nodes.split(",") if n.strip()]
        self._nodes = raw_nodes or [settings.local_node_id]
        v = virtual_nodes_per_node if virtual_nodes_per_node is not None else settings.consistent_hash_virtual_nodes
        self._ring = ConsistentHashRing.from_nodes(self._nodes, virtual_nodes_per_node=v)
        self._local_node_id = local_node_id or settings.local_node_id
        self._node_callbacks = node_callbacks or {}

    def get_owner(self, feed_id: str) -> str:
        return self._ring.get_owner(feed_id)

    def route_action(self, *, feed_id: str, action: Callable[[], Any], **kwargs: Any) -> RouteResult:
        owner = self.get_owner(feed_id)

        cb = self._node_callbacks.get(owner)
        if cb is not None:
            # Provide `action` so callback implementations can execute it directly.
            return RouteResult(
                owner=owner,
                result=cb(feed_id=feed_id, owner=owner, action=action, **kwargs),
            )

        # Fallback to a callback registered for the local node.
        local_cb = self._node_callbacks.get(self._local_node_id)
        if local_cb is not None:
            return RouteResult(
                owner=owner,
                result=local_cb(feed_id=feed_id, owner=owner, action=action, **kwargs),
            )

        return RouteResult(owner=owner, result=action())

