import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, AIMessage
from src.agents.orchestrator import ArchaeonAgentService
from src.api.schemas.chat import ChatRequest, ChatResponse, ChatSessionResponse, MessageResponse
from src.database.engine import get_db
from src.database.models import Message, Repository, ChatSession
from src.ingestion.repository import ingest_repository
from src.rag.conversational import ConversationalRAGService
from src.rag.service import RAGService


logger = logging.getLogger(__name__)

session_router = APIRouter(
    tags=["Sessions"]
)
rag_service = RAGService()
conversational_rag_service = None
agent_service = None

def get_conversational_rag_service():
    global conversational_rag_service
    if conversational_rag_service is None:
        conversational_rag_service = ConversationalRAGService()
    return conversational_rag_service

def get_agent_service() -> ArchaeonAgentService:
    global agent_service
    if agent_service is None:
        agent_service = ArchaeonAgentService()
    return agent_service

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
        if not request.agent_mode:
            # Fast Single-Turn LCEL RAG (Phase 4)
            service = conversational_rag_service or get_conversational_rag_service()
            result = service.chat(
                repository_id=session.repository_id,
                message=request.message,
                chat_history=chat_history,
                top_k=request.top_k,
            )
        else:
            # Autonomous ReAct Agent Loop (Phase 5)
            service = agent_service or get_agent_service()
            result = service.chat(
                repository_id=session.repository_id,
                db=db,
                clone_path=repo.clone_path or f"data/repos/{repo.id}",
                message=request.message,
                chat_history=chat_history,
            )
    except ValueError as exc:
        logger.error(f"Chat service configuration error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat service is unavailable. Please configure the required API credentials before using multi-turn chat."
        ) from exc
    except Exception as exc:
        exc_str = str(exc).lower()
        if "429" in exc_str or "resource_exhausted" in exc_str or "quota" in exc_str or "rate limit" in exc_str:
            logger.warning(f"Rate limit reached: {exc}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Gemini API rate limit reached (5 requests per minute limit). Please wait 15-30 seconds before asking your next question."
            ) from exc

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
