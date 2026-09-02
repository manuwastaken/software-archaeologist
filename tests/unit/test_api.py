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

def test_get_nonexistent_job():
    """Test GET /jobs/{id} for non-existent ID returns 404."""
    response = client.get("/jobs/non-existent-uuid")
    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found."
