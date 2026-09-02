from pydantic import BaseModel, ConfigDict
from datetime import datetime

class RepositoryCreate(BaseModel):
    url: str

class RepositoryResponse(BaseModel):
    id: str
    url: str
    name: str | None = None
    status: str
    file_count: int | None = None
    default_branch: str | None = None
    clone_path: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
