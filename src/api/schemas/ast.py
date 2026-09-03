from pydantic import BaseModel, ConfigDict
from datetime import datetime

class FileResponse(BaseModel):
    id: str
    repository_id: str
    path: str
    file_size: int
    line_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SymbolResponse(BaseModel):
    id: str
    file_id: str
    name: str
    symbol_type: str
    parent_class: str | None = None
    start_line: int
    end_line: int
    docstring: str | None = None
    metadata_json: dict | None = None

    model_config = ConfigDict(from_attributes=True)