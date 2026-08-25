from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.repositories.react_projects import ReactProjectRepository
from app.schemas.react_projects import (
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ProjectPatchRequest,
    ProjectResponse,
    ProjectListResponse,
    PaginationMetadata,
    ErrorResponse,
    ProjectStatus,
    BillingType
)

router = APIRouter(
    prefix="/react/projects",
    tags=["React - Projects"],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized - Bearer token required"},
        403: {"model": ErrorResponse, "description": "Forbidden - Insufficient permissions"},
        404: {"model": ErrorResponse, "description": "Not found"},
        400: {"model": ErrorResponse, "description": "Bad request"},
    }
)

# ============================================================================
# POST - CREATE PROJECT
# ============================================================================
@router.post(
    "/",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project",
    description="Create a new project with the provided details. Requires bearer token authentication."
)
def create_project(
    payload: ProjectCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new project.
    
    **Body Parameters:**
    - project_name (required): Name of the project (1-150 characters)
    - organization_id (required): Organization ID
    - description (optional): Project description (max 1000 characters)
    - start_date (optional): Project start date (ISO format)
    - deadline (optional): Project deadline (ISO format)
    - is_billable (optional): Whether project is billable (default: true)
    - billing_type (optional): Billing type - 'free', 'hourly', 'fixed' (default: 'free')
    - fixed_hours (optional): Fixed hours for project (must be > 0)
    - leader_id (optional): Project leader user ID
    - status_id (optional): Project status ID
    
    **Returns:** Created project object
    """
    try:
        # Check if project with same name already exists in organization
        if ReactProjectRepository.check_project_exists(
            db,
            payload.organization_id,
            payload.project_name
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project with name '{payload.project_name}' already exists in this organization"
            )
        
        # Create the project
        project = ReactProjectRepository.create_project(
            db=db,
            project_data=payload,
            created_by_user_id=current_user.id
        )
        
        return ProjectResponse.model_validate(project)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create project: {str(e)}"
        )


# ============================================================================
# GET - LIST PROJECTS (with pagination)
# ============================================================================
@router.get(
    "/",
    response_model=ProjectListResponse,
    status_code=status.HTTP_200_OK,
    summary="List projects with pagination",
    description="List all projects for an organization with pagination and filtering. Requires bearer token."
)
def list_projects(
    organization_id: int = Query(..., gt=0, description="Organization ID to filter by"),
    page: int = Query(1, ge=1, description="Page number (starting from 1)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (1-100)"),
    search: Optional[str] = Query(None, max_length=100, description="Search term for project name/description"),
    status: Optional[str] = Query(None, description="Filter by status (planning, active, pending, todo, completed, cancelled, archived)"),
    is_billable: Optional[bool] = Query(None, description="Filter by billable status"),
    leader_id: Optional[int] = Query(None, gt=0, description="Filter by project leader ID"),
    sort_by: str = Query("created_at", description="Sort by field (created_at, project_name, deadline)"),
    sort_order: str = Query("desc", description="Sort order (asc, desc)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List projects with advanced filtering and pagination.
    
    **Query Parameters:**
    - organization_id (required): Organization ID
    - page (optional): Page number (default: 1)
    - limit (optional): Items per page, max 100 (default: 20)
    - search (optional): Search projects by name or description
    - status (optional): Filter by project status
    - is_billable (optional): Filter by billable status
    - leader_id (optional): Filter by project leader
    - sort_by (optional): Sort field - 'created_at', 'project_name', 'deadline' (default: created_at)
    - sort_order (optional): Sort order - 'asc' or 'desc' (default: desc)
    
    **Returns:** Paginated list of projects with metadata
    """
    try:
        # Validate sort_by parameter
        valid_sort_fields = ["created_at", "project_name", "deadline", "start_date", "updated_at"]
        if sort_by not in valid_sort_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sort_by. Must be one of: {', '.join(valid_sort_fields)}"
            )
        
        # Validate sort_order parameter
        if sort_order.lower() not in ["asc", "desc"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid sort_order. Must be 'asc' or 'desc'"
            )
        
        # Get projects
        projects, total = ReactProjectRepository.list_projects(
            db=db,
            organization_id=organization_id,
            page=page,
            limit=limit,
            search=search,
            status=status,
            is_billable=is_billable,
            leader_id=leader_id,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        # Calculate pagination metadata
        total_pages = (total + limit - 1) // limit  # Ceiling division
        has_next = page < total_pages
        has_prev = page > 1
        
        pagination = PaginationMetadata(
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev
        )
        
        return ProjectListResponse(
            data=[ProjectResponse.model_validate(p) for p in projects],
            pagination=pagination
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve projects: {str(e)}"
        )


# ============================================================================
# GET - RETRIEVE SINGLE PROJECT
# ============================================================================
@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a single project",
    description="Retrieve details of a specific project by ID. Requires bearer token."
)
def get_project(
    project_id: int = Query(..., gt=0, description="Project ID"),
    organization_id: int = Query(..., gt=0, description="Organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific project by ID.
    
    **Parameters:**
    - project_id (path): Project ID
    - organization_id (query): Organization ID (for authorization)
    
    **Returns:** Project object
    """
    try:
        project = ReactProjectRepository.get_project_by_id(
            db=db,
            project_id=project_id,
            organization_id=organization_id
        )
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found in organization {organization_id}"
            )
        
        return ProjectResponse.model_validate(project)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve project: {str(e)}"
        )


# ============================================================================
# PUT - UPDATE PROJECT (Full update)
# ============================================================================
@router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a project (full update)",
    description="Update all fields of a project. Requires bearer token authentication."
)
def update_project(
    project_id: int,
    organization_id: int = Query(..., gt=0, description="Organization ID"),
    payload: ProjectUpdateRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update an existing project (full update).
    
    **Path Parameters:**
    - project_id: Project ID to update
    
    **Query Parameters:**
    - organization_id (required): Organization ID
    
    **Body Parameters (all optional):**
    - project_name: Project name (1-150 characters)
    - description: Project description (max 1000 characters)
    - start_date: Project start date (ISO format)
    - deadline: Project deadline (ISO format)
    - completed_at: Project completion date (ISO format)
    - is_billable: Whether project is billable
    - status: Project status (planning, active, pending, todo, completed, cancelled, archived)
    - billing_type: Billing type (free, hourly, fixed)
    - fixed_hours: Fixed hours for project (must be > 0)
    - leader_id: Project leader user ID
    - status_id: Project status ID
    
    **Returns:** Updated project object
    """
    try:
        # Get the project
        project = ReactProjectRepository.get_project_by_id(
            db=db,
            project_id=project_id,
            organization_id=organization_id
        )
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found"
            )
        
        # Check for duplicate name if name is being updated
        if payload and payload.project_name and payload.project_name != project.project_name:
            if ReactProjectRepository.check_project_exists(
                db=db,
                organization_id=organization_id,
                project_name=payload.project_name,
                exclude_id=project_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Project with name '{payload.project_name}' already exists in this organization"
                )
        
        # Update the project
        updated_project = ReactProjectRepository.update_project(
            db=db,
            db_project=project,
            project_data=payload
        )
        
        return ProjectResponse.model_validate(updated_project)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update project: {str(e)}"
        )


# ============================================================================
# PATCH - PARTIAL UPDATE PROJECT
# ============================================================================
@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Partially update a project",
    description="Update specific fields of a project. Only provided fields are updated. Requires bearer token."
)
def patch_project(
    project_id: int,
    organization_id: int = Query(..., gt=0, description="Organization ID"),
    payload: ProjectPatchRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Partially update an existing project.
    
    **Path Parameters:**
    - project_id: Project ID to update
    
    **Query Parameters:**
    - organization_id (required): Organization ID
    
    **Body Parameters (all optional, only provided fields are updated):**
    - project_name: Project name (1-150 characters)
    - description: Project description (max 1000 characters)
    - start_date: Project start date (ISO format)
    - deadline: Project deadline (ISO format)
    - completed_at: Project completion date (ISO format)
    - is_billable: Whether project is billable
    - status: Project status (planning, active, pending, todo, completed, cancelled, archived)
    - billing_type: Billing type (free, hourly, fixed)
    - fixed_hours: Fixed hours for project (must be > 0)
    - leader_id: Project leader user ID
    - status_id: Project status ID
    
    **Returns:** Updated project object
    """
    try:
        # Get the project
        project = ReactProjectRepository.get_project_by_id(
            db=db,
            project_id=project_id,
            organization_id=organization_id
        )
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found"
            )
        
        # Check for duplicate name if name is being updated
        if payload and payload.project_name and payload.project_name != project.project_name:
            if ReactProjectRepository.check_project_exists(
                db=db,
                organization_id=organization_id,
                project_name=payload.project_name,
                exclude_id=project_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Project with name '{payload.project_name}' already exists in this organization"
                )
        
        # Partially update the project
        updated_project = ReactProjectRepository.patch_project(
            db=db,
            db_project=project,
            project_data=payload
        )
        
        return ProjectResponse.model_validate(updated_project)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update project: {str(e)}"
        )


# ============================================================================
# DELETE - DELETE PROJECT
# ============================================================================
@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project",
    description="Delete a specific project by ID. Requires bearer token authentication."
)
def delete_project(
    project_id: int,
    organization_id: int = Query(..., gt=0, description="Organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a project.
    
    **Path Parameters:**
    - project_id: Project ID to delete
    
    **Query Parameters:**
    - organization_id (required): Organization ID
    
    **Returns:** 204 No Content on successful deletion
    """
    try:
        # Get the project
        project = ReactProjectRepository.get_project_by_id(
            db=db,
            project_id=project_id,
            organization_id=organization_id
        )
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found"
            )
        
        # Delete the project
        ReactProjectRepository.delete_project(db=db, db_project=project)
        
        # Return 204 No Content
        return None
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete project: {str(e)}"
        )
