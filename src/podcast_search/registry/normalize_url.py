from __future__ import annotations

import hashlib
from urllib.parse import urlparse, urlunparse


def normalize_url(url: str) -> str:
    """Canonicalize RSS feed URLs for stable deduplication."""

    cleaned = (url or "").strip()
    parsed = urlparse(cleaned)

    if not parsed.scheme or not parsed.netloc:
        # Keep non-absolute inputs unchanged after trimming.
        return cleaned

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"

    # Normalize directory-like paths with a trailing slash.
    # Heuristic: no '.' in the last segment implies directory-like URL.
    last_seg = path.rsplit("/", 1)[-1]
    if last_seg and "." not in last_seg and not path.endswith("/"):
        path = f"{path}/"

    # Remove fragment identifiers and keep query parameters.
    rebuilt = parsed._replace(scheme=scheme, netloc=netloc, path=path, fragment="")
    return urlunparse(rebuilt)


def feed_id_from_normalized_url(normalized_url: str) -> str:
    """Build a stable feed identifier from canonical URL text."""

    digest = hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()
    return digest[:24]

