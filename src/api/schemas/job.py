from pydantic import BaseModel, ConfigDict
from datetime import datetime


# Output Schema: What FastAPI returns when checking GET /jobs/{id}
class JobResponse(BaseModel):
    id: str
    repository_id: str
    status: str
    progress: int
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    # Allows converting SQLAlchemy Job objects directly to JSON schema
    model_config = ConfigDict(from_attributes=True)