from __future__ import annotations


def chunk_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    """Deterministic character chunking with overlap."""

    normalized = (text or "").replace("\r\n", "\n")
    size = max(int(chunk_size), 1)
    ov = max(int(overlap), 0)
    if ov >= size:
        ov = max(size - 1, 0)

    # Move forward by `size - overlap` so adjacent chunks share context.
    step = size - ov
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + size, len(normalized))
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start += step

    return chunks

