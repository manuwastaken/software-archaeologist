import uuid
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

def test_create_and_get_repository():
    """Test POST /repositories, GET /repositories, and GET /repositories/{id}."""
    unique_id = str(uuid.uuid4())[:8]
    test_url = f"https://github.com/example/test-repo-{unique_id}"

    # 1. Create a new repository
    response = client.post("/repositories", json={"url": test_url})
    assert response.status_code == 201
    data = response.json()
    assert data["url"] == test_url
    assert data["status"] == "pending"
    repo_id = data["id"]

    # 2. Duplicate submission should fail with HTTP 400
    dup_response = client.post("/repositories", json={"url": test_url})
    assert dup_response.status_code == 400
    assert dup_response.json()["detail"] == "Repository already exists."

    # 3. List repositories
    list_response = client.get("/repositories")
    assert list_response.status_code == 200
    repos = list_response.json()
    assert len(repos) >= 1
    assert any(r["id"] == repo_id for r in repos)

    # 4. Get single repository
    get_response = client.get(f"/repositories/{repo_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == repo_id

def test_get_nonexistent_repository():
    """Test GET /repositories/{id} for non-existent ID returns 404."""
    response = client.get("/repositories/non-existent-uuid")
    assert response.status_code == 404
    assert response.json()["detail"] == "Repository not found."


def test_session_chat_endpoints_exist_and_return_history(monkeypatch):
    """API-call regression test: exercises the real FastAPI routes for session creation, chat, and history retrieval."""
    unique_id = str(uuid.uuid4())[:8]
    repo_url = f"https://github.com/example/session-chat-repo-{unique_id}"

    repo_response = client.post("/repositories", json={"url": repo_url})
    assert repo_response.status_code == 201
    repo_id = repo_response.json()["id"]

    from src.database.engine import SessionLocal
    from src.database.models import Repository

    db = SessionLocal()
    try:
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        assert repo is not None
        repo.status = "completed"
        db.commit()
    finally:
        db.close()

    session_response = client.post(f"/repositories/{repo_id}/sessions")
    assert session_response.status_code == 200
    session_id = session_response.json()["id"]

    fake_service = type(
        "FakeService",
        (),
        {"chat": staticmethod(lambda repo_id, message, chat_history, top_k: {
            "answer": "The repository implements this feature.",
            "citations": [{
                "file_path": "src/example.py",
                "symbol_name": "feature_fn",
                "start_line": 1,
                "end_line": 10,
                "similarity_score": 0.97
            }],
        })}
    )()
    monkeypatch.setattr("src.api.routes.repository.conversational_rag_service", fake_service)

    chat_response = client.post(
        f"/sessions/{session_id}/chat",
        json={"message": "Tell me about the feature.", "top_k": 5},
    )
    assert chat_response.status_code == 200
    payload = chat_response.json()
    assert payload["session_id"] == session_id
    assert payload["user_message"]["content"] == "Tell me about the feature."
    assert payload["assistant_message"]["content"] == "The repository implements this feature."

    history_response = client.get(f"/sessions/{session_id}/messages")
    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history) == 2
    assert [item["role"] for item in history] == ["user", "assistant"]


def test_get_all_jobs():
    """Test GET /jobs returns all queued jobs created by repository submissions."""
    unique_id = str(uuid.uuid4())[:8]
    repo_url = f"https://github.com/example/jobs-list-repo-{unique_id}"

    repo_response = client.post("/repositories", json={"url": repo_url})
    assert repo_response.status_code == 201
    repo_id = repo_response.json()["id"]

    response = client.get("/jobs")
    assert response.status_code == 200
    jobs = response.json()
    assert any(job["repository_id"] == repo_id for job in jobs)


def test_get_nonexistent_job():
    """Test GET /jobs/{id} for non-existent ID returns 404."""
    response = client.get("/jobs/non-existent-uuid")
    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found."
