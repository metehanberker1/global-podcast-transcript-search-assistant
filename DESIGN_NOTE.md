# Design Note

## Why this architecture

We optimized for semantic retrieval quality, low operational friction, and a clean path to scale.

- **Semantic search + vector database**
  - We care about meaning, not exact words, so vector search is the right core primitive.
  - Users can phrase the same idea differently and still get relevant transcript matches.

- **Why ChromaDB**
  - Chroma made sense here because it is simple to run, local-first, and integrates cleanly with Python.
  - It gives us persistent collections without introducing early infrastructure overhead.
  - At this stage, that tradeoff is better than jumping straight to a heavier managed/distributed vector stack.

- **Why an LLM query planner**
  - Raw user text is often messy or underspecified.
  - The planner structures that text into a retrieval-friendly form, which improves matching quality beyond basic cleanup.

- **Why FastAPI over Flask or Django**
  - FastAPI gives typed models, validation, and OpenAPI with very little ceremony, which fits an API-first service.
  - Flask is flexible but would require more manual guardrails for request/response validation.
  - Django is great for full web platforms, but it is more framework than this backend needs.

- **Why Streamlit**
  - Streamlit lets us ship a clean demo interface quickly and keep iteration tight.
  - It is a good fit for showcasing product behavior without building a full frontend app first.

- **Why frontend/backend separation**
  - The UI talks to the backend over HTTP, which keeps responsibilities clear.
  - That separation makes scaling, testing, and future client additions much easier.

- **Why sharding + consistent hashing**
  - As feed count and traffic grow, sharding gives a clear horizontal scaling path.
  - Consistent hashing keeps routing predictable and limits remapping churn when node membership changes.

- **Why URL normalization + registry**
  - This prevents duplicate ingest from alias URLs and keeps feed identity stable.
  - It also supports deterministic search scope based on the latest ingested feed.

- **Why index-handle caching**
  - If a URL (or its normalized alias) was already ingested, we can resolve its chunk/index handle from cache instead of rebuilding lookup paths.
  - That reduces overhead on repeated customer queries and improves response latency on warm paths.

- **Why metrics + layered tests**
  - Metrics give immediate visibility into ingest/search health and latency.
  - Unit/integration/contract/live test layers give fast feedback locally and real running-server validation when needed.

## What to improve next for production readiness

- Add hybrid retrieval (vector + keyword/BM25) to improve both semantic and exact-term recall.
- Add two-stage ranking (fast candidate retrieval + stronger re-ranking) to improve top-result precision.
- Add incremental, idempotent ingestion so only new/changed episodes are embedded and indexed.
- Move from local Chroma persistence to a managed/distributed vector backend with backup/restore and SLA guarantees.
- Introduce async ingestion workers with queueing, retries, and dead-letter handling.
- Add authentication/authorization, tenant isolation, and request-level rate limits.
- Add structured logs, tracing, alerting, and dashboards for full observability.
- Add embedding/index versioning with controlled reindex workflows to prevent model/dimension drift issues.
- Add API versioning and stronger deployment gates (health probes + smoke checks).