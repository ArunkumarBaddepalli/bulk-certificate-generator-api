"""One certificate failing during *generation* must not stop the others.

The validation tests cover failures at submission time. This covers the other
stage: a recipient that passes validation but blows up while rendering. We
inject that by patching the renderer to raise for one specific name.
"""

import pytest


@pytest.fixture
def explode_for_priya(monkeypatch):
    from app import service
    from app.generator import render_certificate as real_render

    def flaky_render(*, recipient_name, **kwargs):
        if recipient_name == "Priya Sharma":
            raise RuntimeError("simulated renderer crash")
        return real_render(recipient_name=recipient_name, **kwargs)

    # service imported the symbol directly, so patch it on the service module.
    monkeypatch.setattr(service, "render_certificate", flaky_render)


def test_one_generation_failure_is_isolated(client, payload, explode_for_priya):
    body = client.post("/jobs", json=payload).json()
    assert body["accepted"] == 3  # all passed validation; failure happens later

    job = client.get(f"/jobs/{body['job_id']}").json()
    assert job["status"] == "PARTIAL"
    assert job["progress"] == {"total": 3, "processed": 3, "succeeded": 2, "failed": 1}

    items = client.get(f"/jobs/{body['job_id']}/certificates").json()["items"]
    by_name = {i["recipient_name"]: i for i in items}

    assert by_name["Arun Kumar"]["status"] == "GENERATED"
    assert by_name["Rahul Verma"]["status"] == "GENERATED"

    failed = by_name["Priya Sharma"]
    assert failed["status"] == "FAILED"
    assert failed["error_message"].startswith("generation:")
    assert "simulated renderer crash" in failed["error_message"]
    assert failed["download_url"] is None


def test_failed_certificate_download_is_409_with_reason(client, payload, explode_for_priya):
    job_id = client.post("/jobs", json=payload).json()["job_id"]
    failed = client.get(f"/jobs/{job_id}/certificates", params={"status": "FAILED"}).json()["items"][0]

    r = client.get(f"/certificates/{failed['id']}/download")
    assert r.status_code == 409
    assert r.json()["detail"]["status"] == "FAILED"
    assert "simulated" in r.json()["detail"]["error_message"]


def test_every_recipient_failing_at_generation_marks_job_failed(client, payload, monkeypatch):
    from app import service

    def always_fail(**kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(service, "render_certificate", always_fail)

    job_id = client.post("/jobs", json=payload).json()["job_id"]
    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] == "FAILED"
    assert job["progress"]["failed"] == 3
    assert job["progress"]["succeeded"] == 0
