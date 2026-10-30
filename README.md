# Asynchronous AI Research Microservice

Konecta GenAI development plan project: an asynchronous research microservice that accepts research queries over HTTP, runs long-running work in Celery workers, retrieves internal knowledge with RAG, calls an external FastMCP tool, and returns a structured Pydantic research report.

This repository implements the three milestones from **Samir AI Development Plan** without expanding beyond that scope.

## What was built

### Milestone 1 — Asynchronous backbone & microservices

- FastAPI with:
  - `POST /api/v1/research` — queues work and returns `task_id` immediately
  - `GET /api/v1/task/{task_id}` — reports Celery `PENDING` / `STARTED` / `SUCCESS` / `FAILURE`
- Redis as Celery message broker and result backend (`docker-compose.yml`)
- Celery worker with a short mock sleep so status polling can observe `PENDING` before `SUCCESS`

### Milestone 2 — Vector retrieval (RAG) & chunking

- Chroma vector database (persisted under `data/chroma`)
- Ingestion script using LangChain `TextLoader` + `RecursiveCharacterTextSplitter`
- Default context file: `knowledge_base.md`
- Worker retrieval helper: embed query → top-K similarity search
- Bonus: Redis semantic cache for retrieval results and completed reports

### Milestone 3 — Agent orchestration & tool use

- LangGraph `StateGraph` state tracks:
  - user query
  - retrieved context
  - search results
  - final report
- FastMCP HTTP server exposing a **Web Search** tool (live DuckDuckGo by default)
- Nodes:
  - **Retriever** → vector DB, then decide if KB is sufficient
  - **Researcher** → FastMCP `web_search` **only when KB is insufficient**
  - **Writer** → synthesizes available evidence into a `ResearchReport` Pydantic schema

GitHub MCP via Cursor is used as a learning/scaffolding aid during development (as stated in the plan). Runtime external tools for this service are provided by the local FastMCP server.

## Architecture

```text
Client
  │
  ▼
FastAPI  ──POST /api/v1/research──►  Redis/Celery queue
  │                                      │
  └──GET /api/v1/task/{id}◄── results ───┘
                                         │
                                         ▼
                                   Celery worker
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
              Retriever node      Researcher node       Writer node
              (Chroma RAG)        (FastMCP search)   (structured LLM)
```

## Tech stack

| Category | Technology |
| --- | --- |
| API / async workers | FastAPI, Celery, Redis |
| Orchestration & tools | LangChain, LangGraph, FastMCP |
| Data & output | Chroma (vector DB), Pydantic, OpenAI embeddings/chat |
| Local infra | Docker Compose (Redis) |

## Project layout

```text
app/
  main.py              # FastAPI routes
  celery_app.py        # Celery configuration
  tasks.py             # Background research task
  schemas.py           # Pydantic request/response/report models
  config.py            # Settings from .env
  rag/
    ingest.py          # Chunk + embed knowledge files
    retrieve.py        # Top-K retrieval + semantic cache
    store.py           # Chroma + embeddings
  agent/
    state.py           # LangGraph state
    nodes.py           # Retriever / Researcher / Writer
    graph.py           # StateGraph wiring
  mcp_server/
    server.py          # FastMCP web_search tool
  static/
    index.html         # Web UI
    styles.css
    app.js
knowledge_base.md      # Sample internal knowledge for RAG
docker-compose.yml     # Redis
requirements.txt
.env.example
```

## Prerequisites

- Python 3.11+ (developed against a modern CPython venv)
- Docker Desktop (for Redis)
- An OpenAI API key (embeddings + Writer node)

## Setup

```powershell
cd C:\Users\Samir\Documents\GenAI\projects\ai-researcher-microservice
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set:

```env
OPENAI_API_KEY=sk-...
```

Start Redis:

```powershell
docker compose up -d
```

Ingest the knowledge base into Chroma:

```powershell
python -m app.rag.ingest
```

## Run the system (4 processes)

Use four terminals, all with the venv activated.

### 1) Redis

Already running via Docker Compose.

### 2) FastMCP server (external tool)

```powershell
python -m app.mcp_server.server
```

Listens on `http://127.0.0.1:8001/mcp`.

### 3) Celery worker

On Windows use the solo pool:

```powershell
celery -A tasks worker --loglevel=INFO --pool=solo
```

### 4) FastAPI

```powershell
uvicorn app.main:app --reload --port 8000
```

- Web UI: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## How to use

### Web UI (recommended)

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/), type a research question, click **Start research**. The page polls `GET /api/v1/task/{task_id}` and renders the structured report when the worker finishes.

Make sure Redis, the FastMCP server, and the Celery worker are running first.

### Submit research via API

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/research `
  -H "Content-Type: application/json" `
  -d "{\"query\": \"What are Samir hobbies and how does RAG help research?\"}"
```

Example response:

```json
{
  "task_id": "b1c2...",
  "status": "PENDING"
}
```

### Poll status

```powershell
curl http://127.0.0.1:8000/api/v1/task/REPLACE_WITH_TASK_ID
```

While the worker is sleeping/working you should see `PENDING` or `STARTED`. When finished:

```json
{
  "task_id": "...",
  "status": "SUCCESS",
  "result": {
    "cached": false,
    "report": {
      "query": "...",
      "summary": "...",
      "key_findings": ["..."],
      "internal_context": [{"content": "...", "source": "knowledge_base.md", "score": 0.2}],
      "external_results": [{"title": "...", "snippet": "...", "url": "..."}],
      "confidence": "medium"
    }
  },
  "error": null
}
```

## Acceptance criteria mapping

| Criterion from the plan | How this project meets it |
| --- | --- |
| User never waits for LLM processing on the API | `POST /research` only enqueues Celery and returns `task_id` |
| Final output adheres to a Pydantic schema | Writer uses `with_structured_output(ResearchReport)` |
| Combines vector DB + MCP tools | Retriever → Chroma; Researcher → FastMCP `web_search`; Writer merges both |

## Notes / design choices tied to the plan

- **Pydantic schema:** the PDF requires a schema for the Writer output but does not list fields. `ResearchReport` is defined to match the Milestone 3 state: query, retrieved context, MCP search results, and a synthesized final report.
- **Web Search tool:** implemented as a FastMCP mock/internal search tool, which the plan explicitly allows.
- **Vector database:** Chroma is used as the local vector database behind LangChain.
- **Windows Celery:** prefer `--pool=solo` to avoid prefork/`PermissionError` issues on Windows.

## Experimenting with chunking (Milestone 2)

```powershell
python -m app.rag.ingest --chunk-size 300 --chunk-overlap 30
python -m app.rag.ingest --chunk-size 800 --chunk-overlap 100
```

Compare retrieval quality by repeating the same research query after each re-ingest.
