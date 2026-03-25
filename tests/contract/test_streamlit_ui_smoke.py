from __future__ import annotations

from pathlib import Path


def test_streamlit_ui_widgets_are_present() -> None:
    # Lightweight UI contract smoke test based on source text.
    repo_root = Path(__file__).resolve().parent.parent.parent
    app_path = repo_root / "streamlit_app.py"
    assert app_path.exists()

    text = app_path.read_text(encoding="utf-8")

    # Core navigation labels
    assert '"Ingest feed"' in text or "Ingest feed" in text
    assert '"Search"' in text or "Search" in text

    # Ingest controls
    assert "RSS feed URL" in text
    assert "Ingest" in text

    # Search controls
    assert "Query" in text
    assert "Search" in text

