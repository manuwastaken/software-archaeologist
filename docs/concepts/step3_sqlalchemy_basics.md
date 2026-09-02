# Step 3 — Database & SQLAlchemy Basics

This document explains how databases work, what an ORM is, and breaks down the exact code you implemented in `src/database/models.py` and `src/database/engine.py`.

---

## 1. What is a Database?

A database is a system for persistently storing and querying structured data.

### SQLite vs PostgreSQL

| Feature | SQLite | PostgreSQL |
|---|---|---|
| **What it is** | A single `.db` file on your computer | A standalone database server process |
| **Setup** | Zero setup (built into Python) | Requires installing and running a service / Docker container |
| **Best for** | Development, testing, desktop apps | High-concurrency production applications |
| **Role in Archaeon** | Phase 1–6 development database | Phase 7+ production database |

Because we use **SQLAlchemy**, switching from SQLite to PostgreSQL later only requires changing one line of configuration in `.env` (`DATABASE_URL`).

---

## 2. What is an ORM (Object-Relational Mapper)?

A database works with **Tables, Rows, and Columns**.
Python works with **Classes, Objects, and Attributes**.

An **ORM** translates between the two automatically:

```
Database World                     Python World
──────────────                     ────────────
Table: repositories      <===>     Class: Repository
Row in database          <===>     Instance of Repository (repo = Repository(...))
Column: url              <===>     Attribute: repo.url
```

Without an ORM, you would have to write raw SQL strings like:
`INSERT INTO repositories (id, url) VALUES ('123', 'https://...');`

With SQLAlchemy ORM, you work with pure Python:
`db.add(Repository(url="https://..."))`

---

## 3. Core SQLAlchemy Concepts

### `Base` (Declarative Base)
The parent class for all your database tables. It keeps track of all models defined in your code so SQLAlchemy knows what tables to create.

### `Engine`
The starting point for any SQLAlchemy application. It maintains the database connection pool and handles communication between Python and SQLite/PostgreSQL.

### `Session`
Represents a single workspace / transaction with the database. You open a session, perform operations (add, query, update, delete), commit the changes, and close the session.

---

## 4. Breakdown of `src/database/models.py`

This file defines the **structure (schema)** of your database tables using SQLAlchemy 2.0 type hints (`Mapped` and `mapped_column`).

### Table 1: `repositories`
Stores information about each ingested GitHub project.

Key elements:
- `id: Mapped[str]`: Primary key formatted as a unique UUID string (`uuid.uuid4()`).
- `url: Mapped[str]`: The GitHub repository URL (`unique=True`, `nullable=False`).
- `name`, `file_count`, `default_branch`, `clone_path`: Set to `nullable=True` because they are empty when a repo is first submitted and populated after cloning.
- `created_at` / `updated_at`: Automatically set timestamps using `datetime.now(timezone.utc)`.

### Table 2: `jobs`
Tracks background ingestion tasks.

Key elements:
- `repository_id: Mapped[str]`: A **Foreign Key** pointing to `repositories.id`. This establishes a relationship between a job and its repository.
- `status`: Tracking task progress (`'queued'`, `'processing'`, `'completed'`, `'failed'`).
- `progress`: Percentage complete (0–100).
- `error`: Stores error trace details if ingestion fails (`nullable=True`).

---

## 5. Breakdown of `src/database/engine.py`

This file handles **connecting to SQLite** and **managing database sessions for FastAPI**.

```python
# 1. Environment Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./archaeon.db")

# 2. Engine Creation
# connect_args={"check_same_thread": False} allows multi-threaded access in SQLite
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})

# 3. Session Factory
# SessionLocal creates new Session objects on demand
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. Helper Function to Create Tables
def init_db():
    Base.metadata.create_all(bind=engine)
```

### The `get_db()` Dependency Generator

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

FastAPI uses this function to give each API request its own clean database session. 
- When an API request comes in, `get_db()` opens a session (`db = SessionLocal()`).
- It `yield`s the session to your API route function.
- After the API route returns a response (or throws an error), the `finally` block runs and cleanly closes `db.close()`.

---

## Summary Flow

```
   HTTP Request (e.g., POST /repositories)
                     │
                     ▼
             FastAPI Route Function
                     │
                     ▼ injects session via get_db()
                SQLAlchemy Session
                     │
                     ▼ uses models (Repository, Job)
              SQLAlchemy Engine
                     │
                     ▼
           SQLite File (archaeon.db)
```
