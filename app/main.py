"""FastAPI application: routes only. Business logic lives in service.py."""
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from . import config, models, schemas, service
from .db import get_db, init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Bulk Certificate Generator API",
    version="1.0.0",
    description=(
        "Submit a list of recipients once; certificates are generated in the "
        "background and can be polled and downloaded per recipient."
    ),
    lifespan=lifespan,
)


# ---------- serializers ----------

def _job_out(job: models.Job) -> dict:
    return {
        "id": job.id,
        "event_name": job.event_name,
        "issuer": job.issuer,
        "issue_date": job.issue_date,
        "status": job.status.value,
        "progress": {
            "total": job.total,
            "processed": job.succeeded + job.failed,
            "succeeded": job.succeeded,
            "failed": job.failed,
        },
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "certificates_url": f"/jobs/{job.id}/certificates",
    }


def _cert_out(cert: models.Certificate) -> dict:
    return {
        "id": cert.id,
        "job_id": cert.job_id,
        "recipient_name": cert.recipient_name,
        "recipient_email": cert.recipient_email,
        "completion_date": cert.completion_date,
        "status": cert.status.value,
        "error_message": cert.error_message,
        "download_url": (
            f"/certificates/{cert.id}/download"
            if cert.status == models.CertStatus.GENERATED
            else None
        ),
    }


def _get_job_or_404(db: Session, job_id: str) -> models.Job:
    job = db.get(models.Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


# ---------- routes ----------

@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


@app.post("/jobs", status_code=202, response_model=schemas.JobAccepted, tags=["jobs"])
def create_job(
    payload: schemas.JobCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Submit a bulk certificate request.

    Returns 202 immediately with a job id. Generation runs in the background;
    poll GET /jobs/{id} for progress.
    """
    if len(payload.recipients) > config.MAX_RECIPIENTS_PER_JOB:
        raise HTTPException(
            status_code=422,
            detail=f"too many recipients: maximum {config.MAX_RECIPIENTS_PER_JOB} per job",
        )

    job = service.create_job(db, payload)

    if job.status != models.JobStatus.FAILED:
        background.add_task(service.process_job, job.id)

    return {
        "job_id": job.id,
        "status": job.status.value,
        "total": job.total,
        "accepted": job.total - job.failed,
        "rejected": job.failed,
        "status_url": f"/jobs/{job.id}",
    }


@app.get("/jobs/{job_id}", response_model=schemas.JobOut, tags=["jobs"])
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Job status and aggregate progress."""
    return _job_out(_get_job_or_404(db, job_id))


@app.get("/jobs/{job_id}/certificates", response_model=schemas.CertificateList, tags=["certificates"])
def list_certificates(
    job_id: str,
    status: models.CertStatus | None = Query(default=None, description="Filter by status"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Per-recipient results. Use ?status=FAILED to see exactly what went wrong."""
    _get_job_or_404(db, job_id)

    query = db.query(models.Certificate).filter_by(job_id=job_id)
    if status is not None:
        query = query.filter_by(status=status)

    total = query.count()
    items = query.order_by(models.Certificate.created_at).offset(offset).limit(limit).all()

    return {
        "job_id": job_id,
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_cert_out(c) for c in items],
    }


@app.get("/certificates/{cert_id}/download", tags=["certificates"])
def download_certificate(cert_id: str, db: Session = Depends(get_db)):
    """Download one generated certificate as PDF."""
    cert = db.get(models.Certificate, cert_id)
    if cert is None:
        raise HTTPException(status_code=404, detail="certificate not found")
    if cert.status != models.CertStatus.GENERATED or not cert.file_path:
        raise HTTPException(
            status_code=409,
            detail={"status": cert.status.value, "error_message": cert.error_message},
        )

    safe_name = "".join(ch if ch.isalnum() else "_" for ch in (cert.recipient_name or "certificate"))
    return FileResponse(
        cert.file_path,
        media_type="application/pdf",
        filename=f"certificate_{safe_name}.pdf",
    )
