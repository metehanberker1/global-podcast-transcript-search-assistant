# Podcast Search Assistant

Streamlit frontend + FastAPI backend for ingesting podcast RSS feeds and running semantic transcript search over a persistent Chroma vector store.

## Local Setup

### 1) Create and activate a virtual environment

Windows (PowerShell):

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Windows (cmd):

```bash
python -m venv .venv
.venv\Scripts\activate.bat
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

```bash
pip install -U pip
pip install -e ".[dev]"
```

### 3) Configure environment

Create a `.env` file in repo root:

```env
OPENAI_API_KEY=
QUERY_PLANNER_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
CHROMA_PERSIST_DIR=./chromadb
REGISTRY_PATH=./data/feed_registry.json
API_BASE_URL=http://127.0.0.1:8000
PODCAST_SEARCH_DUMMY_EMBEDDINGS=1
```

Notes:
- Keep `OPENAI_API_KEY` empty + `PODCAST_SEARCH_DUMMY_EMBEDDINGS=1` for local/offline testing.
- For real embeddings/planner, set a valid `OPENAI_API_KEY` and unset `PODCAST_SEARCH_DUMMY_EMBEDDINGS`.

## Run

### Option A: Streamlit only (recommended for local dev)

```bash
streamlit run streamlit_app.py
```

Behavior:
- Streamlit checks `API_BASE_URL`.
- If local API is not reachable, it auto-starts FastAPI in-process and connects UI calls to it.
- Sidebar shows backend status and active API URL.

### Option B: Run FastAPI explicitly

```bash
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

Then run Streamlit in another terminal:

```bash
streamlit run streamlit_app.py
```

## API Endpoints

- `GET /api/metrics`
- `POST /api/feeds`
- `POST /api/search`

## Testing

Full suite:

```bash
pytest -q
```

Live API test (opt-in, requires running server):

Terminal 1 (start local API server):

```bash
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Terminal 2 (run live test against that server):

Windows (cmd):

```bash
set RUN_LIVE_API_TESTS=1 && pytest -q tests/live/test_live_api_server_requests.py
```

macOS/Linux:

```bash
RUN_LIVE_API_TESTS=1 pytest -q tests/live/test_live_api_server_requests.py
```

Optional target override:

```bash
API_BASE_URL=http://127.0.0.1:8000
```
