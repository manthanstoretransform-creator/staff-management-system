from collections import defaultdict
from datetime import date
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.reports import ReportsRepository
from app.schemas.reports import BillableFilter, ReportDimension, UsageType
from app.services.time_tracking import TimeTrackingService

_hours = TimeTrackingService._hours
_utc_start = TimeTrackingService._utc_start
_utc_end = TimeTrackingService._utc_end


def _weighted_average(pairs) -> Optional[float]:
    """pairs: iterable of (avg, sample_count). Weighted by sample_count so a
    project with 1 sample doesn't pull the overall average as hard as one
    with 500."""
    total_weighted = 0.0
    total_count = 0
    for avg, count in pairs:
        if avg is None or not count:
            continue
        total_weighted += avg * count
        total_count += count
    return round(total_weighted / total_count, 2) if total_count else None


class ReportsService:
    @staticmethod
    def _resolve_common(
        db: Session,
        current_user: User,
        start_date: date,
        end_date: date,
        member_ids: Optional[list[int]],
        project_ids: Optional[list[int]],
        billing_type: Optional[BillableFilter],
    ):
        if start_date > end_date:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "from cannot be after to.")
        member_ids = sorted(set(member_ids)) if member_ids else None
        project_ids = sorted(set(project_ids)) if project_ids else None
        is_billable = None if billing_type is None else billing_type == BillableFilter.billable

        start_time = _utc_start(start_date)
        end_time = _utc_end(end_date)
        organization_id = current_user.organization_id

        eligible_projects = ReportsRepository.eligible_projects(db, organization_id, project_ids, is_billable)
        eligible_ids = list(eligible_projects.keys())
        return organization_id, member_ids, eligible_projects, eligible_ids, start_time, end_time

    # ------------------------------------------------------------- grouped

    @staticmethod
    def build_grouped(
        db: Session,
        current_user: User,
        dimension: ReportDimension,
        start_date: date,
        end_date: date,
        member_ids: Optional[list[int]],
        project_ids: Optional[list[int]],
        billing_type: Optional[BillableFilter],
        usage_type: UsageType,
    ) -> dict:
        organization_id, member_ids, eligible_projects, eligible_ids, start_time, end_time = (
            ReportsService._resolve_common(db, current_user, start_date, end_date, member_ids, project_ids, billing_type)
        )

        if dimension == ReportDimension.projects:
            grouped_data, summary_extra = ReportsService._grouped_projects(
                db, organization_id, eligible_projects, eligible_ids, member_ids, start_time, end_time, start_date, end_date
            )
        elif dimension == ReportDimension.members:
            grouped_data, summary_extra = ReportsService._grouped_members(
                db, organization_id, eligible_ids, member_ids, start_time, end_time, start_date, end_date
            )
        elif dimension == ReportDimension.tasks:
            grouped_data, summary_extra = ReportsService._grouped_tasks(
                db, organization_id, eligible_ids, member_ids, start_time, end_time, start_date, end_date
            )
        else:
            grouped_data, summary_extra = ReportsService._grouped_apps(
                db, organization_id, eligible_ids, member_ids, start_time, end_time, usage_type
            )

        total_seconds = sum(item["tracked_seconds"] for item in grouped_data)
        average_activity = _weighted_average(
            (item["activity_percentage"], item.pop("_sample_count")) for item in grouped_data
        )

        return {
            "start_date": start_date,
            "end_date": end_date,
            "summary": {
                "total_hours": round(total_seconds / 3600, 2),
                "total_tracked_seconds": total_seconds,
                "total_hours_formatted": _hours(total_seconds),
                "average_activity_percentage": average_activity,
                **summary_extra,
            },
            "grouped_data": grouped_data,
        }

    @staticmethod
    def _item(key, name, secs, avg_pct, sample_count, meta_label) -> dict:
        return {
            "id": key,
            "name": name,
            "tracked_seconds": secs,
            "tracked_hours": round(secs / 3600, 2),
            "tracked_hours_formatted": _hours(secs),
            "activity_percentage": round(avg_pct, 2) if avg_pct is not None else None,
            "meta_label": meta_label,
            "_sample_count": sample_count,
        }

    @staticmethod
    def _grouped_projects(db, organization_id, eligible_projects, eligible_ids, member_ids, start_time, end_time, start_date, end_date):
        seconds_by = ReportsRepository.session_seconds_by(
            db, organization_id, eligible_ids, member_ids, start_time, end_time, start_date, end_date, "project_id"
        )
        included_ids = [pid for pid, secs in seconds_by.items() if secs > 0]
        activity_by = ReportsRepository.session_activity_by(db, organization_id, included_ids, member_ids, start_time, end_time, "project_id")
        triples = ReportsRepository.session_triples(db, organization_id, included_ids, member_ids, start_time, end_time, start_date, end_date)

        project_members = defaultdict(set)
        project_tasks = defaultdict(set)
        all_members = set()
        for pid, uid, tid in triples:
            project_members[pid].add(uid)
            project_tasks[pid].add(tid)
            all_members.add(uid)

        entry_count = ReportsRepository.session_entry_count(db, organization_id, included_ids, member_ids, start_time, end_time, start_date, end_date)

        grouped = []
        for pid in included_ids:
            avg, count = activity_by.get(pid, (None, 0))
            meta = f"{len(project_members[pid])} members · {len(project_tasks[pid])} tasks"
            grouped.append(ReportsService._item(pid, eligible_projects[pid], seconds_by[pid], avg, count, meta))
        grouped.sort(key=lambda item: -item["tracked_seconds"])

        return grouped, {"total_members": len(all_members), "total_entries": entry_count, "total_projects": len(included_ids)}

    @staticmethod
    def _grouped_members(db, organization_id, eligible_ids, member_ids, start_time, end_time, start_date, end_date):
        seconds_by = ReportsRepository.session_seconds_by(
            db, organization_id, eligible_ids, member_ids, start_time, end_time, start_date, end_date, "user_id"
        )
        included_ids = [uid for uid, secs in seconds_by.items() if secs > 0]
        activity_by = ReportsRepository.session_activity_by(db, organization_id, eligible_ids, member_ids, start_time, end_time, "user_id")
        triples = ReportsRepository.session_triples(db, organization_id, eligible_ids, member_ids, start_time, end_time, start_date, end_date)
        users = ReportsRepository.users_lookup(db, organization_id, included_ids)

        member_projects = defaultdict(set)
        member_tasks = defaultdict(set)
        for pid, uid, tid in triples:
            member_projects[uid].add(pid)
            member_tasks[uid].add(tid)

        entry_count = ReportsRepository.session_entry_count(db, organization_id, eligible_ids, member_ids, start_time, end_time, start_date, end_date)

        grouped = []
        for uid in included_ids:
            avg, count = activity_by.get(uid, (None, 0))
            name, _role = users.get(uid, (f"User {uid}", None))
            meta = f"{len(member_projects[uid])} projects, {len(member_tasks[uid])} tasks"
            grouped.append(ReportsService._item(uid, name, seconds_by[uid], avg, count, meta))
        grouped.sort(key=lambda item: -item["tracked_seconds"])

        return grouped, {"total_members": len(included_ids), "total_entries": entry_count}

    @staticmethod
    def _grouped_tasks(db, organization_id, eligible_ids, member_ids, start_time, end_time, start_date, end_date):
        seconds_by = ReportsRepository.session_seconds_by(
            db, organization_id, eligible_ids, member_ids, start_time, end_time, start_date, end_date, "task_id"
        )
        included_ids = [tid for tid, secs in seconds_by.items() if secs > 0]
        activity_by = ReportsRepository.session_activity_by(db, organization_id, eligible_ids, member_ids, start_time, end_time, "task_id")
        triples = ReportsRepository.session_triples(db, organization_id, eligible_ids, member_ids, start_time, end_time, start_date, end_date)
        tasks = ReportsRepository.tasks_lookup(db, organization_id, included_ids)

        all_members = {uid for _, uid, _ in triples}
        entry_count = ReportsRepository.session_entry_count(db, organization_id, eligible_ids, member_ids, start_time, end_time, start_date, end_date)

        grouped = []
        for tid in included_ids:
            avg, count = activity_by.get(tid, (None, 0))
            task_name, _pid, project_name = tasks.get(tid, (f"Task {tid}", None, "Unknown project"))
            grouped.append(ReportsService._item(tid, task_name, seconds_by[tid], avg, count, project_name))
        grouped.sort(key=lambda item: -item["tracked_seconds"])

        return grouped, {"total_members": len(all_members), "total_entries": entry_count, "total_tasks": len(included_ids)}

    @staticmethod
    def _grouped_apps(db, organization_id, eligible_ids, member_ids, start_time, end_time, usage_type: UsageType):
        usage_value = usage_type.value
        seconds_by = ReportsRepository.app_usage_seconds_by_name(db, organization_id, eligible_ids, member_ids, start_time, end_time, usage_value)
        included_names = [name for name, secs in seconds_by.items() if secs > 0]
        activity_by = ReportsRepository.app_usage_activity_by_name(db, organization_id, eligible_ids, member_ids, start_time, end_time, usage_value)
        member_counts = ReportsRepository.app_usage_member_counts_by_name(db, organization_id, eligible_ids, member_ids, start_time, end_time, usage_value)
        all_members = ReportsRepository.app_usage_distinct_member_ids(db, organization_id, eligible_ids, member_ids, start_time, end_time, usage_value)
        entry_count = ReportsRepository.app_usage_entry_count(db, organization_id, eligible_ids, member_ids, start_time, end_time, usage_value)

        grouped = []
        for name in included_names:
            avg, count = activity_by.get(name, (None, 0))
            meta = f"{member_counts.get(name, 0)} members"
            grouped.append(ReportsService._item(name, name, seconds_by[name], avg, count, meta))
        grouped.sort(key=lambda item: -item["tracked_seconds"])

        return grouped, {"total_members": len(all_members), "total_entries": entry_count, "total_apps": len(included_names)}

    # --------------------------------------------------------- detail rows

    @staticmethod
    def build_detailed_logs(
        db: Session,
        current_user: User,
        dimension: ReportDimension,
        start_date: date,
        end_date: date,
        member_ids: Optional[list[int]],
        project_ids: Optional[list[int]],
        billing_type: Optional[BillableFilter],
        usage_type: UsageType,
        search: Optional[str],
        sort_by: str,
        sort_desc: bool,
        page: int,
        limit: int,
    ) -> dict:
        organization_id, member_ids, _eligible_projects, eligible_ids, start_time, end_time = (
            ReportsService._resolve_common(db, current_user, start_date, end_date, member_ids, project_ids, billing_type)
        )
        offset = (page - 1) * limit

        if dimension == ReportDimension.apps:
            rows, total = ReportsRepository.app_usage_detailed_logs(
                db, organization_id, eligible_ids, member_ids, start_time, end_time, usage_type.value,
                search, sort_by, sort_desc, offset, limit,
            )
            items = [
                {
                    "id": row.id,
                    "date": row.work_date,
                    "member_id": row.member_id,
                    "member_name": row.member_name,
                    "role": row.role,
                    "project_id": row.project_id,
                    "project_name": row.project_name,
                    "task_id": row.task_id,
                    "task_name": row.task_name,
                    "app": row.name if usage_type == UsageType.app else None,
                    "url": row.name if usage_type == UsageType.url else None,
                    "tracked_hours": round(row.tracked_seconds / 3600, 2),
                    "activity_percentage": round(row.activity_percentage, 2) if row.activity_percentage is not None else None,
                }
                for row in rows
            ]
        else:
            rows, total = ReportsRepository.session_detailed_logs(
                db, organization_id, eligible_ids, member_ids, start_time, end_time, start_date, end_date,
                search, sort_by, sort_desc, offset, limit,
            )
            items = [
                {
                    "id": row.id,
                    "date": row.work_date,
                    "member_id": row.member_id,
                    "member_name": row.member_name,
                    "role": row.role,
                    "project_id": row.project_id,
                    "project_name": row.project_name,
                    "task_id": row.task_id,
                    "task_name": row.task_name,
                    # Session-grain rows have no single app/URL to honestly
                    # attribute -- see docs/Reports_API.md.
                    "app": None,
                    "url": None,
                    "tracked_hours": round(row.tracked_seconds / 3600, 2),
                    "activity_percentage": round(row.activity_percentage, 2) if row.activity_percentage is not None else None,
                }
                for row in rows
            ]

        total_pages = (total + limit - 1) // limit if total else 0
        return {
            "start_date": start_date,
            "end_date": end_date,
            "items": items,
            "pagination": {"page": page, "limit": limit, "total": total, "total_pages": total_pages},
        }
