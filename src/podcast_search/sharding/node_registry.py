from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class NodeInfo:
    node_id: str


class NodeRegistry:
    """MVP node registry.

    In later phases this can include health checks, dynamic membership, and
    API endpoints. For now it is deterministic and in-memory.
    """

    def __init__(self, nodes: Iterable[str]) -> None:
        self._nodes = tuple(nodes)
        if not self._nodes:
            raise ValueError("NodeRegistry requires at least one node")

    @property
    def nodes(self) -> tuple[str, ...]:
        return self._nodes

    def get(self, node_id: str) -> NodeInfo:
        if node_id not in self._nodes:
            raise KeyError(node_id)
        return NodeInfo(node_id=node_id)

