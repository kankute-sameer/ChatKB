# ChatKB technical architecture

This document describes the main backend feature flows: knowledge-base ingestion, extraction, retrieval, tabular query, chat turns, and agents. Diagrams use Mermaid.

## System overview

```mermaid
flowchart TB
  subgraph Clients
    UI[React frontend]
  end

  subgraph Edge
    Vercel[Vercel SPA + /api rewrite]
  end

  subgraph Backend["FastAPI backend (Railway)"]
    API[REST + SSE]
    Agents[Agents]
    Conv[Conversations]
    KB[Knowledge bases]
    Auth[JWT auth]
  end

  subgraph Data
    PG[(Postgres + pgvector)]
    S3[(AWS S3)]
  end

  subgraph Providers
    LLM[OpenAI-compatible LLM]
    Gemini[Gemini embeddings]
    Exa[Exa web search]
    Docling[Docling PDF/DOCX]
    DuckDB[DuckDB in-process]
    Langfuse[Langfuse]
  end

  UI --> Vercel --> API
  API --> Auth
  API --> Agents
  API --> Conv
  API --> KB
  KB --> PG
  KB --> S3
  KB --> Docling
  KB --> Gemini
  KB --> LLM
  KB --> DuckDB
  Conv --> LLM
  Conv --> Exa
  Conv --> KB
  Conv --> Langfuse
```

| Concern | Technology |
|---------|------------|
| API | FastAPI, uvicorn (single process) |
| Metadata + vectors | PostgreSQL 16, pgvector (HNSW cosine) |
| Raw files | AWS S3 (presigned GET for PDF viewer) |
| PDF / DOCX parse | Docling (`DocumentConverter` process singleton) |
| Embeddings | Gemini `gemini-embedding-001` (1536 dims) |
| Chat / vision / summaries | OpenAI-compatible Responses API |
| Web search | Exa |
| Tabular SQL | DuckDB over S3 bytes |
| Tracing | Langfuse (optional) |

---

## 1. Knowledge-base ingestion

Upload returns immediately. Processing continues in a background task until the file is `ready` or `failed`.

```mermaid
flowchart TD
  A[POST upload] --> B[Validate MIME + size ≤ 50MB]
  B --> C[Write temp file]
  C --> D[Insert kb_files status=processing]
  D --> E[asyncio.create_task run_ingestion]
  E --> F[Put original bytes to S3]
  F --> G[Extract]
  G --> H{Prose or table?}
  H -->|PDF DOCX MD TXT JSON-prose| I[Describe images]
  I --> J[Assemble content_md]
  J --> K[Chunk blocks]
  H -->|CSV TSV JSON-table| L[Prepare table schema + preview chunks]
  K --> M[LLM file summary]
  L --> M
  M --> N[Gemini embed chunks]
  N --> O[Replace kb_chunks rows]
  O --> P[Update kb_files ready + content_md + summary_md]
  P --> Q[Rebuild collections.index_md]
```

**Code path**

| Stage | Location |
|-------|----------|
| Upload API | `app/features/kb/router.py` → `KbService.upload_file` |
| Pipeline | `app/features/kb/ingestion/pipeline.py` (`run_ingestion`) |
| Extract | `app/features/kb/ingestion/extract.py` |
| Image captions | `app/features/kb/ingestion/describe_image.py` |
| Chunk | `app/features/kb/ingestion/chunk.py` |
| Table prepare | `app/features/kb/ingestion/table.py` |
| Summaries | `app/features/kb/ingestion/assemble.py` + `prompts.py` |
| Embed | `app/features/kb/ingestion/embed.py` |
| Persist | `app/features/kb/db.py` |

**What is stored where**

| Artifact | Store |
|----------|-------|
| Original file bytes | S3 key `{owner_id}/{file_id}{ext}` |
| File metadata, `content_md`, `summary_md`, status | `kb_files` |
| Searchable text + embedding + page/anchor/bbox | `kb_chunks` (+ generated `text_tsv`) |
| Collection catalog of file summaries | `collections.index_md` |
| Image pixels | Not stored; captions only |

---

## 2. Extraction (what runs per format)

```mermaid
flowchart TD
  Start[extract path + mime] --> Ext{Extension}

  Ext -->|.pdf| PDF[Docling PDF pipeline]
  Ext -->|.docx| DOCX[Docling DOCX]
  Ext -->|.md| MD[markdown-it CommonMark]
  Ext -->|.txt| TXT[Blank-line paragraphs]
  Ext -->|.csv / .tsv| CSV[csv.DictReader sample ≤100 rows]
  Ext -->|.json| JSON{Array of objects?}

  PDF --> Prose[ProseExtraction: blocks + pages + bbox + images]
  DOCX --> Prose
  MD --> Prose
  TXT --> Prose
  JSON -->|yes| Table[TableExtraction]
  JSON -->|no| ProseJSON[Chunked pretty JSON prose]
  CSV --> Table
  ProseJSON --> Prose

  Prose --> Img[Picture/chart items → PIL]
  Img --> Cap[Vision LLM captions if ≥ min dimension]
  Cap --> Blocks[Ordered text / heading / image / table blocks]
```

**Docling settings (PDF)** — OCR off, table structure on, picture images at scale 2.0. Converter is a **process-wide singleton** (`get_converter`) because model init is expensive.

**Block fields:** `text`, `block_type`, `page`, `anchor`, `bbox` (normalized for PDF), `is_heading`.

**Chunking (prose):** headings update section context only; non-heading blocks become chunks with the current header prepended; oversized text splits near 2000 tokens (~4 chars/token).

**Standalone tables:** only a schema chunk and a short markdown preview are embedded. Full rows stay on S3 for `query_table`.

---

## 3. Retrieval (`kb_search`)

Agents call `kb_search` scoped to attached collection IDs. Default tool return size is top **5** after fusion.

```mermaid
flowchart TD
  Q[User / agent query] --> E[Gemini embed task=RETRIEVAL_QUERY]
  E --> V[Vector search]
  E --> L[Lexical search]

  V --> VQ["embedding <=> query cosine<br/>limit 30, HNSW"]
  L --> LQ["text_tsv @@ websearch_to_tsquery<br/>GIN, limit 30"]

  VQ --> RRF[Reciprocal rank fusion RRF_K=60]
  LQ --> RRF
  RRF --> Top[Top k hits]
  Top --> Cite[Register KbSource → cite_id]
  Cite --> Out[Tool JSON + source-document UI parts]
```

**Code:** `app/features/kb/retrieve.py` (`hybrid_search`), `app/features/kb/tools.py` (`KbSearchTool`).

**Citation contract:** model must write `[cite:<cite_id>]` using IDs returned by tools. Invalid cites are stripped on validation.

**Tool policy (system prompt):** when both KB and web are available, search the knowledge base first; use `web_search` only if KB is empty/unhelpful or needs fresh public data (`KB_SEARCH_GUIDANCE` in `app/features/agents/wrapper.py`).

---

## 4. Tabular query (`query_table`)

```mermaid
flowchart TD
  A[kb_search for schema / column names] --> B[query_table file_id + SQL]
  B --> C[Auth: file in agent collections + ready]
  C --> D[Download S3 bytes to temp]
  D --> E[DuckDB: CREATE TABLE data AS read_*_auto]
  E --> F[Validate read-only SQL]
  F --> G[Execute with timeout + row cap]
  G --> H[Cite each result row]
```

**Guards:** SELECT-only, must reference table `data`, blocked DML/DDL, 5s timeout, ≤100 rows, concurrency and memory limits.

**Code:** `app/features/kb/tools.py` (`QueryTableTool`), `app/features/kb/query.py`.

---

## 5. Chat turn (streaming agent loop)

```mermaid
flowchart TD
  R[POST /v1/responses] --> U[Persist user message]
  U --> G[Spawn generation task]
  G --> T[Resolve agent + scoped tools]
  T --> S[Assemble system prompt]
  S --> I[Build Responses API input]
  I --> L[LLM stream round]
  L --> E[Emit UI SSE events]
  E --> P{Pending tool calls?}
  P -->|yes| X[Execute tools]
  X --> O[Emit tool output + source parts]
  O --> A[Append tool results to input]
  A --> L
  P -->|no| V[Validate citations]
  V --> M[Persist assistant message]
  M --> F[Finish SSE + Langfuse spans]
```

**Limits:** up to 8 tool rounds per turn. Stream buffer is **in-process memory** (single replica / single worker required).

**Code:** `app/features/conversations/service.py` (`run_generation`, `_run_agent_loop`), `app/core/llm/client.py`.

---

## 6. Agents, tools, and prompts

```mermaid
flowchart TD
  C[Conversation] --> ST{session_type}
  ST -->|build| B[Builder agent only]
  B --> BT[Editor tools only]
  ST -->|chat| A[Running agent or default]
  A --> W{web_search in connectors?}
  W -->|yes / no agent| WS[Include web_search]
  W -->|no| NW[Skip web_search]
  A --> COL[Load attached collection IDs]
  COL --> KB[Scope kb_search]
  COL --> QT[Scope query_table]
  BT --> P[System prompt]
  WS --> P
  NW --> P
  KB --> P
  QT --> P
  P --> BASE[BASE_INSTRUCTIONS + agent.instructions]
  BASE --> GUIDE[Append tool guidance blocks]
```

| Tool | When | Backend |
|------|------|---------|
| `web_search` | Chat; connector allows (default on new agents) | Exa |
| `kb_search` | Chat; scoped to collections | Hybrid search |
| `query_table` | Chat; scoped to collections | DuckDB |
| `get_agent_setup` / `update_*` / `list_knowledge_bases` / `attach_knowledge_bases` | Build session only | Agent editor |

**Prompt assembly**

1. `BASE_INSTRUCTIONS` (+ agent `instructions` if any) — `wrapper.py`
2. `WEB_SEARCH_GUIDANCE` if web tool present
3. `KB_SEARCH_GUIDANCE` if KB tool present
4. `QUERY_TABLE_GUIDANCE` if query_table present

Builder instructions live in `app/features/agents/builder.py`.

---

## 7. Auth and feedback

```mermaid
flowchart LR
  Login[POST /auth/login] --> Hash[Verify bcrypt AUTH_USERS]
  Hash --> JWT[Issue JWT sub=username]
  JWT --> Req[Bearer on protected routes]
  Req --> Owner[owner_id = JWT sub]
```

| Feedback | Endpoint | Sink |
|----------|----------|------|
| Thumbs on message | `PUT …/messages/{id}/feedback` | Langfuse score on turn (seed = assistant message id) |
| Product opened | `POST /v1/product/opened` | Langfuse |
| Experience comment | `POST /v1/feedback` | Langfuse |

---

## 8. Observability spans

| Name | Kind |
|------|------|
| `conversation.turn` | Root trace (seeded by assistant message id) |
| `llm.generation` | Each agent-loop round |
| `tool.<name>` | Each tool call |
| `citations` | Post-turn cite validation |
| `product.opened` / `product.feedback` | Product telemetry |

---

## Key source index

| Area | Paths under `backend/app/` |
|------|----------------------------|
| KB service / API | `features/kb/service.py`, `router.py`, `db.py`, `models.py` |
| Ingestion | `features/kb/ingestion/{pipeline,extract,chunk,embed,assemble,table,describe_image,prompts}.py` |
| Retrieval | `features/kb/retrieve.py`, `tools.py`, `query.py` |
| Chat | `features/conversations/service.py`, `router.py`, `buffer.py` |
| Agents | `features/agents/{wrapper,builder,tools,service}.py` |
| LLM / storage / tracing | `core/llm/client.py`, `core/storage.py`, `core/tracing.py`, `core/db.py` |
| Citations | `core/citations/` |
