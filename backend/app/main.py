from fastapi import FastAPI
from app.api.auth import router as auth_router
from app.api.project import router as project_router
from app.api.task import router as task_router

app = FastAPI(
    title="Staff Management System API",
    description="Backend API for Staff Management System",
    version="0.1.0"
)

app.include_router(auth_router)
app.include_router(project_router)
app.include_router(task_router)

@app.get("/")
def read_root():
    return {"message": "Staff Management System API is running."}
