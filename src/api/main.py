from fastapi import FastAPI
from src.database.engine import init_db
from src.api.routes.repository import router as repositories_router
from src.api.routes.jobs import router as jobs_router

# Initialize database tables on application startup
init_db()

app = FastAPI(title="Archaeon API", version="0.1.0")

# Register routes
app.include_router(repositories_router)
app.include_router(jobs_router)
