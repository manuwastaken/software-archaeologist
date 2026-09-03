# Phase 2 — Code Intelligence & Static Analysis Guide

This document provides a complete conceptual and technical breakdown of Phase 2 of **Archaeon**, explaining how Python source code is parsed into Abstract Syntax Trees (AST), stored in SQLite, and exposed via REST API endpoints.

---

## 📌 Phase 2 Overview

While Phase 1 focused on cloning repositories and tracking background job status, **Phase 2 establishes structural Code Intelligence**:

1. **AST Parsing Engine:** Uses Python's native `ast` module and `NodeVisitor` pattern to extract classes, functions, methods, and imports without running the repository's code.
2. **Database Expansion:** Adds `files` and `symbols` relational tables linked to `repositories`.
3. **Ingestion Loop Integration:** Scans cloned repositories for `.py` files, extracts symbols file-by-file, bulk-inserts symbol records into SQLite, and provides dynamic job progress updates (50% ➔ 90%).
4. **REST API Endpoints:** Exposes endpoints to query all files and extracted code symbols (classes, functions, methods, imports) for any ingested repository.

---

## 📁 Updated Directory Structure

```text
software-archaeologist/
│
├── src/
│   ├── analysis/
│   │   ├── __init__.py
│   │   └── ast_parser.py        ← AST SymbolVisitor & file parser
│   │
│   ├── api/
│   │   ├── main.py
│   │   ├── routes/
│   │   │   ├── repository.py    ← Updated with /files & /symbols GET endpoints
│   │   │   └── jobs.py
│   │   └── schemas/
│   │       ├── ast.py           ← FileResponse & SymbolResponse Pydantic schemas
│   │       ├── repository.py
│   │       └── job.py
│   │
│   ├── database/
│   │   ├── engine.py
│   │   └── models.py          ← Updated with File & Symbol ORM models
│   │
│   └── ingestion/
│       ├── git.py               ← Added locate_py() helper function
│       └── repository.py        ← Updated ingestion loop for AST parsing
│
├── docs/
│   └── concepts/
│       ├── step1_llm_basics.md
│       ├── step2_fastapi_basics.md
│       ├── step3_sqlalchemy_basics.md
│       ├── phase1_codebase_guide.md
│       └── phase2_codebase_guide.md
```

---

## 1. AST Parser Engine (`src/analysis/ast_parser.py`)

### `SymbolVisitor(NodeVisitor)` Class
A single visitor class inheriting from Python's `ast.NodeVisitor` that traverses Abstract Syntax Trees and extracts code entities:

- **`visit_ClassDef(node)`**: Triggers on `class ...:`. Extracts class name, docstring, base classes (inheritance via `ast.unparse`), and line numbers (`start_line`, `end_line`). Tracks `current_class` context for nested methods.
- **`visit_FunctionDef(node)`**: Triggers on `def ...():`. Inspects `current_class` context to determine if the symbol is a standalone `"function"` or a `"method"`. Extracts argument names via `ast.unparse`, parent class, docstring, and line range.
- **`visit_Import(node)`**: Triggers on `import ...`. Extracts imported module names.
- **`visit_ImportFrom(node)`**: Triggers on `from ... import ...`. Handles module names and relative imports cleanly.

### `parse_python_file(file_path)` Helper Function
- Opens a single Python file with `encoding="utf-8"`.
- Builds the syntax tree using `ast.parse()`.
- Runs `SymbolVisitor()` and returns a dictionary: `{"classes": [...], "functions": [...], "imports": [...]}`.
- Includes `try/except` error handling to catch `SyntaxError` or `UnicodeDecodeError` gracefully without crashing the server.

---

## 2. Database Schema Expansion (`src/database/models.py`)

Two new SQLAlchemy 2.0 ORM tables were added with foreign key relationships:

### `File` Model (`files` table)
- `id`: UUID Primary Key string.
- `repository_id`: Foreign Key pointing to `repositories.id`.
- `path`: Relative file path (e.g. `"src/database/engine.py"`).
- `file_size`: File size in bytes.
- `line_count`: Total line count of the file.
- `created_at`: UTC Timestamp.
- **Relationships:** `repository` (`File` $\rightarrow$ `Repository`), `symbols` (`File` $\rightarrow$ `list[Symbol]` with `cascade="all, delete-orphan"`).

### `Symbol` Model (`symbols` table)
- `id`: UUID Primary Key string.
- `file_id`: Foreign Key pointing to `files.id`.
- `name`: Symbol identifier (e.g. `"UserRepository"`, `"get_db"`).
- `symbol_type`: Type discriminator (`"class"`, `"function"`, `"method"`, `"import"`).
- `parent_class`: Name of parent class if method (`nullable=True`).
- `start_line` / `end_line`: Code boundary line numbers.
- `docstring`: Extracted docstring text (`Text`, `nullable=True`).
- `metadata_json`: Extra structural metadata stored as JSON (`{"base_classes": [...]}` or `{"args": [...]}`).
- **Relationship:** `file` (`Symbol` $\rightarrow$ `File`).

---

## 3. Ingestion Loop Integration (`src/ingestion/`)

### `src/ingestion/git.py`
- **`locate_py(repo_path)`**: Uses `os.walk()` to recursively search for `.py` files while explicitly skipping `.git`, `.venv`, and `__pycache__` directories.

### `src/ingestion/repository.py`
- After Git cloning completes (50% progress):
  1. Finds all `.py` files using `locate_py()`.
  2. Iterates over each `.py` file, calculates relative paths, line count, and byte size.
  3. Inserts a `File` record in SQLite and refreshes `file.id`.
  4. Parses file AST using `parse_python_file()`.
  5. Builds `Symbol` objects for classes, functions, methods, and imports.
  6. Bulk-inserts symbols using `db.add_all(symbols_to_create)`.
  7. Updates `job.progress` dynamically from 50% ➔ 85%.
  8. Finalizes metadata and sets `job.progress = 100` and `repo.status = "completed"`.

---

## 4. API Schemas & Endpoints (`src/api/`)

### `src/api/schemas/ast.py`
Pydantic v2 validation models with `ConfigDict(from_attributes=True)`:
- `FileResponse`: Returns file details (`id`, `repository_id`, `path`, `file_size`, `line_count`, `created_at`).
- `SymbolResponse`: Returns symbol details (`id`, `file_id`, `name`, `symbol_type`, `parent_class`, `start_line`, `end_line`, `docstring`, `metadata_json`).

### `src/api/routes/repository.py`
- **`GET /repositories/{id}/files`**: Returns list of all files in a repository (`list[FileResponse]`).
- **`GET /repositories/{id}/symbols`**: Joins `Symbol` with `File` (`db.query(Symbol).join(File).filter(File.repository_id == id).all()`) to return all extracted symbols for a repository (`list[SymbolResponse]`).

---

## 🧪 Summary Flow

```text
                  POST /repositories (User submits GitHub URL)
                                     │
                                     ▼
                        Phase 1: Git Clone Engine
                                     │
                                     ▼
                   Phase 2: locate_py() & AST Parser
                                     │
                        ┌────────────┴────────────┐
                        ▼                         ▼
              File Metadata Saved       Symbols Extracted & Saved
             (files table in SQLite)    (symbols table in SQLite)
                                     │
                                     ▼
             GET /repositories/{id}/files & GET /repositories/{id}/symbols
                   (Inspect extracted code structure in Swagger UI)
```
