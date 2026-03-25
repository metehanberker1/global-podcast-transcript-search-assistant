from __future__ import annotations

from pathlib import Path


def apply_all(conn, migrations_dir: Path) -> None:
    """Migration hook placeholder.

    Kept as a stable call site so schema migrations can be introduced without
    changing startup wiring.
    """

    _ = (conn, migrations_dir)
    return None

