from datetime import date
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.projects_report import ProjectsReportRepository
from app.schemas.projects_report import BillableFilter
from app.services.time_tracking import TimeTrackingService


class ProjectsReportService:
    @staticmethod
    def build(
        db: Session,
        current_user: User,
        start_date: date,
        end_date: date,
        member_ids: Optional[list[int]],
        project_ids: Optional[list[int]],
        billing_type: Optional[BillableFilter],
    ) -> dict:
        if start_date > end_date:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "from cannot be after to.")

        # De-dupe caller-supplied id lists so repeated ids don't skew nothing but
        # do keep intent obvious at the query layer.
        member_ids = sorted(set(member_ids)) if member_ids else None
        project_ids = sorted(set(project_ids)) if project_ids else None
        is_billable = None
        if billing_type is not None:
            is_billable = billing_type == BillableFilter.billable

        start_time = TimeTrackingService._utc_start(start_date)
        end_time = TimeTrackingService._utc_end(end_date)

        organization_id = current_user.organization_id

        eligible_projects = ProjectsReportRepository.eligible_projects(
            db, organization_id, project_ids, is_billable
        )
        eligible_ids = list(eligible_projects.keys())

        auto_hours = ProjectsReportRepository.hours_by_project(
            db, organization_id, eligible_ids, member_ids, start_time, end_time
        )
        manual_hours = ProjectsReportRepository.manual_hours_by_project(
            db, organization_id, eligible_ids, member_ids, start_date, end_date
        )

        combined_hours = {
            pid: auto_hours.get(pid, 0) + manual_hours.get(pid, 0)
            for pid in set(auto_hours) | set(manual_hours)
        }
        # A project only appears in the report if it actually has matching
        # tracked time in range -- an eligible-but-silent project is dropped,
        # per the confirmed "exclude zero-data projects" convention.
        included_ids = [pid for pid, secs in combined_hours.items() if secs > 0]

        activity = ProjectsReportRepository.activity_by_project(
            db, organization_id, included_ids, member_ids, start_time, end_time
        )
        member_id_set = ProjectsReportRepository.distinct_member_ids(
            db, organization_id, included_ids, member_ids, start_time, end_time, start_date, end_date
        )

        projects = []
        for pid in included_ids:
            secs = combined_hours[pid]
            avg_pct, _sample_count = activity.get(pid, (None, 0))
            projects.append({
                "project_id": pid,
                "project_name": eligible_projects[pid],
                "tracked_seconds": secs,
                "tracked_hours": round(secs / 3600, 2),
                "tracked_hours_formatted": TimeTrackingService._hours(secs),
                "activity_percentage": round(avg_pct, 2) if avg_pct is not None else None,
            })
        projects.sort(key=lambda item: (-item["tracked_seconds"], item["project_name"]))

        total_seconds = sum(combined_hours[pid] for pid in included_ids)
        weighted_pct_sum = 0.0
        weighted_pct_count = 0
        for pid in included_ids:
            avg_pct, sample_count = activity.get(pid, (None, 0))
            if avg_pct is not None and sample_count:
                weighted_pct_sum += avg_pct * sample_count
                weighted_pct_count += sample_count
        average_activity_percentage = (
            round(weighted_pct_sum / weighted_pct_count, 2) if weighted_pct_count else None
        )

        return {
            "start_date": start_date,
            "end_date": end_date,
            "summary": {
                "total_project_hours": round(total_seconds / 3600, 2),
                "total_tracked_seconds": total_seconds,
                "total_hours_formatted": TimeTrackingService._hours(total_seconds),
                "average_activity_percentage": average_activity_percentage,
                "total_members": len(member_id_set),
                "total_projects": len(included_ids),
            },
            "projects": projects,
        }
