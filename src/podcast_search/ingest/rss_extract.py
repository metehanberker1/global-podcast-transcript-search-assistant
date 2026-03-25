from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EpisodeExtracted:
    episode_id: str
    episode_title: str
    published_at: str | None
    text: str
    source_url: str | None


def _episode_id_from_fields(title: str, published_at: str | None, link: str | None) -> str:
    seed = f"{title}|{published_at or ''}|{link or ''}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]


def extract_episode_items(feed_xml: str, *, episode_limit: int) -> list[EpisodeExtracted]:
    # Import lazily so module import remains lightweight.
    import feedparser

    parsed = feedparser.parse(feed_xml)
    entries: list[Any] = list(getattr(parsed, "entries", []) or [])
    entries = entries[: max(int(episode_limit), 0)]

    out: list[EpisodeExtracted] = []
    for e in entries:
        title = (getattr(e, "title", None) or e.get("title") or "").strip()
        published_at = (getattr(e, "published", None) or e.get("published") or e.get("updated") or None)
        if published_at is not None:
            published_at = str(published_at)

        link = getattr(e, "link", None) or e.get("link") or None
        if link is not None:
            link = str(link)

        guid = getattr(e, "guid", None) or e.get("guid") or e.get("id") or None
        if guid is not None:
            guid = str(guid)

        episode_id = guid or _episode_id_from_fields(title, published_at, link)

        # Build the episode text from the richest available fields.
        summary = e.get("summary") if hasattr(e, "get") else None
        description = e.get("description") if hasattr(e, "get") else None
        content = e.get("content") if hasattr(e, "get") else None

        text_parts: list[str] = []
        if summary:
            text_parts.append(str(summary))
        if description and description not in text_parts:
            text_parts.append(str(description))
        if content:
            # `content` is often a list of objects containing a `value` field.
            if isinstance(content, list):
                for c in content:
                    v = c.get("value") if isinstance(c, dict) else None
                    if v:
                        text_parts.append(str(v))

        if not text_parts:
            text_parts.append(title)

        text = "\n".join([p.strip() for p in text_parts if p and str(p).strip()])

        out.append(
            EpisodeExtracted(
                episode_id=episode_id,
                episode_title=title or episode_id,
                published_at=published_at,
                text=text,
                source_url=link,
            )
        )

    return out


def discover_related_feed_urls(feed_xml: str) -> list[str]:
    """Extract alternate/self feed URLs when present."""

    import feedparser

    parsed = feedparser.parse(feed_xml)
    links = []
    feed = getattr(parsed, "feed", None)
    for l in getattr(feed, "links", []) or []:
        href = None
        if isinstance(l, dict):
            href = l.get("href")
        else:
            href = getattr(l, "href", None)
        if href:
            links.append(str(href))
    return links

