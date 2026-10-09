"""Job status and progress reporting."""


def test_all_success_is_completed(client, payload):
    job_id = client.post("/jobs", json=payload).json()["job_id"]
    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] == "COMPLETED"
    assert job["progress"] == {"total": 3, "processed": 3, "succeeded": 3, "failed": 0}


def test_mixed_result_is_partial(client, payload):
    payload["recipients"][0]["email"] = "broken"
    job_id = client.post("/jobs", json=payload).json()["job_id"]
    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] == "PARTIAL"
    assert job["progress"] == {"total": 3, "processed": 3, "succeeded": 2, "failed": 1}


def test_processed_equals_succeeded_plus_failed(client, payload):
    payload["recipients"][1]["email"] = "broken"
    payload["recipients"][2]["name"] = ""
    job_id = client.post("/jobs", json=payload).json()["job_id"]
    p = client.get(f"/jobs/{job_id}").json()["progress"]
    assert p["processed"] == p["succeeded"] + p["failed"] == 3


def test_status_is_from_the_documented_set(client, payload):
    job_id = client.post("/jobs", json=payload).json()["job_id"]
    status = client.get(f"/jobs/{job_id}").json()["status"]
    assert status in {"PENDING", "RUNNING", "COMPLETED", "PARTIAL", "FAILED"}


def test_timestamps_present(client, payload):
    job_id = client.post("/jobs", json=payload).json()["job_id"]
    job = client.get(f"/jobs/{job_id}").json()
    assert "T" in job["created_at"]
    assert "T" in job["updated_at"]
