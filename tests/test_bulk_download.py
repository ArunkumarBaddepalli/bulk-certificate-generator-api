"""ZIP download of every generated certificate in a job."""
import io
import zipfile


def _zip_from(client, job_id):
    r = client.get(f"/jobs/{job_id}/download")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    assert f"certificates_{job_id}.zip" in r.headers["content-disposition"]
    return zipfile.ZipFile(io.BytesIO(r.content))


def test_zip_contains_one_pdf_per_generated_certificate(client, payload):
    job_id = client.post("/jobs", json=payload).json()["job_id"]
    items = client.get(f"/jobs/{job_id}/certificates").json()["items"]

    zf = _zip_from(client, job_id)
    names = zf.namelist()
    assert len(names) == 3
    for item in items:
        matching = [n for n in names if item["id"] in n]
        assert len(matching) == 1, f"no zip entry for {item['id']}"
        assert matching[0].endswith(".pdf")
        assert zf.read(matching[0])[:5] == b"%PDF-"


def test_zip_filenames_use_sanitised_recipient_name(client, payload):
    payload["recipients"] = [{"name": "O'Brien / Smith", "email": "ob@example.com"}]
    job_id = client.post("/jobs", json=payload).json()["job_id"]
    (name,) = _zip_from(client, job_id).namelist()
    assert name.startswith("O_Brien___Smith_")
    assert "/" not in name and "'" not in name


def test_partial_job_zip_has_only_the_successes(client, payload):
    payload["recipients"][1]["email"] = "broken"
    job_id = client.post("/jobs", json=payload).json()["job_id"]
    assert client.get(f"/jobs/{job_id}").json()["status"] == "PARTIAL"
    assert len(_zip_from(client, job_id).namelist()) == 2


def test_zip_is_404_when_nothing_was_generated(client, payload):
    for r in payload["recipients"]:
        r["email"] = "bad"
    job_id = client.post("/jobs", json=payload).json()["job_id"]
    assert client.get(f"/jobs/{job_id}/download").status_code == 404


def test_zip_is_404_for_unknown_job(client):
    assert client.get("/jobs/nope/download").status_code == 404


def test_zip_is_409_while_job_not_finished(client, payload, monkeypatch):
    # Stop the worker from running so the job stays PENDING.
    from app import service

    monkeypatch.setattr(service, "process_job", lambda job_id: None)

    job_id = client.post("/jobs", json=payload).json()["job_id"]
    assert client.get(f"/jobs/{job_id}").json()["status"] == "PENDING"

    r = client.get(f"/jobs/{job_id}/download")
    assert r.status_code == 409
    assert r.json()["detail"]["status"] == "PENDING"
