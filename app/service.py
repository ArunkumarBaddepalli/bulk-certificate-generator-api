"""Job orchestration: create the job, then generate certificates in the background.

Failure isolation lives here. Every recipient is wrapped in its own try/except at
both stages (validation, then generation), so one bad row records one FAILED
certificate and the loop continues.
"""

import logging

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import config, models, schemas
from .db import SessionLocal
from .generator import render_certificate

log = logging.getLogger(__name__)

TERMINAL_STATES = {models.JobStatus.COMPLETED, models.JobStatus.PARTIAL, models.JobStatus.FAILED}


def _format_validation_error(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err["loc"]) or "recipient"
        parts.append(f"{loc}: {err['msg']}")
    return "; ".join(parts)[:500]


def get_job_by_idempotency_key(db: Session, key: str) -> models.Job | None:
    return db.query(models.Job).filter_by(idempotency_key=key).one_or_none()


def create_job(db: Session, payload: schemas.JobCreate, idempotency_key: str | None = None) -> models.Job:
    """Persist the job and one certificate row per recipient.

    Recipients failing strict validation (or duplicating an earlier email in
    the same request) are stored immediately as FAILED with the reason. Valid
    ones are stored as PENDING for the background worker.

    If `idempotency_key` is given and a job with that key already exists, the
    existing job is returned and nothing new is written.
    """
    if idempotency_key:
        existing = get_job_by_idempotency_key(db, idempotency_key)
        if existing is not None:
            return existing

    job = models.Job(
        event_name=payload.event_name,
        issuer=payload.issuer,
        issue_date=payload.issue_date,
        total=len(payload.recipients),
        idempotency_key=idempotency_key or None,
    )
    db.add(job)
    db.flush()  # assigns job.id

    seen_emails: set[str] = set()
    rejected = 0

    for raw in payload.recipients:
        # Keep whatever the client sent, so a FAILED row is still identifiable.
        cert = models.Certificate(
            job_id=job.id,
            recipient_name=(raw.name or "").strip()[:120] or None,
            recipient_email=(raw.email or "").strip()[:254] or None,
        )
        try:
            valid = schemas.ValidRecipient(
                name=raw.name, email=raw.email, completion_date=raw.completion_date
            )
            key = valid.email.lower()
            if key in seen_emails:
                raise ValueError(f"duplicate email in request: {valid.email}")
            seen_emails.add(key)

            cert.recipient_name = valid.name
            cert.recipient_email = valid.email
            cert.completion_date = valid.completion_date
            cert.status = models.CertStatus.PENDING
        except ValidationError as exc:
            cert.status = models.CertStatus.FAILED
            cert.error_message = "validation: " + _format_validation_error(exc)
            rejected += 1
        except ValueError as exc:
            cert.status = models.CertStatus.FAILED
            cert.error_message = f"validation: {exc}"
            rejected += 1
        db.add(cert)

    job.failed = rejected
    if rejected == job.total:
        # Nothing to generate; the worker is not scheduled for this job.
        job.status = models.JobStatus.FAILED

    try:
        db.commit()
    except IntegrityError:
        # Two concurrent requests with the same Idempotency-Key: the UNIQUE
        # constraint makes the second one lose. Discard ours, return the winner.
        db.rollback()
        if idempotency_key:
            existing = get_job_by_idempotency_key(db, idempotency_key)
            if existing is not None:
                return existing
        raise
    db.refresh(job)
    return job


def process_job(job_id: str) -> None:
    """Background worker entry point.

    Runs after the HTTP response, so it opens its own session. Must never
    raise: an exception here would be swallowed by the task runner and the
    job would sit in RUNNING forever. Everything is caught and recorded.
    """
    db = SessionLocal()
    try:
        # Atomic claim: only a PENDING job flips to RUNNING, and only one caller
        # wins. Guards against the same job being queued twice (e.g. a lost
        # idempotency race) and against re-processing a finished job.
        claimed = (
            db.query(models.Job)
            .filter_by(id=job_id, status=models.JobStatus.PENDING)
            .update({"status": models.JobStatus.RUNNING}, synchronize_session=False)
        )
        db.commit()
        if not claimed:
            return

        job = db.get(models.Job, job_id)

        pending = (
            db.query(models.Certificate)
            .filter_by(job_id=job_id, status=models.CertStatus.PENDING)
            .order_by(models.Certificate.created_at)
            .all()
        )

        for cert in pending:
            try:
                out_path = config.CERT_STORAGE_DIR / job.id / f"{cert.id}.pdf"
                render_certificate(
                    path=out_path,
                    recipient_name=cert.recipient_name or "",
                    event_name=job.event_name,
                    issuer=job.issuer,
                    issue_date=job.issue_date,
                    completion_date=cert.completion_date,
                    certificate_id=cert.id,
                )
                cert.file_path = str(out_path)
                cert.status = models.CertStatus.GENERATED
                job.succeeded += 1
            except Exception as exc:  # noqa: BLE001 -- isolate per-item failure
                log.exception("certificate %s in job %s failed", cert.id, job_id)
                cert.status = models.CertStatus.FAILED
                cert.error_message = f"generation: {type(exc).__name__}: {exc}"[:500]
                job.failed += 1

            # Commit per item so GET /jobs/{id} shows live progress on long batches.
            db.commit()

        if job.succeeded == 0:
            job.status = models.JobStatus.FAILED
        elif job.failed == 0:
            job.status = models.JobStatus.COMPLETED
        else:
            job.status = models.JobStatus.PARTIAL
        db.commit()

    except Exception:  # noqa: BLE001 -- last line of defence, see docstring
        log.exception("job %s crashed", job_id)
        try:
            job = db.get(models.Job, job_id)
            if job is not None:
                job.status = models.JobStatus.FAILED
                db.commit()
        except Exception:  # noqa: BLE001
            log.exception("could not mark job %s FAILED", job_id)
    finally:
        db.close()
