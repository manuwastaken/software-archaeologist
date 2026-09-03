from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from src.database.engine import get_db
from src.database.models import Repository, Job, File, Symbol
from src.api.schemas.repository import RepositoryCreate, RepositoryResponse
from src.api.schemas.ast import SymbolResponse, FileResponse
from src.api.schemas.rag import QueryRequest, QueryResponse, Citation
from src.ingestion.repository import ingest_repository
from src.rag.service import RAGService

router = APIRouter(
    prefix="/repositories",
    tags=["Repositories"]
)
rag_service = RAGService()

@router.get("", response_model=list[RepositoryResponse])
def get_repositories(db: Session = Depends(get_db)):
    return db.query(Repository).all()

@router.post("", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
def create_repository(repository: RepositoryCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    existing_repo = db.query(Repository).filter(Repository.url == repository.url).first()
    if existing_repo:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Repository already exists.")

    repo = Repository(url=repository.url, status="pending")
    db.add(repo)
    db.commit()
    db.refresh(repo)

    job = Job(repository_id=repo.id, status="queued", progress=0)
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(ingest_repository, repo.id, job.id, repo.url)
    return repo

@router.get("/{repo_id}", response_model=RepositoryResponse)
def get_repository(repo_id: str, db: Session = Depends(get_db)):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")
    return repo


@router.get("/{id}/files", response_model=list[FileResponse])
def get_repository_files(id: str, db: Session = Depends(get_db)):
    repo = db.query(Repository).filter(Repository.id == id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")
    
    files = db.query(File).filter(File.repository_id == id).all()
    return files

@router.get("/{id}/symbols", response_model=list[SymbolResponse])
def get_repository_symbols(id: str, db: Session = Depends(get_db)):
    repo = db.query(Repository).filter(Repository.id == id).first()
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found.")

    symbols = db.query(Symbol).join(File).filter(File.repository_id == id).all()
    return symbols

@router.post("/{id}/query", response_model=QueryResponse)
def query_repository(id: str, request: QueryRequest, db: Session = Depends(get_db)):
    repo = db.query(Repository).filter(Repository.id == id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Repository not found."
        )
        
    if repo.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Repository is not ready yet (status: {repo.status}). Please wait for ingestion to complete."
        )
    result = rag_service.answer_question(
        repository_id=id,
        question=request.question,
        top_k=request.top_k
    )
    return result