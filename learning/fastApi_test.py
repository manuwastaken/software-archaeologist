from fastapi import FastAPI, Path
from typing import Optional
from pydantic import BaseModel

# Create the FastAPI app object. This is the main server instance.
app = FastAPI()

# In-memory database-like dictionary for demo projects.
project = {
    1: {"name": "Archeon", "start_date": "31.08.26", "phase": "Fast Apis"}
}

# Pydantic model for creating a new project.
# It validates the JSON body sent in a POST request.
class Project(BaseModel):
    name: str
    start_date: str
    phase: str

# Pydantic model for updating a project.
# All fields are optional, so partial updates are allowed.
class Update_Project(BaseModel):
    name: Optional[str] = None
    start_date: Optional[str] = None
    phase: Optional[str] = None

# GET endpoint: returns a greeting message.
@app.get("/hello")
def say_hello():
    return {"message": "Hello Archeon"}

# GET endpoint: fetches one project by its numeric ID from the URL.
@app.get("/get_project/{project_id}")
def get_project(project_id: int = Path(..., description="The ID of the project you want to show")):
    return project[project_id]

# GET endpoint: searches for a project by its name using a query parameter.
@app.get("/get_by_name")
def get_name(name: Optional[str] = None):
    for project_id in project:
        if project[project_id]["name"] == name:
            return project[project_id]
    return {"Data": "Not found"}

# POST endpoint: creates a new project using a JSON body.
@app.post("/create_project/{project_id}")
def create_project(project_id: int, project_data: Project):
    if project_id in project:
        return {"Error": "Project exists"}
    project[project_id] = project_data.dict()
    return project[project_id]

# PUT endpoint: updates an existing project with partial data.
@app.put("/update_project/{project_id}")
def update_project(project_id: int, project_data: Update_Project):
    if project_id not in project:
        return {"Error": "Project does not exist"}

    if project_data.name is not None:
        project[project_id]["name"] = project_data.name

    if project_data.start_date is not None:
        project[project_id]["start_date"] = project_data.start_date

    if project_data.phase is not None:
        project[project_id]["phase"] = project_data.phase

    return project[project_id]

# DELETE endpoint: removes a project by ID.
@app.delete("/delete_project/{project_id}")
def delete_project(project_id: int):
    if project_id not in project:
        return {"Error": "Project does not exist"}
    del project[project_id]
    return {"Message": "Project deleted successfully"}
