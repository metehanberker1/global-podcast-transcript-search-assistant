from __future__ import annotations

from pathlib import Path


def apply_all(conn, migrations_dir: Path) -> None:
    """Deterministic MVP no-op.

    The goal for Phase 1 is wiring only. Later phases can add schema/migrations.
    """

    _ = (conn, migrations_dir)
    return None

