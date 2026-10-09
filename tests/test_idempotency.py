"""Idempotency-Key header on POST /jobs.

A client that retries after a timeout must not create a second job and
generate every certificate twice. Same key => same job, returned with 200.
"""

HEADER = {"Idempotency-Key": "order-2026-10-09-batch-7"}


def test_same_key_returns_same_job_and_200(client, payload):
    first = client.post("/jobs", json=payload, headers=HEADER)
    assert first.status_code == 202

    second = client.post("/jobs", json=payload, headers=HEADER)
    assert second.status_code == 200
    assert second.json()["job_id"] == first.json()["job_id"]
    assert second.json()["status_url"] == first.json()["status_url"]


def test_repeat_does_not_create_a_second_job_or_regenerate(client, payload):
    from app import models
    from app.db import SessionLocal

    client.post("/jobs", json=payload, headers=HEADER)
    client.post("/jobs", json=payload, headers=HEADER)
    client.post("/jobs", json=payload, headers=HEADER)

    with SessionLocal() as db:
        assert db.query(models.Job).count() == 1
        assert db.query(models.Certificate).count() == 3


def test_different_keys_create_different_jobs(client, payload):
    a = client.post("/jobs", json=payload, headers={"Idempotency-Key": "k1"}).json()["job_id"]
    b = client.post("/jobs", json=payload, headers={"Idempotency-Key": "k2"}).json()["job_id"]
    assert a != b


def test_no_header_always_creates_a_new_job(client, payload):
    a = client.post("/jobs", json=payload).json()["job_id"]
    b = client.post("/jobs", json=payload).json()["job_id"]
    assert a != b


def test_repeat_returns_current_counts_not_stale_ones(client, payload):
    """The replayed response reflects the job's state now, not at creation."""
    first = client.post("/jobs", json=payload, headers=HEADER).json()
    assert first["status"] == "PENDING"  # as returned before the worker ran

    replay = client.post("/jobs", json=payload, headers=HEADER).json()
    assert replay["job_id"] == first["job_id"]
    assert replay["status"] == "COMPLETED"  # worker has run by now
    assert replay["accepted"] == 3
