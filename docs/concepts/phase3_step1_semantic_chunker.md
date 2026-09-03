# Phase 3 — Step 1: Semantic Code Chunking Guide

This document explains the conceptual foundations, architectural design, and operational details of the **Semantic Code Chunker** (`src/rag/chunker.py`) in **Archaeon**.

---

## 1. The Core Problem: Why Naive Document RAG Fails for Code

Traditional RAG systems designed for prose documents (PDFs, Markdown, news articles) use **fixed-window chunking**:
> *"Take all text in a file. Split every 500 characters or 300 words with a 50-character overlap."*

Applying this to source code produces catastrophic failures:

```python
# --- CHUNK 1 ENDS HERE (at arbitrary character limit) ---
    def calculate_compound_interest(principal: float, rate: float, years: int) -> float:
        rate_factor = (1 + rate / 100)
# --- CHUNK 2 STARTS HERE ---
        return principal * (rate_factor ** years)
```

### Consequences:
1. **Broken Syntax & Logic:** The function definition, argument types, and return types are in Chunk 1; the mathematical calculation and return statement are in Chunk 2. Neither chunk contains the complete logical thought.
2. **Contextual Blindness:** Chunk 2 has no idea what function it belongs to, what file it lives in, or what `rate_factor` represents.
3. **Retrieval Degradation:** When a user queries *"How is interest computed?"*, Chunk 2 might match on `principal * (rate_factor ** years)`, but the model cannot determine what arguments were expected or what function it is.

---

## 2. Archaeon’s Strategy: AST-Driven Semantic Chunking

Because Archaeon performs **Abstract Syntax Tree (AST) parsing in Phase 2**, every class, function, method, docstring, and line boundary is already indexed in SQLite.

The **Semantic Chunker** uses this structural knowledge to slice code strictly along **natural syntax boundaries**:
- Every function is chunked from its `def` line to its final line, including decorators, docstrings, and return statements.
- Every class method is chunked as an independent unit and stamped with its parent class name.
- Every file produces an overview chunk capturing module-level imports and global variables.

---

## 3. The 3 Distinct Semantic Chunk Types

To ensure 100% of a Python file is represented without redundancy, Archaeon produces three specific chunk types:

| Chunk Type | Extraction Scope | Why It Is Essential |
| :--- | :--- | :--- |
| **`file_overview`** | Top lines of the file (up to line 50) before the first `class` or `def`. | Captures module docstrings, `import` statements, global configurations, and constants (e.g. `DATABASE_URL = ...`). |
| **`class` (Summary)** | Slices from `symbol.start_line` up to `first_method_start - 1`. | Captures `class Name(Bases):`, class docstring, and class attributes without duplicating the bodies of its child methods. |
| **`function` / `method`** | Slices the entire `def` block from `symbol.start_line` to `symbol.end_line`. | Delivers 100% signal for algorithmic logic. Methods are explicitly tagged with `Parent Class: {symbol.parent_class}`. |

---

## 4. The Contextual Header Architecture

If you pass raw code to an embedding model or an LLM:
```python
def save(self):
    self.db.commit()
```
Neither the embedding vector nor the LLM knows **what file** this lives in, **what class** it belongs to, or **what line numbers** to cite.

### The Archaeon Context Header
Before embedding, the chunker prepends a standardized natural language header directly to the text of every chunk:

```text
File: src/database/repository.py
Symbol: save (method)
Parent Class: UserRepository
Lines: 45-47

def save(self):
    self.db.commit()
```

### Why Prepending Headers Solves RAG Blindness:
1. **Semantic Search Boost:** The embedding vector captures both the code syntax AND the file path/symbol semantics simultaneously.
2. **Zero Ambiguity:** The LLM immediately knows the file path and line numbers when generating citations.
3. **Hierarchy Awareness:** Methods are never orphaned from their parent classes.

---

## 5. The `CodeChunk` Data Structure

Every chunk is encapsulated in a strongly-typed Python dataclass (`src/rag/chunker.py`):

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class CodeChunk:
    chunk_id: str             # Unique ID: e.g. "{file_id}_{symbol_id}" or "{file_id}_overview"
    content: str              # Context Header + Code Snippet (used for embeddings & LLM prompt)
    metadata: dict[str, Any]  # Filterable properties stored in ChromaDB for search & citations
```

### Stored Metadata Fields:
- `repository_id`: Isolates search to a specific repository.
- `file_id`: UUID foreign key to SQLite `files.id`.
- `file_path`: Relative file path (e.g. `src/database/engine.py`).
- `symbol_name`: Identifier name (e.g. `get_db`, `UserRepository`, or `None` for overviews).
- `symbol_type`: Discrimination tag (`"class"`, `"function"`, `"method"`, `"file_overview"`).
- `parent_class`: Parent class name for methods (or `None`).
- `start_line` & `end_line`: Exact source line numbers.

---

## 6. Slicing Mechanics & Index Alignment

A critical detail in code chunking is aligning Python's **0-indexed list operations** with AST's **1-indexed line numbers**:

- AST reports: Line 1 = First line of the file.
- Python list indexing: `lines[0]` = First line of the file.

```python
# To slice lines from symbol.start_line to symbol.end_line:
start_idx = max(0, symbol.start_line - 1)
end_idx = min(len(lines), symbol.end_line)
code_snippet = "".join(lines[start_idx:end_idx]).strip()
```

This guarantees byte-perfect code extraction with zero index off-by-one errors.
