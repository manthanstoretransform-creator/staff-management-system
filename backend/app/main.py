from fastapi import FastAPI
from app.api.auth import router as auth_router
from app.api.project import router as project_router
from app.api.task import router as task_router
from app.api.project_member import router as project_member_router
from app.api.task_assignee import router as task_assignee_router
from app.api.time_entry import router as time_entry_router
from app.api.manual_time_entry import router as manual_time_entry_router
from app.api.employees import router as employees_router
from app.api.time_entry_screenshot import router as time_entry_screenshot_router
from app.api.members import router as members_router
from app.api.project_management import router as project_management_router
from app.api.time_entry_app_usage import router as time_entry_app_usage_router
from app.api.url_usage import router as url_usage_router
from app.api.teams import router as teams_router
from app.api.time_tracking import router as time_tracking_router
from app.react_apis.projects_report import router as projects_report_router
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
import logging

# Setup logging for serverless environment
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Staff Management System API",
    description="Backend API for Staff Management System",
    version="0.1.0"
)

# Log app initialization for debugging
logger.info(f"FastAPI app initialized. Environment: {settings.ENV}")

# 1. Base registrations for desktop client endpoints (which expect paths without /api/v1)
app.include_router(auth_router)
app.include_router(project_router)
app.include_router(task_router)
app.include_router(project_member_router)
app.include_router(task_assignee_router)
app.include_router(time_entry_router)
app.include_router(manual_time_entry_router)
app.include_router(employees_router)
app.include_router(time_entry_screenshot_router)
app.include_router(members_router)
app.include_router(time_entry_app_usage_router)
app.include_router(url_usage_router)

# 2. Registrations with the /api/v1 prefix (expected by React frontend and prefix-aware desktop calls)
api_prefix = "/api/v1"
app.include_router(auth_router, prefix=api_prefix)
app.include_router(time_entry_router, prefix=api_prefix)
app.include_router(manual_time_entry_router, prefix=api_prefix)
app.include_router(employees_router, prefix=api_prefix)
app.include_router(time_entry_screenshot_router, prefix=api_prefix)
app.include_router(members_router, prefix=api_prefix)
app.include_router(time_entry_app_usage_router, prefix=api_prefix)
app.include_router(url_usage_router, prefix=api_prefix)

# 3. Registrations for routers that contain their own /api/v1 internal prefix
# These must only be registered once without prefix parameters to avoid double-prefixing.
app.include_router(project_management_router)
app.include_router(teams_router)
app.include_router(time_tracking_router)
app.include_router(projects_report_router)

@app.get("/")
def read_root():
    return {"message": "Staff Management System API is running.", "environment": settings.ENV}

@app.get("/health")
def health_check():
    return {"status": "healthy", "environment": settings.ENV}


# Configure CORS to always allow both local and production frontends
cors_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "https://staff-management-system-frontend-six.vercel.app",
    "https://staffmanagementsystembackend.vercel.app",
    "https://staff-management.vercel.app",
    "https://stafftrack.io",
    "https://www.stafftrack.io"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)