from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

import streamlit as st

# Streamlit Cloud runs this file from repo root without PYTHONPATH configured.
# Ensure `src/` is importable so `from app...` works both locally and in the cloud.
_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from app.config import settings  # noqa: E402
from app.db import connect, get_db_config  # noqa: E402
from app.http import Http  # noqa: E402
from app.migrations.runner import apply_all  # noqa: E402
from podcast_search.ingest.service import ingest_feed  # noqa: E402
from podcast_search.search.service import search  # noqa: E402


def _init_db() -> None:
    cfg = get_db_config(settings.database_url)
    conn = connect(cfg)
    try:
        migrations_dir = Path(__file__).resolve().parent / "src" / "app" / "migrations"
        apply_all(conn, migrations_dir=migrations_dir)
    finally:
        conn.close()


@contextmanager
def _db_conn():
    cfg = get_db_config(settings.database_url)
    conn = connect(cfg)
    try:
        yield conn
    finally:
        conn.close()


def _page_css() -> None:
    st.markdown(
        """
<style>
  .block-container { max-width: 1100px; padding-top: 1.25rem; }
  code { font-size: 0.92em; }
</style>
""",
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="Podcast Search Assistant",
        page_icon="🎙️",
        layout="wide",
    )
    _page_css()

    st.title("Podcast Search Assistant")
    st.caption("A transcript search helper for podcast RSS feeds.")

    _init_db()

    page = st.radio(
        "Page",
        options=["Ingest feed", "Search"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if page == "Ingest feed":
        st.subheader("Ingest feed")
        st.write(
            "Paste a podcast RSS feed URL, then ingest episodes into the local DB "
            "for search."
        )

        feed_url = st.text_input(
            "RSS feed URL",
            value="https://feeds.captivate.fm/the-news-agents/",
            placeholder="https://feeds.captivate.fm/the-news-agents/",
        )

        if st.button("Ingest", type="primary"):
            out = st.empty()
            with out.container():
                with st.spinner("Fetching feed + indexing…"):
                    http = Http()
                    try:
                        feed_xml = http.get_text(feed_url)
                        with _db_conn() as conn:
                            res = ingest_feed(
                                conn,
                                feed_url=feed_url.strip(),
                                feed_xml=feed_xml,
                                http=http,
                                episode_limit=int(settings.ingest_episode_limit),
                            )
                    except Exception as exc:
                        st.error(f"Ingest failed: {exc}")
                    else:
                        with st.container(border=True):
                            st.success("Ingest complete.")
                            st.write(
                                f"**Episodes ingested**: {res.episode_count}\n\n"
                                f"**Chunks indexed**: {res.chunk_count}"
                            )
                    finally:
                        http.close()

    if page == "Search":
        st.subheader("Search")
        st.write(
            "Enter a natural-language query and get back the most relevant "
            "excerpted matches."
        )

        q = st.text_input("Query", value="Where was Trump mentioned?")

        if st.button("Search", type="primary"):
            out = st.empty()
            with out.container():
                with st.spinner("Searching…"):
                    with _db_conn() as conn:
                        try:
                            hits = search(conn, query=q, k=5)
                        except Exception as exc:
                            st.error(f"Search failed: {exc}")
                            hits = []

                if not hits:
                    with st.container(border=True):
                        st.info("No results.")
                else:
                    with st.container(border=True):
                        st.success(f"Found {len(hits)} result(s).")

                    for h in hits:
                        with st.container(border=True):
                            st.markdown(f"**{h.episode_title}**")
                            st.code(h.excerpt.strip(), language=None)
                            st.caption(f"score={h.score:.2f}")


if __name__ == "__main__":
    main()
