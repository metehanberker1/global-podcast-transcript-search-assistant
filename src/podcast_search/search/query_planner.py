from __future__ import annotations

import json
from typing import Any

from app.config import settings


def plan_query_text(user_query: str) -> str:
    """Use GPT-4o-mini to structure the query for embeddings.

    Output must be *embedding input text*, not an answer. If planning fails,
    fall back to the raw user query.
    """

    # If no key is configured, avoid API calls.
    if not getattr(settings, "openai_api_key", None):
        return user_query

    try:  # pragma: no cover (real API path)
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        model = settings.query_planner_model

        prompt = (
            "You are a query planning tool for semantic search over podcast episodes. "
            "Given a user's natural-language request, produce ONLY a JSON object with keys: "
            "`query_text` (string used as embedding input) and `filters` (array, can be empty). "
            "Do NOT summarize, do NOT answer, do NOT include any other keys."
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_query},
        ]

        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.0,
            # json_object keeps output machine-parseable in most OpenAI setups.
            response_format={"type": "json_object"},
        )

        content = resp.choices[0].message.content or ""
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            content = content[start : end + 1]
        data: dict[str, Any] = json.loads(content)
        query_text = data.get("query_text")
        if isinstance(query_text, str) and query_text.strip():
            return query_text.strip()
    except Exception:
        return user_query

    return user_query

