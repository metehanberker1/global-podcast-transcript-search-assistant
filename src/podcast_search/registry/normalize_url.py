from __future__ import annotations

import hashlib
from urllib.parse import urlparse, urlunparse


def normalize_url(url: str) -> str:
    """Canonicalize RSS feed URLs for stable deduplication."""

    cleaned = (url or "").strip()
    parsed = urlparse(cleaned)

    if not parsed.scheme or not parsed.netloc:
        # If it's not a valid absolute URL, fall back to trimmed string.
        return cleaned

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"

    # If this looks like a "directory" feed endpoint, ensure trailing slash.
    # Heuristic: no '.' in last segment => treat as directory-like.
    last_seg = path.rsplit("/", 1)[-1]
    if last_seg and "." not in last_seg and not path.endswith("/"):
        path = f"{path}/"

    # Strip fragments; preserve query.
    rebuilt = parsed._replace(scheme=scheme, netloc=netloc, path=path, fragment="")
    return urlunparse(rebuilt)


def feed_id_from_normalized_url(normalized_url: str) -> str:
    """Must be stable and match existing registry IDs."""

    digest = hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()
    return digest[:24]

