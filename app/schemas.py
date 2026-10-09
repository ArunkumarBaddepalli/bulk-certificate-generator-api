"""Pydantic request / response schemas.

Validation is two-tier:

  1. JobCreate validates the *envelope* (event name, issuer, date, non-empty
     list). Failing this returns 422 -- the whole request is malformed.

  2. RecipientIn is intentionally loose. Each recipient is then checked
     individually against ValidRecipient inside the service. A recipient that
     fails is recorded as FAILED with the reason; the valid ones proceed.

So a client sending 500 recipients with 3 bad emails gets 497 certificates and
a precise list of the 3 problems, instead of a 422 and a forced resubmission.
"""
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------- request ----------

class RecipientIn(BaseModel):
    """Loose shape accepted at the API boundary. See module docstring.

    Every field is an optional plain string on purpose: typing completion_date
    as `date` here would make Pydantic reject the *whole request* when one
    recipient has a bad date, which defeats per-recipient validation.
    """
    name: str | None = None
    email: str | None = None
    completion_date: str | None = None


class ValidRecipient(BaseModel):
    """Strict per-row rules, applied in the service layer."""
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    completion_date: date | None = None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class JobCreate(BaseModel):
    event_name: str = Field(min_length=1, max_length=200)
    issuer: str = Field(min_length=1, max_length=200)
    issue_date: date
    recipients: list[RecipientIn] = Field(min_length=1)

    @field_validator("event_name", "issuer")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


# ---------- responses ----------

class JobAccepted(BaseModel):
    job_id: str
    status: str
    total: int
    accepted: int   # passed per-row validation, queued for generation
    rejected: int   # failed per-row validation, recorded as FAILED
    status_url: str


class JobProgress(BaseModel):
    total: int
    processed: int
    succeeded: int
    failed: int


class JobOut(BaseModel):
    id: str
    event_name: str
    issuer: str
    issue_date: date
    status: str
    progress: JobProgress
    created_at: datetime
    updated_at: datetime
    certificates_url: str


class CertificateOut(BaseModel):
    id: str
    job_id: str
    recipient_name: str | None
    recipient_email: str | None
    completion_date: date | None
    status: str
    error_message: str | None
    download_url: str | None


class CertificateList(BaseModel):
    job_id: str
    total: int
    limit: int
    offset: int
    items: list[CertificateOut]
