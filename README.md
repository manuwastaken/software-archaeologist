# 🏛️ Archaeon — AI Software Archaeologist

> An autonomous Code Intelligence and Semantic Retrieval system combining AST static analysis, vector embeddings, and grounded LLM reasoning to explain **how** and **why** software systems evolve.

---

## 📌 Features Across Completed Phases

### 🚀 Phase 1 — Foundations (Completed)
- ⚡ **FastAPI REST API:** Modular endpoints with `APIRouter`, Pydantic v2 schemas, and interactive OpenAPI documentation (`/docs`).
- 🗄️ **SQLAlchemy 2.0 ORM & SQLite:** Multi-threaded SQLite database engine managing repository state and background ingestion tasks.
- 🔄 **Asynchronous Git Ingestion:** Clones GitHub repositories and extracts metadata using `GitPython` and FastAPI `BackgroundTasks`.
- 🧪 **Automated Testing:** Comprehensive unit tests covering API routes, ORM models, and schemas.

### 🧠 Phase 2 — Code Intelligence & Static Analysis (Completed)
- 🌳 **Python AST Parser:** Built with native `ast.NodeVisitor` to safely extract classes, inheritance hierarchies, functions, methods, imports, docstrings, and exact line boundaries without executing code.
- 📄 **File-by-File Ingestion:** Discovers all Python source files while filtering out `.git`, `.venv`, and `__pycache__` directories.
- 🔗 **Relational Symbol Mapping:** `files` and `symbols` SQLite tables with foreign key cascades and parent class relationships.
- 📊 **Dynamic Progress Tracking:** Reports fine-grained background job progress (0% ➔ 50% clone, 50% ➔ 85% AST).
- 🔍 **Code Inspection Endpoints:** `GET /repositories/{id}/files` and `GET /repositories/{id}/symbols`.

### 🧠 Phase 3 — Semantic RAG Engine (Completed)
- ✂️ **AST Semantic Chunker:** Slices code strictly along logical syntax boundaries (file overviews, class definitions, standalone functions, and class methods) with prepended contextual headers.
- ⚡ **Gemini Embeddings Service:** Generates 3,072-dimensional vector embeddings using Google's `models/gemini-embedding-001` with multi-threaded concurrent batching, query LRU caching, and exponential backoff retry.
- 🗃️ **ChromaDB Vector Store:** Embedded persistent vector database with cosine similarity search and repository-level metadata filtering.
- 💬 **Grounded Q&A Endpoint:** `POST /repositories/{id}/query` leveraging `gemini-2.5-flash` with strict anti-hallucination guardrails and line-level citations.

---

## 🚀 Quick Start

### 1. Installation
```bash
# Clone the repository
git clone https://github.com/manuwastaken/software-archaeologist.git
cd software-archaeologist

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows PowerShell
# source .venv/bin/activate # Linux / macOS

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create a `.env` file in the project root:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Run the API Server
```bash
uvicorn src.api.main:app --reload
```

Interactive API Documentation (Swagger UI) is live at: 👉 **http://127.0.0.1:8000/docs**

---

## 📡 API Endpoints

| Method | Endpoint | Description | Status Code |
| :--- | :--- | :--- | :--- |
| **POST** | `/repositories` | Submit a GitHub repository URL for ingestion | `201 Created` |
| **GET** | `/repositories` | List all ingested repositories | `200 OK` |
| **GET** | `/repositories/{id}` | Get metadata and status for a repository | `200 OK` |
| **GET** | `/repositories/{id}/files` | List files discovered during ingestion | `200 OK` |
| **GET** | `/repositories/{id}/symbols` | List all extracted AST symbols (classes, functions, methods) | `200 OK` |
| **POST** | `/repositories/{id}/query` | Ask a natural language question about the codebase (RAG) | `200 OK` |
| **GET** | `/jobs/{id}` | Check background ingestion job progress (0% - 100%) | `200 OK` |

---

## 🧪 Running Automated Tests

Run the full unit test suite (13 tests executing locally with zero API quota consumption):
```bash
pytest tests/unit -v
```

To run the live end-to-end integration test against Gemini:
```bash
pytest tests/unit/integration/test_live_rag.py -s -v
```

---

## 📖 Study Material & Concept Guides

Comprehensive architectural reference guides for each phase are available under `docs/concepts/`:

- **Phase 1 Foundations:**
  - [`step1_llm_basics.md`](docs/concepts/step1_llm_basics.md) — API keys, models, prompts, tokens, and temperature.
  - [`step2_fastapi_basics.md`](docs/concepts/step2_fastapi_basics.md) — HTTP, REST, routers, dependency injection, and Pydantic.
  - [`step3_sqlalchemy_basics.md`](docs/concepts/step3_sqlalchemy_basics.md) — ORM, SQLite, session lifecycle, and engine configuration.
  - [`phase1_codebase_guide.md`](docs/concepts/phase1_codebase_guide.md) — Phase 1 architecture and Git clone pipeline.
- **Phase 2 Code Intelligence:**
  - [`phase2_codebase_guide.md`](docs/concepts/phase2_codebase_guide.md) — Python AST parsing, `SymbolVisitor`, database models, and endpoints.
- **Phase 3 RAG Engine:**
  - [`phase3_step1_semantic_chunker.md`](docs/concepts/phase3_step1_semantic_chunker.md) — Semantic AST chunking, context headers, and boundary slicing.
  - [`phase3_step2_embeddings_and_vector_store.md`](docs/concepts/phase3_step2_embeddings_and_vector_store.md) — 3072-dim embeddings, concurrency, LRU cache, and ChromaDB.
  - [`phase3_step3_grounded_rag_service_and_api.md`](docs/concepts/phase3_step3_grounded_rag_service_and_api.md) — Ingestion integration, prompt engineering, and grounded Q&A endpoint.

---

## 🗺️ Project Roadmap

- [x] **Phase 1:** API Skeleton, SQLite Database, Git Ingestion Engine, & Unit Tests
- [x] **Phase 2:** Code Intelligence (Python AST Parsing & Symbol Extraction)
- [x] **Phase 3:** RAG System (Embeddings, ChromaDB Vector Search, & Grounded Q&A)
- [ ] **Phase 4:** LangChain Integration & Conversational Memory *(Next!)*
- [ ] **Phase 5:** Tool-Using Agent Layer
- [ ] **Phase 6:** Archaeology (Git History, Diffs, & GitHub Issues/PRs)
- [ ] **Phase 7:** MLOps & Automation (n8n, Docker, & PostgreSQL + pgvector)
- [ ] **Phase 8:** Evaluation Dataset, Benchmarks, & v1.0 Release
