# Phase 1 Codebase Reference Guide

This document provides a complete breakdown of every file created in Phase 1 of **Archaeon**, explaining its purpose, internal functions/classes, and how it connects to the rest of the architecture.

---

## 📁 Directory Structure Overview

```text
software-archaeologist/
│
├── src/
│   ├── api/
│   │   ├── main.py
│   │   ├── routes/
│   │   │   ├── repository.py
│   │   │   └── jobs.py
│   │   └── schemas/
│   │       ├── repository.py
│   │       └── job.py
│   │
│   ├── database/
│   │   ├── engine.py
│   │   └── models.py
│   │
│   └── ingestion/
│       ├── git.py
│       └── repository.py
│
├── tests/
│   └── unit/
│       ├── test_api.py
│       ├── test_models.py
│       └── test_schemas.py
│
├── docs/
│   └── concepts/
│       ├── step1_llm_basics.md
│       ├── step2_fastapi_basics.md
│       ├── step3_sqlalchemy_basics.md
│       └── phase1_codebase_guide.md
│
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 1. Application Core & API Layer (`src/api/`)

### 📄 `src/api/main.py`
* **Purpose:** The entry point for the FastAPI web application.
* **Key Components:**
  - Instantiates the main `FastAPI` application object (`app`).
  - Calls `init_db()` to automatically create SQLite database tables on server startup.
  - Registers the API routers (`repositories_router` and `jobs_router`).
* **Connection:** Run by Uvicorn server (`uvicorn src.api.main:app --reload`).

---

### 📄 `src/api/routes/repository.py`
* **Purpose:** Contains all REST API endpoints for repository management.
* **Key Functions:**
  - `@router.post("")` (`create_repository`): Accepts a GitHub URL input, checks for duplicates in SQLite, creates a `pending` `Repository` record and a `queued` `Job` record, and triggers the background ingestion task (`BackgroundTasks`).
  - `@router.get("")` (`get_repositories`): Fetches a list of all repositories stored in the database.
  - `@router.get("/{repo_id}")` (`get_repository`): Retrieves details for a specific repository by its UUID.
* **Connection:** Uses `get_db` dependency to inject database sessions and calls `ingest_repository` in a background thread.

---

### 📄 `src/api/routes/jobs.py`
* **Purpose:** Contains endpoints for monitoring background task progress.
* **Key Functions:**
  - `@router.get("/{job_id}")` (`get_job`): Queries SQLite for a `Job` record by its UUID to return `status`, `progress` (0–100%), and any `error` message.
* **Connection:** Used by clients to poll task status after submitting a repository.

---

### 📄 `src/api/schemas/repository.py`
* **Purpose:** Pydantic v2 data validation models for repositories.
* **Key Classes:**
  - `RepositoryCreate`: Defines input shape when submitting a repo (`url: str`).
  - `RepositoryResponse`: Defines output JSON shape returned by API (`id`, `url`, `name`, `status`, `file_count`, `default_branch`, `clone_path`, timestamps).
* **Connection:** Validates inputs in `repository.py` routes and converts SQLAlchemy models into JSON via `ConfigDict(from_attributes=True)`.

---

### 📄 `src/api/schemas/job.py`
* **Purpose:** Pydantic v2 data validation model for background jobs.
* **Key Classes:**
  - `JobResponse`: Defines output JSON shape returned by `GET /jobs/{id}` (`id`, `repository_id`, `status`, `progress`, `error`, timestamps).
* **Connection:** Converts SQLAlchemy `Job` objects into JSON response payloads.

---

## 2. Database Layer (`src/database/`)

### 📄 `src/database/models.py`
* **Purpose:** Defines SQLite database tables as Python ORM classes using SQLAlchemy 2.0.
* **Key Classes:**
  - `Base`: Parent class inherited from `DeclarativeBase`.
  - `Repository`: Represents the `repositories` table (`id`, `url`, `name`, `status`, `file_count`, `default_branch`, `clone_path`, timestamps).
  - `Job`: Represents the `jobs` table (`id`, `repository_id` foreign key, `status`, `progress`, `error`, timestamps).
* **Connection:** Mapped directly to SQLite database rows in `archaeon.db`.

---

### 📄 `src/database/engine.py`
* **Purpose:** Sets up database connections and manages session lifecycles for FastAPI.
* **Key Components:**
  - `engine`: Creates SQLAlchemy engine pointing to `DATABASE_URL` (SQLite with `check_same_thread=False`).
  - `SessionLocal`: Session factory for instantiating database connections.
  - `init_db()`: Helper that executes `Base.metadata.create_all(bind=engine)`.
  - `get_db()`: Generator dependency yielding clean database sessions to API routes and auto-closing them.

---

## 3. Ingestion Engine Layer (`src/ingestion/`)

### 📄 `src/ingestion/git.py`
* **Purpose:** Low-level Git operations wrapper around `GitPython`.
* **Key Functions:**
  - `git_clone(repo_url, destination_path)`: Downloads a GitHub repository to local disk using `git.Repo.clone_from()`.
  - `git_extract_metadata(destination_path, repo)`: Extracts repository name from URL, counts non-git files, and detects default branch name.

---

### 📄 `src/ingestion/repository.py`
* **Purpose:** Orchestrator function for repository ingestion running in the background.
* **Key Function:**
  - `ingest_repository(repo_id, job_id, repo_url)`:
    1. Opens an isolated `SessionLocal()` database session.
    2. Updates `Job.status = "processing"` and `Repository.status = "processing"`.
    3. Calls `git_clone()` to download repo to `data/repos/<repo_id>`.
    4. Calls `git_extract_metadata()` to analyze repo structure.
    5. Updates `Repository` metadata and marks `Job.status = "completed"` (100% progress).
    6. Catches any errors, updates `Job.status = "failed"` and `Job.error`, and closes the session.

---

## 4. Test Suite Layer (`tests/unit/`)

### 📄 `tests/unit/test_schemas.py`
* **Purpose:** Verifies Pydantic schema validation for inputs and output serializations.

### 📄 `tests/unit/test_models.py`
* **Purpose:** Tests SQLAlchemy models and foreign key relationships using an isolated in-memory SQLite database (`sqlite:///:memory:`).

### 📄 `tests/unit/test_api.py`
* **Purpose:** Integration tests for FastAPI endpoints (`POST /repositories`, `GET /repositories`, `GET /repositories/{id}`, `GET /jobs/{id}`) using FastAPI's `TestClient`.

---

## 5. Configuration & Project Files

* **`.env` / `.env.example`:** Environment variable management (API keys, database URLs).
* **`.gitignore`:** Prevents committing `.venv`, `.env`, database files (`*.db`), and cloned repos (`data/repos/`).
* **`requirements.txt`:** Project dependencies (`fastapi`, `uvicorn`, `sqlalchemy`, `gitpython`, `pydantic`, `pytest`, `httpx`).
* **`README.md`:** Main project overview, setup guide, roadmap, and documentation index.
