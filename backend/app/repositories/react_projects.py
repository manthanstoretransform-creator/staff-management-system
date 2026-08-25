from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, or_, desc
from typing import Optional, List, Tuple
from app.models.project import Project
from app.schemas.react_projects import (
    ProjectCreateRequest, 
    ProjectUpdateRequest, 
    ProjectPatchRequest,
    ProjectStatus
)

class ReactProjectRepository:
    """Repository for React API project operations"""

    @staticmethod
    def get_project_by_id(db: Session, project_id: int, organization_id: int) -> Optional[Project]:
        """Get a single project by ID with organization verification"""
        return db.scalar(
            select(Project).where(
                and_(
                    Project.id == project_id,
                    Project.organization_id == organization_id
                )
            )
        )

    @staticmethod
    def list_projects(
        db: Session,
        organization_id: int,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        status: Optional[str] = None,
        is_billable: Optional[bool] = None,
        leader_id: Optional[int] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Tuple[List[Project], int]:
        """
        List projects with pagination and filtering
        
        Args:
            db: Database session
            organization_id: Organization ID to filter by
            page: Page number (1-indexed)
            limit: Items per page (1-100)
            search: Search term for project name and description
            status: Filter by project status
            is_billable: Filter by billable status
            leader_id: Filter by project leader
            sort_by: Field to sort by (created_at, project_name, deadline)
            sort_order: Sort order (asc, desc)
        
        Returns:
            Tuple of (projects list, total count)
        """
        # Build query
        query = select(Project).where(Project.organization_id == organization_id)
        
        # Apply filters
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    Project.project_name.ilike(search_term),
                    Project.description.ilike(search_term)
                )
            )
        
        if status:
            query = query.where(Project.status == status)
        
        if is_billable is not None:
            query = query.where(Project.is_billable == is_billable)
        
        if leader_id is not None:
            query = query.where(Project.leader_id == leader_id)
        
        # Count total
        count_query = select(func.count()).select_from(Project).where(
            and_(
                Project.organization_id == organization_id,
                or_(
                    search is None or or_(
                        Project.project_name.ilike(f"%{search}%"),
                        Project.description.ilike(f"%{search}%")
                    ),
                    True
                )
            )
        )
        
        # Recount with all filters applied
        if search:
            search_term = f"%{search}%"
            count_query = count_query.where(
                or_(
                    Project.project_name.ilike(search_term),
                    Project.description.ilike(search_term)
                )
            )
        if status:
            count_query = count_query.where(Project.status == status)
        if is_billable is not None:
            count_query = count_query.where(Project.is_billable == is_billable)
        if leader_id is not None:
            count_query = count_query.where(Project.leader_id == leader_id)
        
        total = db.scalar(count_query) or 0
        
        # Apply sorting
        sort_column = getattr(Project, sort_by, Project.created_at)
        if sort_order.lower() == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(sort_column)
        
        # Apply pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)
        
        projects = list(db.scalars(query).all())
        return projects, total

    @staticmethod
    def create_project(
        db: Session,
        project_data: ProjectCreateRequest,
        created_by_user_id: int
    ) -> Project:
        """Create a new project"""
        db_project = Project(
            organization_id=project_data.organization_id,
            project_name=project_data.project_name,
            description=project_data.description,
            start_date=project_data.start_date,
            deadline=project_data.deadline,
            is_billable=project_data.is_billable,
            billing_type=project_data.billing_type.value,
            fixed_hours=project_data.fixed_hours,
            leader_id=project_data.leader_id,
            status_id=project_data.status_id,
            status=ProjectStatus.PLANNING.value,
            created_by=created_by_user_id,
            time_tracked_seconds=0
        )
        db.add(db_project)
        db.commit()
        db.refresh(db_project)
        return db_project

    @staticmethod
    def update_project(
        db: Session,
        db_project: Project,
        project_data: ProjectUpdateRequest
    ) -> Project:
        """Update an entire project (PUT - full update)"""
        update_data = project_data.model_dump(exclude_unset=False, exclude_none=True)
        
        for field, value in update_data.items():
            if value is not None:
                if field == "billing_type" and isinstance(value, str):
                    setattr(db_project, field, value)
                elif field == "status" and isinstance(value, ProjectStatus):
                    setattr(db_project, "status", value.value)
                else:
                    setattr(db_project, field, value)
        
        db.add(db_project)
        db.commit()
        db.refresh(db_project)
        return db_project

    @staticmethod
    def patch_project(
        db: Session,
        db_project: Project,
        project_data: ProjectPatchRequest
    ) -> Project:
        """Partially update a project (PATCH - partial update)"""
        update_data = project_data.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            if value is not None:
                if field == "billing_type" and isinstance(value, str):
                    setattr(db_project, field, value)
                elif field == "status" and isinstance(value, ProjectStatus):
                    setattr(db_project, "status", value.value)
                else:
                    setattr(db_project, field, value)
        
        db.add(db_project)
        db.commit()
        db.refresh(db_project)
        return db_project

    @staticmethod
    def delete_project(db: Session, db_project: Project) -> bool:
        """Delete a project"""
        db.delete(db_project)
        db.commit()
        return True

    @staticmethod
    def check_project_exists(
        db: Session,
        organization_id: int,
        project_name: str,
        exclude_id: Optional[int] = None
    ) -> bool:
        """Check if a project with the same name exists in the organization"""
        query = select(Project).where(
            and_(
                Project.organization_id == organization_id,
                Project.project_name == project_name
            )
        )
        
        if exclude_id is not None:
            query = query.where(Project.id != exclude_id)
        
        return db.scalar(query) is not None

    @staticmethod
    def get_organization_id_for_project(db: Session, project_id: int) -> Optional[int]:
        """Get organization ID for a project (useful for authorization checks)"""
        project = db.scalar(select(Project.organization_id).where(Project.id == project_id))
        return project
