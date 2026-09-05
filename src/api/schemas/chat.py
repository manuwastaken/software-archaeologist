from pydantic import BaseModel, ConfigDict
from datetime import datetime
from src.api.schemas.rag import Citation

class ChatSessionResponse(BaseModel):
    id: str
    repository_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    citation_json: dict | list[dict] | None = None
    created_at: datetime  

    model_config = ConfigDict(from_attributes=True)

class ChatRequest(BaseModel):
    message: str
    top_k: int = 4

    model_config = ConfigDict(from_attributes=True)

class ChatResponse(BaseModel):
    session_id: str
    user_message: MessageResponse
    assistant_message: MessageResponse  
    citations: list[Citation]          

    model_config = ConfigDict(from_attributes=True)