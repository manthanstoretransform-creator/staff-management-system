from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.feedback_request import FeedbackRequest


class FeedbackRepository:
    """Data access for `feedback_requests`. No business rules live here."""

    @staticmethod
    def create(
        db: Session,
        *,
        organization_id: int,
        user_id: int,
        category: str,
        message: str,
        status: str,
    ) -> FeedbackRequest:
        feedback = FeedbackRequest(
            organization_id=organization_id,
            user_id=user_id,
            category=category,
            message=message,
            status=status,
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        return feedback

    @staticmethod
    def get_by_id(db: Session, feedback_id: int) -> Optional[FeedbackRequest]:
        return db.scalar(
            select(FeedbackRequest).where(FeedbackRequest.id == feedback_id)
        )

    @staticmethod
    def list_by_organization(
        db: Session, organization_id: int, limit: int = 100
    ) -> List[FeedbackRequest]:
        return list(
            db.scalars(
                select(FeedbackRequest)
                .where(FeedbackRequest.organization_id == organization_id)
                .order_by(FeedbackRequest.created_at.desc())
                .limit(limit)
            ).all()
        )
