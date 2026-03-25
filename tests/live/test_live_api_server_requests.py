from __future__ import annotations

import http.server
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest

from fixtures.rss_samples import RSS_EP1


def test_running_api_server_accepts_ingest_and_search_requests() -> None:
    """Live API test: assumes FastAPI server is already running.

    Run with:
      Windows (cmd):
        set RUN_LIVE_API_TESTS=1 && pytest -q tests/live/test_live_api_server_requests.py

      macOS/Linux:
        RUN_LIVE_API_TESTS=1 pytest -q tests/live/test_live_api_server_requests.py

    Optional:
      API_BASE_URL=http://127.0.0.1:8000 (default)
    """

    if os.getenv("RUN_LIVE_API_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_API_TESTS=1 to run live API request tests.")

    api_base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")

    # Serve a temporary RSS feed so this test controls its own ingest input.
    rss_server = _RssServer(rss_xml=RSS_EP1)
    rss_server.start()
    feed_url = rss_server.url
    query_text = "Ep1"

    try:
        with httpx.Client(timeout=60.0) as client:
            # Backend must be reachable before exercising ingest/search.
            metrics = client.get(f"{api_base_url}/api/metrics")
            assert metrics.status_code == 200

            # Ingest the temporary feed.
            ingest = client.post(
                f"{api_base_url}/api/feeds",
                json={"feed_url": feed_url, "episode_limit": 10},
            )
            assert ingest.status_code == 201

            # Query the running API and validate response shape.
            search = client.post(
                f"{api_base_url}/api/search",
                json={"query": query_text, "top_k": 5},
            )
            assert search.status_code == 200
            body = search.json()
            assert "results" in body
            assert isinstance(body["results"], list)
            assert body["results"]
    finally:
        rss_server.stop()


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class _RssServer:
    def __init__(self, rss_xml: str) -> None:
        self._rss_xml = rss_xml
        self.port = _find_free_port()
        self._thread: threading.Thread | None = None
        self._httpd: http.server.HTTPServer | None = None

    def start(self) -> None:
        rss_xml = self._rss_xml

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/rss+xml")
                self.end_headers()
                self.wfile.write(rss_xml.encode("utf-8"))

            def log_message(self, format: str, *args) -> None:
                return None

        self._httpd = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=2)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/rss.xml"


def _wait_until_ready(url: str, *, timeout_s: float = 10.0) -> None:
    started = time.time()
    while time.time() - started < timeout_s:
        try:
            with httpx.Client(timeout=1.0) as client:
                r = client.get(url)
                if r.status_code == 200:
                    return
        except Exception:
            pass
        time.sleep(0.25)
    raise RuntimeError(f"Server not ready: {url}")


def test_api_search_via_subprocess_server(tmp_path) -> None:
    chroma_dir = str(tmp_path / "chromadb")
    registry_path = str(tmp_path / "feed_registry.json")

    rss_server = _RssServer(rss_xml=RSS_EP1)
    rss_server.start()
    try:
        port = _find_free_port()
        env = dict(os.environ)
        env["CHROMA_PERSIST_DIR"] = chroma_dir
        env["REGISTRY_PATH"] = registry_path
        env["API_BASE_URL"] = f"http://127.0.0.1:{port}"
        env["OPENAI_API_KEY"] = ""
        env["PODCAST_SEARCH_DUMMY_EMBEDDINGS"] = "1"
        env["SHARD_NODES"] = "local"
        env["LOCAL_NODE_ID"] = "local"

        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "api.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=str(Path(__file__).resolve().parents[2]),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            _wait_until_ready(f"http://127.0.0.1:{port}/api/metrics")
            with httpx.Client(timeout=10.0) as client:
                resp_ingest = client.post(
                    f"http://127.0.0.1:{port}/api/feeds",
                    json={"feed_url": rss_server.url, "episode_limit": 10},
                )
                assert resp_ingest.status_code == 201

                resp_search = client.post(
                    f"http://127.0.0.1:{port}/api/search",
                    json={"query": "Ep1", "top_k": 5},
                )
                assert resp_search.status_code == 200
                assert resp_search.json()["results"]
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    finally:
        rss_server.stop()

