from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable


def _hash_key(key: str) -> int:
    # Use sha256 for stability across Python versions.
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest, 16)


@dataclass(frozen=True)
class ConsistentHashRing:
    nodes: tuple[str, ...]
    virtual_nodes_per_node: int = 100

    def __post_init__(self) -> None:
        if not self.nodes:
            raise ValueError("ConsistentHashRing requires at least one node")
        if self.virtual_nodes_per_node <= 0:
            raise ValueError("virtual_nodes_per_node must be > 0")

    def _build_ring(self) -> list[tuple[int, str]]:
        ring: list[tuple[int, str]] = []
        # Expand each node into virtual nodes for smoother key distribution.
        for node in self.nodes:
            for v in range(self.virtual_nodes_per_node):
                ring.append((_hash_key(f"{node}#{v}"), node))
        ring.sort(key=lambda x: x[0])
        return ring

    def get_owner(self, key: str) -> str:
        ring = self._build_ring()
        h = _hash_key(key)
        for ring_hash, node in ring:
            if h <= ring_hash:
                return node
        # Wrap around.
        return ring[0][1]

    @classmethod
    def from_nodes(
        cls, nodes: Iterable[str], *, virtual_nodes_per_node: int = 100
    ) -> "ConsistentHashRing":
        node_tuple = tuple(nodes)
        return cls(nodes=node_tuple, virtual_nodes_per_node=virtual_nodes_per_node)

