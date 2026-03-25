from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app as api_app


def test_metrics_contract_smoke() -> None:
    client = TestClient(api_app)
    resp = client.get("/api/metrics")
    assert resp.status_code == 200

    body = resp.json()
    # Contract requires these concrete fields in the runtime payload.
    assert isinstance(body["ingest_episode_count"], int)
    assert isinstance(body["chunk_index_count"], int)
    assert isinstance(body["search_hit_count"], int)
    assert isinstance(body["ingest_duration_ms_last"], int)
    assert isinstance(body["search_duration_ms_last"], int)

