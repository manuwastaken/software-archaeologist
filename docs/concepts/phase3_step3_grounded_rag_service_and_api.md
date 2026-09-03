# Phase 3 — Step 3: Grounded RAG Service & REST API Guide

This document explains the conceptual foundations, prompt engineering strategy, ingestion pipeline integration, and API architecture of the **Grounded RAG Service** (`src/rag/service.py`) and **Query Endpoint** (`src/api/routes/repository.py`) in **Archaeon**.

---

## 1. The Ingestion Pipeline Integration (`src/ingestion/repository.py`)

In Phase 3, the background repository ingestion task was updated to automatically execute the full RAG indexing lifecycle:

```text
 0% ──────────────────────────► 50% ──────────────────────────► 85% ──────────────────► 95% ──────────► 100%
[Git Clone & Folder Setup]      [AST File & Symbol Extraction]   [Chunk, Embed & Index]   [Metadata]     [Complete]
```

### The Ingestion Sequence:
1. **Git Clone:** Clones remote repository into `data/repos/{repo_id}` (Progress: 0% ➔ 50%).
2. **AST Parsing & Database Population:** Discovers `.py` files, parses AST syntax trees, inserts `File` and `Symbol` records into SQLite, and commits (Progress: 50% ➔ 85%).
3. **Semantic Chunking:** Calls `CodeChunker.chunk_file(file, destination_path)` for each file.
4. **Concurrent Embedding & ChromaDB Indexing:**
   ```python
   if all_chunks:
       embedding_service = GeminiEmbeddingService()
       v_store = ChromaVectorStore()
       embeddings = embedding_service.embed_documents([c.content for c in all_chunks])
       v_store.add_chunks(all_chunks, embeddings)
   ```
   (Progress advances to 95%).
5. **Finalize:** Extracts repository file count, default branch, sets status to `"completed"` and job progress to 100%.

---

## 2. Grounded RAG Engine Workflow (`src/rag/service.py`)

When a user queries a repository, the `RAGService` orchestrates the retrieval, prompt augmentation, and generative response:

```text
User Question ──► Embed Query (3072-dim) ──► ChromaDB Vector Search (Top-K)
                                                           │
                                                           ▼
                                            Retrieved Chunks + Question
                                                           │
                                                           ▼
                                            Prompt Construction (Anti-Hallucination)
                                                           │
                                                           ▼
                                            Gemini 2.5 Flash Generation
                                                           │
                                                           ▼
                                            Structured Response (Answer + Citations)
```

### Steps Executed in `answer_question(repository_id, question, top_k)`:
1. **Query Vectorization:** Calls `self.embedding_service.embed_query(question)` with `task_type="RETRIEVAL_QUERY"`.
2. **Filtered Nearest-Neighbor Search:** Calls `self.vector_store.search(...)` with `repository_id` hard filter.
3. **Empty Result Guard:** If no chunks match, returns an informative message rather than letting the LLM speculate.
4. **Context Block Assembly:** Formats matches into clean snippet blocks preserving file headers and line ranges.
5. **Prompt Engineering & Anti-Hallucination Guardrails:**
   The prompt enforces 4 strict rules:
   - *Rule 1:* Ground the answer **only** in the provided code snippets.
   - *Rule 2:* Explicitly cite file paths and line ranges (e.g. `[src/auth.py:12-25]`).
   - *Rule 3:* If the provided snippets do not contain the answer, explicitly state that the answer is not present. Do not guess.
   - *Rule 4:* Format output in clean GitHub Markdown.
6. **Inference with Gemini 2.5 Flash:** Dispatches prompt to `gemini-2.5-flash` for high-speed, accurate code explanation.
7. **Structured Citation Generation:** Maps chunk metadata and similarity scores to `Citation` schemas.

---

## 3. API Schemas & REST Endpoint

### Schemas (`src/api/schemas/rag.py`):
- **`QueryRequest`:** `question: str`, `top_k: int = 5`
- **`Citation`:** `file_path: str`, `symbol_name: str | None`, `start_line: int`, `end_line: int`, `similarity_score: float`
- **`QueryResponse`:** `answer: str`, `citations: list[Citation]`

### Route (`src/api/routes/repository.py`):
- **Method:** `POST /repositories/{id}/query`
- **Validation Checks:**
  1. Validates that the repository exists (404 if missing).
  2. Validates that `repo.status == "completed"` (400 if still processing, ensuring users don’t query unindexed code).
  3. Returns `QueryResponse` with status 200 OK.

---

## 4. Real-World Output Example

**Query:** *"How is word similarity or vector calculation handled?"*

```json
{
  "answer": "Word similarity and vector calculations are handled across evaluation utilities and the model's forward pass as follows:\n\n### 1. Finding Similar Words\nIn `get_similar_words`, cosine similarity is computed between a given target word and all words in the vocabulary [word2vec\\eval.py:6-24]:\n\n1. **Embedding Normalization**: The model's target embeddings (`model.v_embeddings`) are retrieved and normalized using L2 normalization (`p=2`) via `F.normalize` [word2vec\\eval.py:11-12].\n2. **Target Vector Retrieval**: The target word index is looked up in `word2idx`, and its normalized vector is isolated [word2vec\\eval.py:14-15].\n3. **Cosine Similarity**: Matrix multiplication (`torch.mm`) is performed between the normalized target vector and the transpose of all normalized embeddings [word2vec\\eval.py:17].\n4. **Top Results**: `torch.topk` fetches the top matches, excludes the target word itself, and returns `top_k` pairs of `(word, similarity_score)` [word2vec\\eval.py:18-24].\n\n### 2. Solving Analogies ($A : B :: C : ?$)\nIn `solve_analogy`, vector arithmetic is used to solve word analogies (e.g., $vec_B - vec_A + vec_C$) [word2vec\\eval.py:26-52]...",
  "citations": [
    {
      "file_path": "word2vec\\eval.py",
      "symbol_name": "get_similar_words",
      "start_line": 6,
      "end_line": 24,
      "similarity_score": 0.7234
    },
    {
      "file_path": "word2vec\\eval.py",
      "symbol_name": "solve_analogy",
      "start_line": 26,
      "end_line": 52,
      "similarity_score": 0.7163
    },
    {
      "file_path": "word2vec\\model.py",
      "symbol_name": "forward",
      "start_line": 21,
      "end_line": 33,
      "similarity_score": 0.6996
    }
  ]
}
```
