"""Creating a generation job."""


def test_create_job_returns_202_and_job_id(client, payload):
    r = client.post("/jobs", json=payload)
    assert r.status_code == 202
    body = r.json()
    assert body["job_id"]
    assert body["total"] == 3
    assert body["accepted"] == 3
    assert body["rejected"] == 0
    assert body["status_url"] == f"/jobs/{body['job_id']}"


def test_created_job_is_fetchable(client, payload):
    job_id = client.post("/jobs", json=payload).json()["job_id"]
    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    job = r.json()
    assert job["id"] == job_id
    assert job["event_name"] == payload["event_name"]
    assert job["issuer"] == payload["issuer"]
    assert job["issue_date"] == payload["issue_date"]
    assert job["certificates_url"] == f"/jobs/{job_id}/certificates"


def test_each_job_gets_a_unique_id(client, payload):
    a = client.post("/jobs", json=payload).json()["job_id"]
    b = client.post("/jobs", json=payload).json()["job_id"]
    assert a != b


def test_unknown_job_is_404(client):
    assert client.get("/jobs/does-not-exist").status_code == 404
