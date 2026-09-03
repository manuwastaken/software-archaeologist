from pydantic import BaseModel, ConfigDict
from datetime import datetime

class Base(BaseModel):
    pass

class QueryRequest(Base):
    question: str
    top_k: int = 5

class Citation(Base):
    file_path: str
    symbol_name: str | None = None
    start_line: int
    end_line: int
    similarity_score: float

class QueryResponse(Base):
    answer: str
    citations: list[Citation]