from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class ProjectStatus(Base):
    __tablename__ = "project_statuses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    color: Mapped[str] = mapped_column(String(7), nullable=False)


class TaskStatus(Base):
    __tablename__ = "task_statuses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    color: Mapped[str] = mapped_column(String(7), nullable=False)