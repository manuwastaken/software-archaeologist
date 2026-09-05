# Phase 4: Session Chat Endpoints

This document describes the repository session and conversational chat endpoints used by the Archaeon API.

## 1. Create a new chat session

### POST /repositories/{id}/sessions

Creates a new `ChatSession` for a completed repository.

#### Request
- Path parameter:
  - `id`: repository UUID

#### Behavior
- Validates that the repository exists.
- Validates that the repository status is `completed`.
- Creates a new `ChatSession` record in SQLite.
- Returns a `ChatSessionResponse` payload.

#### Success response
```json
{
  "id": "<session_uuid>",
  "repository_id": "<repo_uuid>",
  "created_at": "2026-09-05T12:00:00Z"
}
```

#### Errors
- `404 Not Found` if repository does not exist.
- `400 Bad Request` if repository is not completed yet.

---

## 2. List all sessions for a repository

### GET /repositories/{id}/sessions

Returns every chat session associated with a repository.

#### Request
- Path parameter:
  - `id`: repository UUID

#### Behavior
- Queries `ChatSession` rows where `ChatSession.repository_id == id`.
- Returns a list of `ChatSessionResponse` objects.

#### Example response
```json
[
  {
    "id": "<session_uuid>",
    "repository_id": "<repo_uuid>",
    "created_at": "2026-09-05T12:00:00Z"
  }
]
```

#### Errors
- `404 Not Found` if repository is not found.

---

## 3. Fetch full chat history for a session

### GET /sessions/{session_id}/messages

Returns all stored messages for a given session in chronological order.

#### Request
- Path parameter:
  - `session_id`: session UUID

#### Behavior
- Validates that the session exists.
- Queries all `Message` records for that session.
- Orders messages by `created_at`.
- Returns `list[MessageResponse]`.

#### Example response
```json
[
  {
    "id": "<message_uuid>",
    "role": "user",
    "content": "Explain this code path.",
    "citation_json": null,
    "created_at": "2026-09-05T12:05:00Z"
  },
  {
    "id": "<message_uuid>",
    "role": "assistant",
    "content": "This function loads the repository and processes it.",
    "citation_json": [
      {
        "file_path": "src/repository.py",
        "symbol_name": "load_repository",
        "start_line": 10,
        "end_line": 40,
        "similarity_score": 0.92
      }
    ],
    "created_at": "2026-09-05T12:05:30Z"
  }
]
```

#### Errors
- `404 Not Found` if session is not found.

---

## 4. Send a message and get a grounded answer

### POST /sessions/{session_id}/chat

Sends a new user message in a chat session and returns the assistant response using the conversational RAG service.

#### Request
- Path parameter:
  - `session_id`: session UUID
- JSON body:
```json
{
  "message": "What does this repository do?",
  "top_k": 4
}
```

#### Behavior
- Loads the `ChatSession` from SQLite and raises `404` if missing.
- Loads the associated repository and validates it is `completed`.
- Fetches the last 6 messages for the session.
- Converts them into LangChain message objects:
  - `role == "user"` → `HumanMessage(content=...)`
  - `role == "assistant"` → `AIMessage(content=...)`
- Calls `conversational_rag_service.chat(repo_id, message, chat_history, top_k)`.
- Saves the user message and assistant response as two `Message` rows in SQLite.
- Returns `ChatResponse`.

#### Example response
```json
{
  "session_id": "<session_uuid>",
  "user_message": {
    "id": "<message_uuid>",
    "role": "user",
    "content": "What does this repository do?",
    "citation_json": null,
    "created_at": "2026-09-05T12:10:00Z"
  },
  "assistant_message": {
    "id": "<message_uuid>",
    "role": "assistant",
    "content": "This repository ingests and analyzes code structure.",
    "citation_json": [
      {
        "file_path": "src/ingestion/repository.py",
        "symbol_name": "ingest_repository",
        "start_line": 15,
        "end_line": 33,
        "similarity_score": 0.89
      }
    ],
    "created_at": "2026-09-05T12:10:01Z"
  },
  "citations": [
    {
      "file_path": "src/ingestion/repository.py",
      "symbol_name": "ingest_repository",
      "start_line": 15,
      "end_line": 33,
      "similarity_score": 0.89
    }
  ]
}
```

#### Errors
- `404 Not Found` if session does not exist.
- `404 Not Found` if repository is missing.
- `400 Bad Request` if repository is not completed yet.

---

## Notes

These endpoints rely on the SQLite-backed models defined in the project:
- `Repository`
- `ChatSession`
- `Message`

The chat endpoint uses the conversational RAG pipeline to generate grounded responses from repository code context while retaining recent chat history for multi-turn follow-up questions.
