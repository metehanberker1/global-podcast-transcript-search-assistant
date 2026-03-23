from __future__ import annotations

from pathlib import Path


def test_streamlit_ui_widgets_are_present() -> None:
    # Non-invasive smoke test:
    # We do not execute Streamlit; we only ensure the UI contract stays intact.
    repo_root = Path(__file__).resolve().parent.parent.parent
    app_path = repo_root / "streamlit_app.py"
    assert app_path.exists()

    text = app_path.read_text(encoding="utf-8")

    # Page radio options / labels
    assert '"Ingest feed"' in text or "Ingest feed" in text
    assert '"Search"' in text or "Search" in text

    # Ingest controls
    assert "RSS feed URL" in text
    assert "Ingest" in text

    # Search controls
    assert "Query" in text
    assert "Search" in text

