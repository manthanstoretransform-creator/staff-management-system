from collections import OrderedDict
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.project_status import ProjectStatus, TaskStatus
from app.models.task import Task
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.repositories.time_tracking import TimeTrackingRepository


class TimeTrackingService:
    @staticmethod
    def date_bounds(
        range_name: Optional[str],
        selected_date: Optional[date],
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> tuple[date, date]:
        supplied_filters = sum(value is not None for value in (range_name, selected_date, start_date, end_date))
        if supplied_filters == 0:
            range_name = "today"
        elif range_name and (selected_date or start_date or end_date):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Use range, date, or start_date/end_date, not a combination.")
        elif selected_date and (start_date or end_date):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Use date or start_date/end_date, not a combination.")

        today = datetime.now(timezone.utc).date()
        if range_name:
            if range_name == "today":
                return today, today
            if range_name == "7d":
                return today - timedelta(days=6), today
            if range_name == "30d":
                return today - timedelta(days=29), today
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid range. Use today, 7d, or 30d.")
        if selected_date:
            return selected_date, selected_date
        if start_date is None or end_date is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Both start_date and end_date are required.")
        if start_date > end_date:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "start_date cannot be after end_date.")
        return start_date, end_date

    @staticmethod
    def _utc_start(value: date) -> datetime:
        return datetime.combine(value, time.min, tzinfo=timezone.utc)

    @staticmethod
    def _utc_end(value: date) -> datetime:
        return datetime.combine(value + timedelta(days=1), time.min, tzinfo=timezone.utc)

    @staticmethod
    def _hours(total_seconds: int) -> str:
        hours, seconds = divmod(max(0, total_seconds), 3600)
        return f"{hours}h {seconds // 60}m"

    @staticmethod
    def _status(item: Optional[ProjectStatus | TaskStatus]):
        if item is None:
            return None
        return {"id": item.id, "name": item.name, "color": item.color}

    @staticmethod
    def _effective_user_id(current_user: User, employee_id: Optional[int]) -> Optional[int]:
        if not (current_user.permissions or {}).get("time_entries:view_all", False):
            return current_user.id
        return employee_id

    @staticmethod
    def _effective_user_ids(current_user: User, employee_ids: Optional[List[int]]) -> Optional[List[int]]:
        if not (current_user.permissions or {}).get("time_entries:view_all", False):
            return [current_user.id]
        return employee_ids

    @staticmethod
    def _ensure_employee_access(current_user: User, employee_id: Optional[int]) -> None:
        if employee_id is not None and not (current_user.permissions or {}).get("time_entries:view_all", False) and employee_id != current_user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions to view this employee's time.")

    @staticmethod
    def _ensure_employees_access(current_user: User, employee_ids: Optional[List[int]]) -> None:
        if not employee_ids or (current_user.permissions or {}).get("time_entries:view_all", False):
            return
        if any(eid != current_user.id for eid in employee_ids):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions to view this employee's time.")

    @staticmethod
    def list_daily(
        db: Session,
        current_user: User,
        range_name: Optional[str],
        selected_date: Optional[date],
        start_date: Optional[date],
        end_date: Optional[date],
        employee_ids: Optional[List[int]],
        search: Optional[str],
        page: int,
        limit: int,
    ):
        first_date, last_date = TimeTrackingService.date_bounds(range_name, selected_date, start_date, end_date)
        TimeTrackingService._ensure_employees_access(current_user, employee_ids)
        effective_user_ids = TimeTrackingService._effective_user_ids(current_user, employee_ids)
        rows, total = TimeTrackingRepository.list_daily_totals(
            db,
            current_user.organization_id,
            TimeTrackingService._utc_start(first_date),
            TimeTrackingService._utc_end(last_date),
            effective_user_ids,
            search,
            (page - 1) * limit,
            limit,
        )
        items = []
        for row in rows:
            total_seconds = int(row["total_seconds"] or 0)
            items.append({
                "employee_id": row["employee_id"],
                "name": row["name"],
                "email": row["email"],
                "designation": row["designation"],
                "date": row["work_date"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "total_seconds": total_seconds,
                "total_hours": TimeTrackingService._hours(total_seconds),
            })
        return {
            "items": items,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit if total else 0,
            },
        }

    @staticmethod
    def detail(
        db: Session,
        current_user: User,
        employee_id: int,
        range_name: Optional[str],
        selected_date: Optional[date],
        start_date: Optional[date],
        end_date: Optional[date],
    ):
        first_date, last_date = TimeTrackingService.date_bounds(range_name, selected_date, start_date, end_date)
        TimeTrackingService._ensure_employee_access(current_user, employee_id)
        employee = TimeTrackingRepository.get_employee(db, current_user.organization_id, employee_id)
        if not employee:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found.")
        if TimeTrackingService._effective_user_id(current_user, employee_id) != employee_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found.")

        rows = TimeTrackingRepository.detail_entries(
            db,
            current_user.organization_id,
            employee_id,
            TimeTrackingService._utc_start(first_date),
            TimeTrackingService._utc_end(last_date),
        )
        projects = OrderedDict()
        total_seconds = 0
        first_start = None
        last_end = None
        for entry, project, task, project_status, task_status, duration in rows:
            duration_seconds = max(0, int(duration or 0))
            total_seconds += duration_seconds
            first_start = entry.start_time if first_start is None else min(first_start, entry.start_time)
            if entry.end_time is not None:
                last_end = entry.end_time if last_end is None else max(last_end, entry.end_time)

            project_data = projects.setdefault(project.id, {
                "id": project.id,
                "name": project.project_name,
                "status": TimeTrackingService._status(project_status),
                "total_seconds": 0,
                "total_hours": "0h 0m",
                "tasks": OrderedDict(),
            })
            task_data = project_data["tasks"].setdefault(task.id, {
                "id": task.id,
                "name": task.task_name,
                "status": TimeTrackingService._status(task_status),
                "total_seconds": 0,
                "total_hours": "0h 0m",
                "entries": [],
            })
            project_data["total_seconds"] += duration_seconds
            task_data["total_seconds"] += duration_seconds
            task_data["entries"].append({
                "id": entry.id,
                "start_time": entry.start_time,
                "end_time": entry.end_time,
                "duration_seconds": duration_seconds,
                "is_running": entry.end_time is None,
                "is_manual": entry.is_manual,
            })

        project_results = []
        for project_data in projects.values():
            project_data["total_hours"] = TimeTrackingService._hours(project_data["total_seconds"])
            project_data["tasks"] = list(project_data["tasks"].values())
            for task_data in project_data["tasks"]:
                task_data["total_hours"] = TimeTrackingService._hours(task_data["total_seconds"])
            project_results.append(project_data)

        return {
            "employee": {
                "id": employee.id,
                "name": employee.name,
                "email": employee.email,
                "designation": employee.designation,
                "role": employee.role_name,
            },
            "start_date": first_date,
            "end_date": last_date,
            "summary": {
                "start_time": first_start,
                "end_time": last_end,
                "total_seconds": total_seconds,
                "total_hours": TimeTrackingService._hours(total_seconds),
            },
            "projects": project_results,
        }
