from __future__ import annotations

import httpx


class Http:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=httpx.Timeout(20.0))

    def get_text(self, url: str) -> str:
        try:
            resp = self._client.get(url)
        except httpx.RequestError as exc:
            raise RuntimeError(f"Failed to fetch URL: {url} ({exc})") from exc

        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"Non-200 response for {url}: {exc.response.status_code}") from exc

        # RSS is text/XML, so return decoded text content.
        return resp.text

    def close(self) -> None:
        self._client.close()

