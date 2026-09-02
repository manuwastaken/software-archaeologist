    # Step 2 — FastAPI Basics

FastAPI turns your Python functions into a server that other programs (frontends, tools,
users) can talk to over the internet.

This document explains what that means from the ground up.

---

## Quick Start

If you want the shortest working pattern:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/hello")
def say_hello():
    return {"message": "Hello Archeon"}
```

Run it with:

```bash
uvicorn fastApi_test:app --reload
```

If your file is named `main.py` instead, then use:

```bash
uvicorn main:app --reload
```

The pattern is always:

```bash
uvicorn <file_name_without_py>:<app_variable> --reload
```

---

## 1. What is a Server?

### Script vs Server

Right now your code is a script:

```
python llm_test.py
  → runs
  → does one fixed thing
  → exits
```

A server is different:

```
uvicorn main:app
  → starts
  → waits
  → receives request → handles it → sends response
  → waits
  → receives request → handles it → sends response
  → waits forever...
```

A server is a program that **sits and listens** for incoming requests and handles them
one by one (or many at once).

When you use a website, your browser is sending requests to a server. The server handles
them and sends back HTML, JSON, images, etc.

---

## 2. HTTP — The Language of the Web

Servers and clients communicate using **HTTP** (HyperText Transfer Protocol).

Think of HTTP as an agreed format for messages, like a formal letter format:

```
REQUEST (client → server)
──────────────────────────
Method:  POST
URL:     /repositories
Body:    { "url": "https://github.com/example/project" }


RESPONSE (server → client)
──────────────────────────
Status:  200 OK
Body:    { "repository_id": "abc123", "status": "queued" }
```

You have already used HTTP without realising it — when `genai.Client` talks to Google's
servers, it is sending HTTP requests under the hood.

---

## 3. HTTP Methods

Every HTTP request has a **method** that describes the intention.

| Method | Meaning | Example |
|--------|---------|---------|
| `GET` | Fetch something (read-only) | Get list of repositories |
| `POST` | Create something new | Add a new repository |
| `PUT` | Replace something entirely | Update a repository |
| `PATCH` | Update part of something | Change a repository's name |
| `DELETE` | Remove something | Delete a repository |

### In plain terms

```
GET    /repositories        → "give me all my repositories"
POST   /repositories        → "here is a new repository, please add it"
GET    /repositories/abc123 → "give me the repository with id abc123"
DELETE /repositories/abc123 → "remove the repository with id abc123"
```

This is called a **REST API** — a standard way of designing URLs and methods so that
anyone can understand the API without reading the code.

---

## 4. Endpoints

An **endpoint** is one specific URL + method combination that your server handles.

```
POST   /repositories          ← endpoint 1
GET    /repositories          ← endpoint 2
GET    /repositories/{id}     ← endpoint 3
POST   /repositories/{id}/query ← endpoint 4
```

Each endpoint is a separate Python function in FastAPI.

---

## 5. Your First FastAPI Server

```python
from fastapi import FastAPI

app = FastAPI()           # create the application


@app.get("/hello")        # attach this function to GET /hello
def say_hello():
    return {"message": "Hello, world"}
```

That is the entire server. When someone sends a GET request to `/hello`, FastAPI calls
`say_hello()` and sends back the dictionary as JSON automatically.

### Running it

```bash
uvicorn main:app --reload
```

- `main` → the filename (`main.py`)
- `app` → the FastAPI object inside the file
- `--reload` → restart automatically when you edit the file (useful during development)

Your server is now running at:

```
http://localhost:8000
```

Visit `http://localhost:8000/hello` in a browser and you see:

```json
{ "message": "Hello, world" }
```

---

## 6. Automatic Interactive Documentation

This is one of FastAPI's best features.

Visit:

```
http://localhost:8000/docs
```

FastAPI automatically generates a page where you can:
- See all your endpoints listed
- Read what each one expects
- Send real requests and see real responses
- Without writing a single line of documentation

This is called **Swagger UI**. It is generated from your Python code automatically.

---

## 7. Path Parameters

Sometimes part of the URL is a variable — an ID, a name, something that changes.

```python
@app.get("/repositories/{repo_id}")
def get_repository(repo_id: str):
    return {"repo_id": repo_id}
```

Now:
- `GET /repositories/abc123` → `repo_id = "abc123"`
- `GET /repositories/xyz789` → `repo_id = "xyz789"`

The `{repo_id}` in the URL and `repo_id: str` in the function are connected automatically.

---

## 8. Query Parameters

Query parameters are extra options added to the URL after a `?`.

```
GET /repositories?language=python&limit=10
```

In FastAPI:

```python
@app.get("/repositories")
def list_repositories(language: str = None, limit: int = 10):
    return {"language": language, "limit": limit}
```

FastAPI reads them from the URL and passes them as function arguments automatically.
If a parameter has a default value (like `limit: int = 10`), it is optional.

---

## 9. Request Body

For `POST` and `PUT` requests, the data goes in the **request body** — not the URL.

The URL would get too long and messy for complex data.

```
POST /repositories
Content-Type: application/json

{
    "url": "https://github.com/example/project",
    "branch": "main"
}
```

In FastAPI, you define the expected shape using a **Pydantic model**:

```python
from pydantic import BaseModel

class RepositoryCreate(BaseModel):
    url: str
    branch: str = "main"    # optional, defaults to "main"


@app.post("/repositories")
def create_repository(data: RepositoryCreate):
    print(data.url)         # "https://github.com/example/project"
    print(data.branch)      # "main"
    return {"status": "queued"}
```

FastAPI automatically:
- Reads the JSON from the request body
- Validates it against your Pydantic model
- Passes it to your function already parsed
- Returns a helpful error if the data is wrong

This is why `pydantic` was already in your `requirements.txt`.

---

## 10. Pydantic Models

Pydantic lets you define the **shape** of data using Python classes and type hints.

```python
from pydantic import BaseModel
from typing import Optional

class Repository(BaseModel):
    id: str
    url: str
    name: str
    language: Optional[str] = None   # might not be known yet
    status: str = "pending"
```

FastAPI uses these models for:
- **Input** — validating what comes in (request body)
- **Output** — defining what your response looks like

If the incoming data is wrong (missing a required field, wrong type), FastAPI returns a
clear error automatically without you writing any validation code.

---

## 11. Status Codes

HTTP responses include a **status code** — a number that says whether the request
succeeded or failed.

| Code | Meaning |
|------|---------|
| `200` | OK — success |
| `201` | Created — new resource was created |
| `400` | Bad Request — the client sent invalid data |
| `401` | Unauthorized — not authenticated |
| `404` | Not Found — the resource does not exist |
| `422` | Unprocessable Entity — validation failed (FastAPI uses this automatically) |
| `500` | Internal Server Error — something went wrong on the server |

FastAPI returns `200` by default. You can set others explicitly:

```python
from fastapi import HTTPException

@app.get("/repositories/{repo_id}")
def get_repository(repo_id: str):
    repo = find_in_database(repo_id)

    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    return repo
```

---

## 12. Async (Non-blocking)

FastAPI supports `async` functions natively.

```python
@app.post("/repositories/{id}/query")
async def query_repository(id: str, question: str):
    answer = await ask_llm(question)   # waits for LLM without blocking
    return {"answer": answer}
```

This matters because LLM calls take 2–10 seconds. Without `async`, your server would
be frozen, unable to handle any other requests while waiting for the LLM to respond.

With `async`, FastAPI can handle other requests while waiting. This is important for
Archaeon where queries involve multiple sequential LLM and database calls.

You do not need to fully understand async yet — just know that `async def` instead of
`def` is the right choice for functions that call external services.

---

## 13. Putting It Together — Archaeon's First Endpoint

Based on the spec, the first real endpoint you will build:

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class RepositoryRequest(BaseModel):
    url: str                    # "https://github.com/example/project"


class RepositoryResponse(BaseModel):
    repository_id: str
    status: str


@app.post("/repositories", response_model=RepositoryResponse, status_code=201)
async def add_repository(data: RepositoryRequest):
    # 1. validate the URL (is it a real GitHub URL?)
    # 2. save to database
    # 3. queue a background job to clone + analyze
    # 4. return the job ID so the client can check progress

    return RepositoryResponse(
        repository_id="abc123",
        status="queued"
    )
```

Request:

```http
POST /repositories
{ "url": "https://github.com/example/project" }
```

Response:

```json
{
  "repository_id": "abc123",
  "status": "queued"
}
```

---

## 14. Complete Minimal Server Example

```python
# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Archaeon API", version="0.1.0")


# --- models ---

class QuestionRequest(BaseModel):
    question: str

class QuestionResponse(BaseModel):
    answer: str
    model_used: str


# --- endpoints ---

@app.get("/health")
def health_check():
    """Check if the server is running."""
    return {"status": "ok"}


@app.post("/ask", response_model=QuestionResponse)
async def ask_question(data: QuestionRequest):
    """Send a question to the LLM and get an answer."""
    if not data.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # (call LLM here)
    answer = "This is a placeholder answer."

    return QuestionResponse(
        answer=answer,
        model_used="gemini-3.6-flash"
    )
```

Run with:

```bash
uvicorn main:app --reload
```

Then open `http://localhost:8000/docs` and you can test both endpoints immediately.

---

## Summary

| Concept | What it means |
|---|---|
| **Server** | A program that runs continuously and handles requests |
| **HTTP** | The agreed format for requests and responses |
| **Method** | GET = read, POST = create, PUT = replace, DELETE = remove |
| **Endpoint** | One URL + method handled by one Python function |
| **Path parameter** | Variable part of the URL (`/repos/{id}`) |
| **Query parameter** | Optional filters in the URL (`?limit=10`) |
| **Request body** | Data sent with POST/PUT requests (JSON) |
| **Pydantic model** | Python class that defines and validates data shapes |
| **Status code** | Number indicating success (200) or failure (404, 500) |
| **Async** | Non-blocking functions for slow operations (LLM calls, DB queries) |

---

## How FastAPI fits into Archaeon

```
Streamlit UI
    |
    | POST /repositories/{id}/query
    |   { "question": "Why was Redis introduced?" }
    v
FastAPI                  ← you are building this layer
    |
    | routes request to...
    v
Agent Layer
    |
    | uses tools to gather evidence...
    v
LLM
    |
    | generates answer...
    v
FastAPI
    |
    | sends back...
    v
Streamlit UI
    |
    | displays answer + evidence
```

FastAPI is the stable, documented front door of the entire system. Every other component
(agent, retrieval, graph, database) is hidden behind it.
