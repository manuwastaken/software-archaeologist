from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models import Base, Repository, Job

def test_database_models():
    """Test creating tables and storing records in an in-memory database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Create a Repository record
    repo = Repository(url="https://github.com/django/django", status="pending")
    session.add(repo)
    session.commit()
    session.refresh(repo)

    assert repo.id is not None
    assert repo.url == "https://github.com/django/django"
    assert repo.status == "pending"

    # 2. Create a Job linked to the Repository
    job = Job(repository_id=repo.id, status="queued", progress=0)
    session.add(job)
    session.commit()
    session.refresh(job)

    assert job.id is not None
    assert job.repository_id == repo.id
    assert job.status == "queued"

    session.close()
