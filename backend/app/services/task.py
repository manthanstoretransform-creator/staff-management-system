from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List
from app.models.task import Task
from app.models.user import User
from app.schemas.task import TaskCreate, TaskUpdate
from app.repositories.task import TaskRepository
from app.repositories.project_member import ProjectMemberRepository
from app.services.project import ProjectService

class TaskService:
    @staticmethod
    def create_task(db: Session, project_id: int, task_in: TaskCreate, current_user: User) -> Task:
        # 1. Enforce project exists in caller's organization
        project = ProjectService.get_project(db, project_id, current_user)
        
        # 2. Enforce project membership check for employees
        if current_user.role_name == "employee":
            member = ProjectMemberRepository.get_by_project_and_user(db, project_id, current_user.id)
            if not member or member.organization_id != current_user.organization_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You must be a member of this project to create tasks in it."
                )

        # 3. Create the task
        return TaskRepository.create(
            db=db,
            task_in=task_in,
            organization_id=current_user.organization_id,
            project_id=project.id,
            created_by_user_id=current_user.id
        )

    @staticmethod
    def list_tasks(db: Session, project_id: int, current_user: User) -> List[Task]:
        # 1. Enforce project exists in caller's organization
        ProjectService.get_project(db, project_id, current_user)
        # 2. List tasks
        return TaskRepository.list_by_project(db, project_id)

    @staticmethod
    def get_task(db: Session, project_id: int, task_id: int, current_user: User) -> Task:
        # 1. Enforce project exists in caller's organization
        ProjectService.get_project(db, project_id, current_user)
        # 2. Get task and verify parent project match
        task = TaskRepository.get_by_id(db, task_id)
        if not task or task.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        return task

    @staticmethod
    def update_task(db: Session, project_id: int, task_id: int, task_in: TaskUpdate, current_user: User) -> Task:
        # 1. Verify project and task parent project constraints
        task = TaskService.get_task(db, project_id, task_id, current_user)
        # 2. Update task
        return TaskRepository.update(db, task, task_in)

    @staticmethod
    def archive_task(db: Session, project_id: int, task_id: int, current_user: User) -> Task:
        # 1. Verify project and task parent project constraints
        task = TaskService.get_task(db, project_id, task_id, current_user)
        # 2. Archive task
        return TaskRepository.archive(db, task)
