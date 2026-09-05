import logging
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, AIMessage
from src.api.schemas.chat import ChatRequest, ChatResponse, ChatSessionResponse, MessageResponse
from src.database.engine import get_db
from src.database.models import Message, Repository, Job, File, Symbol, ChatSession
from src.api.schemas.repository import RepositoryCreate, RepositoryResponse
from src.api.schemas.ast import SymbolResponse, FileResponse
from src.api.schemas.rag import QueryRequest, QueryResponse, Citation
from src.ingestion.repository import ingest_repository
from src.rag.conversational import ConversationalRAGService
from src.rag.service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/repositories",
    tags=["Repositories"]
)
session_router = APIRouter(
    tags=["Sessions"]
)
rag_service = RAGService()
conversational_rag_service = None

def get_conversational_rag_service():
    global conversational_rag_service
    if conversational_rag_service is None:
        conversational_rag_service = ConversationalRAGService()
    return conversational_rag_service

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

@router.post("/{repo_id}/sessions", response_model=ChatSessionResponse)
def create_chat_session(repo_id: str, db: Session = Depends(get_db)):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found"
        )
    if repo.status !="completed":
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail=f"Repository is not ready yet (status: {repo.status}). Please wait for ingestion to complete."
        )
    chat_session = ChatSession(repository_id = repo_id)
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)
    return chat_session

@router.get("/{id}/sessions", response_model=list[ChatSessionResponse])
def get_sessions(id:str, db: Session = Depends(get_db)):
    repo = db.query(Repository).filter(Repository.id == id).first()
    if not repo:
        raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Repository not found"
        )
    sessions = db.query(ChatSession).filter(ChatSession.repository_id == id).all()
    return sessions

@session_router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
def get_chat_history(session_id: str, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    messages = db.query(Message).filter(Message.session_id == session_id).order_by(Message.created_at)
    return messages

@session_router.post("/sessions/{session_id}/chat", response_model=ChatResponse)
def create_chat(session_id: str, request: ChatRequest, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    repo = db.query(Repository).filter(Repository.id == session.repository_id).first()
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

    history_messages = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.created_at.desc())
        .limit(6)
        .all()
    )
    chat_history = []
    for message in reversed(history_messages):
        if message.role == "user":
            chat_history.append(HumanMessage(content=message.content))
        elif message.role == "assistant":
            chat_history.append(AIMessage(content=message.content))

    try:
        service = conversational_rag_service or get_conversational_rag_service()
        result = service.chat(
            repository_id=session.repository_id,
            message=request.message,
            chat_history=chat_history,
            top_k=request.top_k,
        )
    except ValueError as exc:
        logger.error(f"Chat service configuration error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service is unavailable. Please configure the required API credentials before using multi-turn chat."
        ) from exc
    except Exception as exc:
        logger.error(f"Chat processing error: {type(exc).__name__}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process the chat request: {type(exc).__name__} - {str(exc)}"
        ) from exc

    user_message = Message(session_id=session_id, role="user", content=request.message)
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    assistant_message = Message(
        session_id=session_id,
        role="assistant",
        content=result.get("answer", ""),
        citation_json=result.get("citations", [])
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    return ChatResponse(
        session_id=session_id,
        user_message=user_message,
        assistant_message=assistant_message,
        citations=result.get("citations", [])
    )
