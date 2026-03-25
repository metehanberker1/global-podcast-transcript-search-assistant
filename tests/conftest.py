from __future__ import annotations

import sys
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _ensure_src_on_path() -> None:
    # Keep local imports stable regardless of how pytest is invoked.
    repo_root = Path(__file__).resolve().parent.parent
    src_dir = repo_root / "src"
    tests_dir = repo_root / "tests"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    if str(tests_dir) not in sys.path:
        sys.path.insert(0, str(tests_dir))

