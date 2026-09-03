# 🏛️ Archaeon — AI Software Archaeologist
> An AI-powered software intelligence system combining semantic retrieval, static code analysis, dependency graphs, and Git history to explain **how** and **why** software systems evolve.
---
## 📌 Phase 1 — Foundations (Completed)
Phase 1 establishes the core backend architecture and repository ingestion pipeline:
- ⚡ **FastAPI Web Framework:** Modular REST API with `APIRouter`, Pydantic v2 validation, and OpenAPI documentation (`/docs`).
- 🗄️ **SQLAlchemy 2.0 ORM & SQLite:** Persistent storage for repositories and background job tracking.
- 🔄 **Asynchronous Ingestion Engine:** Background repository cloning and metadata extraction using `GitPython` and FastAPI `BackgroundTasks`.
- 🧪 **Automated Testing:** Unit test suite covering models, schemas, and API endpoints using `pytest` and `TestClient`.
- 📚 **Study Guides & Documentation:** Comprehensive architectural concepts documented under `docs/concepts/`.

## 🧠 Phase 2 — Code Intelligence & Static Analysis (Completed)
Phase 2 adds structural analysis of Python source code during repository ingestion:
- 🌳 **AST Parser:** Uses Python's built-in `ast` module and `NodeVisitor` to extract classes, inheritance, functions, methods, imports, docstrings, arguments, and source line ranges without executing repository code.
- 📄 **File Metadata:** Recursively discovers Python files while skipping `.git`, `.venv`, and `__pycache__` directories, then stores paths, sizes, and line counts.
- 🔗 **Symbol Storage:** Adds `files` and `symbols` tables linked to repositories, including relationships, symbol types, parent classes, and structural metadata.
- 📊 **Ingestion Progress:** Parses and stores code file-by-file while updating background job progress from cloning through finalization.
- 🔍 **Code Inspection API:** Provides endpoints for querying the files and extracted symbols belonging to an ingested repository.
---
## 🚀 Quick Start
### 1. Installation
```bash
# Clone Archaeon repository
git clone https://github.com/manuwastaken/software-archaeologist.git
cd software-archaeologist
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows PowerShell
# Install dependencies
pip install -r requirements.txt
```

### 2. Run the API Server
```bash
uvicorn src.api.main:app --reload
```
Interactive API Documentation (Swagger UI) is available at: 👉 http://127.0.0.1:8000/docs

📡 API Endpoints
Method	Endpoint	Description	Status Code
POST	/repositories	Submit a GitHub repository URL for ingestion	201 Created
GET	/repositories	List all ingested repositories	200 OK
GET	/repositories/{id}	Get metadata for a specific repository	200 OK
GET	/repositories/{id}/files	List files discovered during ingestion	200 OK
GET	/repositories/{id}/symbols	List classes, functions, methods, and imports	200 OK
GET	/jobs/{id}	Check background ingestion job progress	200 OK
🧪 Running Unit Tests
```bash
python -m pytest tests/unit -v
```
📖 Study Material & Concept Guides
Detailed documentation for learning backend concepts built into this project:

docs/concepts/step1_llm_basics.md
 — API, Keys, Models, Prompts, Responses, and Tokens.
docs/concepts/step2_fastapi_basics.md
 — HTTP, REST, FastAPI endpoints, Pydantic, and Async.
docs/concepts/step3_sqlalchemy_basics.md
 — ORM, Engine, Sessions, Base, Models, and SQLite.
🗺️ Project Roadmap
 Phase 1: API Skeleton, SQLite Database, Git Ingestion Engine, & Unit Tests (Completed)
 Phase 2: Code Intelligence (Python AST Parsing & Symbol Extraction) (Completed)
 Phase 3: RAG System (Embeddings, Vector Search, & Reranking)
 Phase 4: LangChain Integration
 Phase 5: Tool-Using Agent Layer
 Phase 6: Archaeology (Git History, Diffs, & GitHub Issues/PRs)
 Phase 7: MLOps & Automation (n8n, Docker, & PostgreSQL + pgvector)
 Phase 8: Evaluation Dataset, Benchmarks, & v1.0 Release