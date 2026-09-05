from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.database.engine import get_db
from src.database.models import Job
from src.api.schemas.job import JobResponse

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"]
)

@router.get("", response_model=list[JobResponse])
def get_all_jobs(db: Session = Depends(get_db)):
    jobs = db.query(Job).all()
    return jobs

@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job

@router.get("/repository/{repo_id}", response_model=list[JobResponse])
def get_jobs_by_repository(repo_id: str, db: Session = Depends(get_db)):
    jobs = db.query(Job).filter(Job.repository_id == repo_id).all()
    if not jobs:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No jobs found for this repository.")
    return jobs