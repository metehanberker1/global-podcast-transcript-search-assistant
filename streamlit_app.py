from __future__ import annotations

import shutil
import socket
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

import httpx
import streamlit as st
import uvicorn

# Ensure `src/` is importable when running from repo root.
_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from app.config import settings
from app.db import connect, get_db_config
from app.migrations.runner import apply_all
from podcast_search.indexing.index_handle_cache import clear_cache
from podcast_search.registry.feed_registry import FeedRegistry


def _can_connect(host: str, port: int, timeout_s: float = 0.3) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout_s)
        return sock.connect_ex((host, port)) == 0


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _is_local_api_url(api_url: str) -> bool:
    parsed = urlparse(api_url)
    return parsed.hostname in {"127.0.0.1", "localhost"}


@st.cache_resource(show_spinner=False)
def _ensure_backend_api() -> tuple[str, str]:
    # Respect external API targets as-is.
    configured = settings.api_base_url.rstrip("/")
    if not _is_local_api_url(configured):
        return configured, "external API_BASE_URL"

    parsed = urlparse(configured)
    host = parsed.hostname or "127.0.0.1"
    port = int(parsed.port or 8000)

    # Reuse an already-running local API instance when available.
    if _can_connect(host, port):
        return f"http://{host}:{port}", "existing local API"

    # Otherwise start a local FastAPI server for this Streamlit session.
    from api.main import app as fastapi_app

    chosen_port = port if not _can_connect(host, port) else _find_free_port()
    config = uvicorn.Config(
        app=fastapi_app,
        host="127.0.0.1",
        port=chosen_port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.time() + 12.0
    api_base = f"http://127.0.0.1:{chosen_port}"
    while time.time() < deadline:
        try:
            with httpx.Client(timeout=1.0) as client:
                resp = client.get(f"{api_base}/api/metrics")
            if resp.status_code == 200:
                return api_base, "auto-started local API"
        except Exception:
            time.sleep(0.25)
            continue
        time.sleep(0.25)

    raise RuntimeError("Auto-started API server did not become ready in time.")


def _init_db() -> None:
    cfg = get_db_config(settings.database_url)
    conn = connect(cfg)
    try:
        migrations_dir = Path(__file__).resolve().parent / "src" / "app" / "migrations"
        apply_all(conn, migrations_dir=migrations_dir)
    finally:
        conn.close()


def _clear_persisted_data() -> tuple[int, str]:
    registry = FeedRegistry()
    entries = registry.load()
    urls: list[str] = []
    for entry in entries.values():
        if entry.original_url:
            urls.append(entry.original_url)
        if entry.normalized_url:
            urls.append(entry.normalized_url)

    # De-duplicate while preserving first-seen order.
    deduped_urls = list(dict.fromkeys(urls))
    deleted_text = "\n".join(deduped_urls)

    clear_cache()
    shutil.rmtree(Path(settings.chroma_persist_dir), ignore_errors=True)
    Path(settings.registry_path).unlink(missing_ok=True)
    return len(deduped_urls), deleted_text


@contextmanager
def _db_conn():
    # Maintained as a shared DB context helper.
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
  .stApp {
    background: radial-gradient(circle at top left, #f5f7ff 0%, #f7f8fc 30%, #f3f5fa 100%);
  }
  [data-testid="stHeader"] {
    background: linear-gradient(180deg, rgba(245, 247, 255, 0.94) 0%, rgba(245, 247, 255, 0.72) 100%) !important;
    backdrop-filter: blur(6px);
  }
  [data-testid="stToolbar"] {
    right: 0.65rem;
  }
  [data-testid="stDecoration"] {
    background: transparent !important;
  }
  .block-container {
    max-width: 1100px;
    padding-top: 1.4rem;
    padding-bottom: 2rem;
  }
  h1, h2, h3 {
    letter-spacing: -0.01em;
  }
  code { font-size: 0.92em; }
  [data-testid="stSidebar"] {
    background: linear-gradient(180deg, #eef2ff 0%, #f5f7ff 100%);
    border-right: 1px solid rgba(81, 98, 255, 0.14);
  }
  [data-testid="stSidebar"] .block-container {
    padding-top: 1rem;
  }
  [data-testid="stRadio"] > div[role="radiogroup"] {
    background: #ffffff;
    border: 1px solid rgba(43, 52, 103, 0.14);
    border-radius: 12px;
    padding: 0.35rem 0.45rem;
    width: fit-content;
  }
  [data-testid="stTextInput"] input {
    border: 1px solid rgba(43, 52, 103, 0.18) !important;
    border-radius: 10px !important;
    background: #ffffff !important;
  }
  [data-testid="stTextInput"] input:focus {
    border-color: #5a67ff !important;
    box-shadow: 0 0 0 2px rgba(90, 103, 255, 0.15) !important;
  }
  [data-testid="stSlider"] {
    background: #ffffff;
    border: 1px solid rgba(43, 52, 103, 0.12);
    border-radius: 12px;
    padding: 0.45rem 0.7rem 0.2rem 0.7rem;
  }
  [data-testid="stSlider"] [role="slider"] {
    background: #5a67ff !important;
    border-color: #5a67ff !important;
  }
  .stButton > button {
    border: 0 !important;
    border-radius: 10px !important;
    background: linear-gradient(135deg, #ff4b6a 0%, #ff5c7d 100%) !important;
    box-shadow: 0 7px 20px rgba(255, 76, 108, 0.28);
    font-weight: 600 !important;
    transition: transform 0.16s ease, box-shadow 0.16s ease;
  }
  .stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 10px 24px rgba(255, 76, 108, 0.33);
  }
  [data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 14px;
    border: 1px solid rgba(43, 52, 103, 0.12) !important;
    box-shadow: 0 10px 26px rgba(35, 47, 104, 0.08);
    background: rgba(255, 255, 255, 0.9);
    backdrop-filter: blur(2px);
  }
  .status-bubble {
    border: 1px solid rgba(81, 98, 255, 0.16);
    border-radius: 14px;
    padding: 0.6rem 0.72rem;
    margin-bottom: 0.55rem;
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.92) 0%, rgba(237, 241, 255, 0.96) 100%);
    box-shadow: 0 8px 20px rgba(81, 98, 255, 0.11);
  }
  .status-bubble .label {
    font-size: 0.72rem;
    opacity: 0.62;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .status-bubble .value {
    font-size: 0.88rem;
    line-height: 1.25rem;
    font-weight: 600;
    color: #1c275f;
    word-break: break-word;
  }
  .status-bubble .value a {
    color: #2a3778;
    text-decoration: none;
  }
  .status-bubble .value a:hover {
    text-decoration: underline;
  }
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
    try:
        api_base_url, backend_status = _ensure_backend_api()
    except Exception as exc:
        st.error(f"Backend API startup failed: {exc}")
        st.stop()
    with st.sidebar:
        st.markdown(
            (
                "<div class='status-bubble'>"
                "<div class='label'>Backend</div>"
                f"<div class='value'>{backend_status}</div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            (
                "<div class='status-bubble'>"
                "<div class='label'>API URL</div>"
                f"<div class='value'><a href='{api_base_url}' target='_blank'>{api_base_url}</a></div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        st.divider()
        st.caption("Data Controls")
        if "deleted_urls_list" not in st.session_state:
            st.session_state.deleted_urls_list = []
        if st.button("Delete DB + Cache", use_container_width=True):
            deleted_count, deleted_text = _clear_persisted_data()
            st.session_state.deleted_urls_list = [
                line.strip() for line in deleted_text.splitlines() if line.strip()
            ]
            if st.session_state.deleted_urls_list:
                bullets = "\n".join([f"- {u}" for u in st.session_state.deleted_urls_list])
                st.success(
                    f"Deleted storage and cache. URLs removed: {deleted_count}\n\n"
                    f"{bullets}"
                )
            else:
                st.success("Deleted storage and cache. URLs removed: 0")

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
                    try:
                        payload = {
                            "feed_url": feed_url.strip(),
                            "episode_limit": int(settings.ingest_episode_limit),
                        }
                        endpoint = f"{api_base_url}/api/feeds"
                        with httpx.Client(timeout=60.0) as client:
                            resp = client.post(endpoint, json=payload)

                        if resp.status_code == 409:
                            data = resp.json()
                            st.warning("Feed already ingested; skipping re-embedding.")
                            res = SimpleNamespace(**data)
                        else:
                            resp.raise_for_status()
                            data = resp.json()
                            res = SimpleNamespace(**data)
                    except httpx.RequestError:
                        st.error(
                            "API server not reachable. If running externally, set API_BASE_URL "
                            "to that service."
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

    if page == "Search":
        st.subheader("Search")
        st.write(
            "Enter a natural-language query and get back the most relevant "
            "excerpted matches."
        )

        q = st.text_input("Query", value="Where was Trump mentioned?")
        st.markdown("**Number of chunks**")
        match_count = st.slider(
            "Number of chunks",
            min_value=1,
            max_value=50,
            value=5,
            step=1,
            label_visibility="collapsed",
        )

        if st.button("Search", type="primary"):
            out = st.empty()
            with out.container():
                with st.spinner("Searching…"):
                    try:
                        endpoint = f"{api_base_url}/api/search"
                        payload = {"query": q, "top_k": int(match_count)}
                        with httpx.Client(timeout=60.0) as client:
                            resp = client.post(endpoint, json=payload)
                        resp.raise_for_status()
                        data = resp.json()
                        hits = [SimpleNamespace(**h) for h in (data.get("results") or [])]
                    except httpx.RequestError:
                        st.error(
                            "API server not reachable. If running externally, set API_BASE_URL "
                            "to that service."
                        )
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
