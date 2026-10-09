"""Input validation.

Envelope problems  -> 422, whole request rejected.
Per-recipient problems -> job accepted, that recipient recorded as FAILED with a reason.
"""
import pytest


# ---- envelope: 422 ----

@pytest.mark.parametrize("field", ["event_name", "issuer", "issue_date", "recipients"])
def test_missing_required_field_is_422(client, payload, field):
    del payload[field]
    assert client.post("/jobs", json=payload).status_code == 422


def test_empty_recipient_list_is_422(client, payload):
    payload["recipients"] = []
    assert client.post("/jobs", json=payload).status_code == 422


def test_blank_event_name_is_422(client, payload):
    payload["event_name"] = "   "
    assert client.post("/jobs", json=payload).status_code == 422


def test_invalid_issue_date_is_422(client, payload):
    payload["issue_date"] = "not-a-date"
    assert client.post("/jobs", json=payload).status_code == 422


def test_too_many_recipients_is_422(client, payload, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "MAX_RECIPIENTS_PER_JOB", 2)
    r = client.post("/jobs", json=payload)  # payload has 3
    assert r.status_code == 422
    assert "too many recipients" in r.json()["detail"]


# ---- per-recipient: accepted, individually FAILED ----

def _failed_items(client, job_id):
    return client.get(f"/jobs/{job_id}/certificates", params={"status": "FAILED"}).json()["items"]


def test_bad_email_fails_only_that_recipient(client, payload):
    payload["recipients"][1]["email"] = "not-an-email"
    r = client.post("/jobs", json=payload)
    assert r.status_code == 202
    body = r.json()
    assert body["accepted"] == 2
    assert body["rejected"] == 1

    failed = _failed_items(client, body["job_id"])
    assert len(failed) == 1
    assert failed[0]["recipient_email"] == "not-an-email"
    assert failed[0]["error_message"].startswith("validation:")
    assert "email" in failed[0]["error_message"]

    job = client.get(f"/jobs/{body['job_id']}").json()
    assert job["status"] == "PARTIAL"
    assert job["progress"]["succeeded"] == 2


def test_blank_name_fails_only_that_recipient(client, payload):
    payload["recipients"][0]["name"] = "   "
    body = client.post("/jobs", json=payload).json()
    assert body["rejected"] == 1
    failed = _failed_items(client, body["job_id"])
    assert failed[0]["recipient_email"] == "arun@example.com"
    assert "name" in failed[0]["error_message"]


def test_missing_name_fails_only_that_recipient(client, payload):
    del payload["recipients"][2]["name"]
    body = client.post("/jobs", json=payload).json()
    assert body["rejected"] == 1
    assert body["accepted"] == 2


def test_bad_completion_date_fails_only_that_recipient(client, payload):
    payload["recipients"][1]["completion_date"] = "31/02/2026"
    body = client.post("/jobs", json=payload).json()
    assert body["rejected"] == 1
    failed = _failed_items(client, body["job_id"])
    assert "completion_date" in failed[0]["error_message"]


def test_duplicate_email_fails_second_occurrence(client, payload):
    payload["recipients"].append({"name": "Arun Again", "email": "ARUN@example.com"})  # case-insensitive
    body = client.post("/jobs", json=payload).json()
    assert body["total"] == 4
    assert body["rejected"] == 1
    failed = _failed_items(client, body["job_id"])
    assert failed[0]["recipient_name"] == "Arun Again"
    assert "duplicate" in failed[0]["error_message"]


def test_all_recipients_invalid_marks_job_failed_without_running(client, payload):
    for r in payload["recipients"]:
        r["email"] = "bad"
    body = client.post("/jobs", json=payload).json()
    assert body["accepted"] == 0
    assert body["status"] == "FAILED"
    job = client.get(f"/jobs/{body['job_id']}").json()
    assert job["status"] == "FAILED"
    assert job["progress"]["succeeded"] == 0
