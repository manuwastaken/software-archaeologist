from sqlalchemy.orm import Session
from src.database.engine import SessionLocal
from src.database.models import Repository, Job
from src.ingestion.git import git_clone, git_extract_metadata

def ingest_repository(repo_id: str, job_id: str, repo_url: str):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            print(f"Job with ID {job_id} not found.")
            return
        job.status = "processing"
        job.progress = 10

        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if not repo:
            print(f"Repository with ID {repo_id} not found.")
            return
        repo.status = "processing"
        db.commit()

        destination_path = f"data/repos/{repo_id}"
        git_clone(repo_url, destination_path)
        job.progress = 50
        db.commit()

        name, filecount, default_branch, clone_path = git_extract_metadata(destination_path, repo)
        job.progress = 80
        db.commit()

        repo.name = name
        repo.file_count = filecount
        repo.default_branch = default_branch
        repo.clone_path = clone_path
        repo.status = "completed"

        job.status = "completed"
        job.progress = 100
        db.commit()

    except Exception as e:
        print(f"Error during ingestion: {e}")
        db.rollback()
        job = db.query(Job).filter(Job.id == job_id).first()
        repo = db.query(Repository).filter(Repository.id == repo_id).first()
        if job:
            job.status = "failed"
            job.error = str(e)
            job.progress = 0
        if repo:
            repo.status = "failed"
        db.commit()
    finally:
        db.close()
