import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient
from src.api.main import app
from src.database.engine import SessionLocal
from src.database.models import Repository

client = TestClient(app)

def test_query_repository_validations():
    db = SessionLocal()
    try:
        # Use random UUIDs in URLs so they are guaranteed unique on every test run
        unique_url_1 = f"https://github.com/test/{uuid.uuid4()}"
        unique_url_2 = f"https://github.com/test/{uuid.uuid4()}"

        repo_processing = Repository(url=unique_url_1, status="processing")
        repo_completed = Repository(url=unique_url_2, status="completed")
        db.add_all([repo_processing, repo_completed])
        db.commit()
        db.refresh(repo_processing)
        db.refresh(repo_completed)

        # A: Query non-existent repo -> 404
        res_404 = client.post("/repositories/fake-id/query", json={"question": "What does this do?"})
        assert res_404.status_code == 404

        # B: Query repo that is still processing -> 400
        res_400 = client.post(f"/repositories/{repo_processing.id}/query", json={"question": "What does this do?"})
        assert res_400.status_code == 400
        assert "not ready" in res_400.json()["detail"]

        # C: Query completed repo with mocked RAG answer -> 200 (zero API calls)
        mock_answer = {
            "answer": "This is a mock explanation.",
            "citations": [
                {
                    "file_path": "src/test.py",
                    "symbol_name": "test_func",
                    "start_line": 1,
                    "end_line": 10,
                    "similarity_score": 0.88
                }
            ]
        }
        with patch("src.api.routes.repository.rag_service.answer_question", return_value=mock_answer):
            res_200 = client.post(f"/repositories/{repo_completed.id}/query", json={"question": "How does it work?"})
            assert res_200.status_code == 200
            data = res_200.json()
            assert data["answer"] == "This is a mock explanation."
            assert len(data["citations"]) == 1
            assert data["citations"][0]["file_path"] == "src/test.py"
    finally:
        db.close()