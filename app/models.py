"""ORM models.

Two tables:
  jobs          -- one row per bulk request; aggregate counts + overall status
  certificates  -- one row per recipient; per-item status, error, file path

Per-item rows are what make failure isolation visible to the client: a job can
be PARTIAL with exactly the failed recipients listed, instead of all-or-nothing.
"""

import enum
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class JobStatus(enum.StrEnum):
    PENDING = "PENDING"  # created, worker not started yet
    RUNNING = "RUNNING"  # worker processing
    COMPLETED = "COMPLETED"  # every recipient generated
    PARTIAL = "PARTIAL"  # some generated, some failed
    FAILED = "FAILED"  # nothing generated


class CertStatus(enum.StrEnum):
    PENDING = "PENDING"
    GENERATED = "GENERATED"
    FAILED = "FAILED"


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    event_name: Mapped[str] = mapped_column(String(200), nullable=False)
    issuer: Mapped[str] = mapped_column(String(200), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING, nullable=False)
    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    succeeded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    certificates: Mapped[list["Certificate"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True, nullable=False)

    # Stored as provided, so a FAILED row still tells the client which recipient it was.
    recipient_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    recipient_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    status: Mapped[CertStatus] = mapped_column(Enum(CertStatus), default=CertStatus.PENDING, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    job: Mapped[Job] = relationship(back_populates="certificates")
