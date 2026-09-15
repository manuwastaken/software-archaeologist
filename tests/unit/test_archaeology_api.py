import uuid
from fastapi.testclient import TestClient
from src.api.main import app
from src.database.engine import SessionLocal
from src.database.models import Repository
from src.analysis.git_history import CommitSummary, BlameSegment, CommitDetail

client = TestClient(app)


def _create_completed_repo(clone_path: str = "data/repos/test-clone") -> str:
    """Helper to register a completed repo in DB for testing."""
    unique_id = str(uuid.uuid4())[:8]
    repo_url = f"https://github.com/example/archaeology-repo-{unique_id}"
    response = client.post("/repositories", json={"url": repo_url})
    assert response.status_code == 201
    repo_id = response.json()["id"]

    db = SessionLocal()
    try:
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        assert repo is not None
        repo.status = "completed"
        repo.clone_path = clone_path
        db.commit()
    finally:
        db.close()
    return repo_id


def test_get_commits_endpoint(monkeypatch):
    """Test GET /repositories/{id}/commits returns commits list."""
    repo_id = _create_completed_repo()

    fake_commits = [
        CommitSummary(
            hexsha="a1b2c3d",
            author="Ada Lovelace",
            authored_date="2026-01-01T12:00:00",
            message="Add algorithm engine",
        ),
        CommitSummary(
            hexsha="e5f6a7b",
            author="Charles Babbage",
            authored_date="2026-01-02T14:30:00",
            message="Initial mechanical design",
        ),
    ]

    monkeypatch.setattr(
        "src.analysis.git_history.GitHistoryAnalyzer.get_commits",
        lambda self, file_path=None, limit=20: fake_commits,
    )

    response = client.get(f"/repositories/{repo_id}/commits?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["hexsha"] == "a1b2c3d"
    assert data[0]["author"] == "Ada Lovelace"
    assert data[0]["message"] == "Add algorithm engine"


def test_get_blame_endpoint(monkeypatch):
    """Test GET /repositories/{id}/blame returns blame segments."""
    repo_id = _create_completed_repo()

    fake_blames = [
        BlameSegment(
            start_line=1,
            end_line=10,
            commit_hash="a1b2c3d",
            author="Ada Lovelace",
            date="2026-01-01T12:00:00",
            summary="Add algorithm engine",
        ),
        BlameSegment(
            start_line=11,
            end_line=25,
            commit_hash="e5f6a7b",
            author="Charles Babbage",
            date="2026-01-02T14:30:00",
            summary="Initial mechanical design",
        ),
    ]

    monkeypatch.setattr(
        "src.analysis.git_history.GitHistoryAnalyzer.get_blame",
        lambda self, file_path, start_line, end_line: fake_blames,
    )

    response = client.get(
        f"/repositories/{repo_id}/blame?file_path=src/app.py&start_line=1&end_line=25"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["start_line"] == 1
    assert data[0]["end_line"] == 10
    assert data[0]["author"] == "Ada Lovelace"
    assert data[1]["start_line"] == 11
    assert data[1]["end_line"] == 25


def test_get_commit_diff_endpoint(monkeypatch):
    """Test GET /repositories/{id}/commits/{hash} returns commit detail."""
    repo_id = _create_completed_repo()

    fake_detail = CommitDetail(
        hexsha="a1b2c3d",
        author="Ada Lovelace",
        date="2026-01-01T12:00:00",
        message="Add algorithm engine\n\nFull description here.",
        files_changed=["src/engine.py", "tests/test_engine.py"],
        diff_text="@@ -0,0 +1,5 @@\n+def compute():\n+    return 42\n",
    )

    monkeypatch.setattr(
        "src.analysis.git_history.GitHistoryAnalyzer.get_diff",
        lambda self, commit_hash, max_lines=60: fake_detail,
    )

    response = client.get(f"/repositories/{repo_id}/commits/a1b2c3d?max_lines=50")
    assert response.status_code == 200
    data = response.json()
    assert data["hexsha"] == "a1b2c3d"
    assert data["author"] == "Ada Lovelace"
    assert "src/engine.py" in data["files_changed"]
    assert "+def compute():" in data["diff_text"]


def test_archaeology_endpoints_404_for_missing_repo():
    """Test all 3 endpoints return 404 when repo ID does not exist."""
    missing_id = "non-existent-repo-id"

    r1 = client.get(f"/repositories/{missing_id}/commits")
    assert r1.status_code == 404

    r2 = client.get(f"/repositories/{missing_id}/blame?file_path=app.py&start_line=1&end_line=10")
    assert r2.status_code == 404

    r3 = client.get(f"/repositories/{missing_id}/commits/a1b2c3d")
    assert r3.status_code == 404


def test_archaeology_endpoints_400_for_pending_repo():
    """Test all 3 endpoints return 400 when repo is not yet completed."""
    unique_id = str(uuid.uuid4())[:8]
    response = client.post("/repositories", json={"url": f"https://github.com/example/pending-{unique_id}"})
    assert response.status_code == 201
    pending_repo_id = response.json()["id"]

    r1 = client.get(f"/repositories/{pending_repo_id}/commits")
    assert r1.status_code == 400

    r2 = client.get(f"/repositories/{pending_repo_id}/blame?file_path=app.py&start_line=1&end_line=10")
    assert r2.status_code == 400

    r3 = client.get(f"/repositories/{pending_repo_id}/commits/a1b2c3d")
    assert r3.status_code == 400
