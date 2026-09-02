from datetime import datetime, timezone
from src.api.schemas.repository import RepositoryCreate, RepositoryResponse
from src.api.schemas.job import JobResponse

def test_repository_create_schema():
    """Test validating repository creation input."""
    payload = {"url": "https://github.com/psf/requests"}
    schema = RepositoryCreate(**payload)
    assert schema.url == "https://github.com/psf/requests"

def test_repository_response_schema():
    """Test repository output schema serialization."""
    now = datetime.now(timezone.utc)
    data = {
        "id": "test-repo-123",
        "url": "https://github.com/psf/requests",
        "name": "requests",
        "status": "completed",
        "file_count": 42,
        "default_branch": "main",
        "clone_path": "data/repos/test-repo-123",
        "created_at": now,
        "updated_at": now,
    }
    schema = RepositoryResponse(**data)
    assert schema.id == "test-repo-123"
    assert schema.status == "completed"
    assert schema.file_count == 42

def test_job_response_schema():
    """Test job output schema serialization."""
    now = datetime.now(timezone.utc)
    data = {
        "id": "job-456",
        "repository_id": "test-repo-123",
        "status": "processing",
        "progress": 50,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }
    schema = JobResponse(**data)
    assert schema.id == "job-456"
    assert schema.progress == 50
    assert schema.error is None
