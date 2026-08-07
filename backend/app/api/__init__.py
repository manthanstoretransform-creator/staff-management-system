from app.api.auth import router as auth_router
from app.api.project import router as project_router
from app.api.task import router as task_router

__all__ = ["auth_router", "project_router", "task_router"]
