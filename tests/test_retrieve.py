"""Listing and downloading generated certificates."""


def test_list_returns_all_with_download_urls(client, payload):
    job_id = client.post("/jobs", json=payload).json()["job_id"]
    r = client.get(f"/jobs/{job_id}/certificates")
    assert r.status_code == 200
    body = r.json()
    assert body["job_id"] == job_id
    assert body["total"] == 3
    assert len(body["items"]) == 3
    for item in body["items"]:
        assert item["status"] == "GENERATED"
        assert item["download_url"] == f"/certificates/{item['id']}/download"


def test_list_filters_by_status(client, payload):
    payload["recipients"][0]["email"] = "nope"
    job_id = client.post("/jobs", json=payload).json()["job_id"]

    ok = client.get(f"/jobs/{job_id}/certificates", params={"status": "GENERATED"}).json()
    bad = client.get(f"/jobs/{job_id}/certificates", params={"status": "FAILED"}).json()
    assert ok["total"] == 2
    assert bad["total"] == 1


def test_list_paginates(client, payload):
    job_id = client.post("/jobs", json=payload).json()["job_id"]
    page1 = client.get(f"/jobs/{job_id}/certificates", params={"limit": 2, "offset": 0}).json()
    page2 = client.get(f"/jobs/{job_id}/certificates", params={"limit": 2, "offset": 2}).json()
    assert page1["total"] == 3
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 1
    ids = {i["id"] for i in page1["items"]} | {i["id"] for i in page2["items"]}
    assert len(ids) == 3


def test_list_for_unknown_job_is_404(client):
    assert client.get("/jobs/nope/certificates").status_code == 404


def test_download_returns_pdf(client, payload):
    job_id = client.post("/jobs", json=payload).json()["job_id"]
    item = client.get(f"/jobs/{job_id}/certificates").json()["items"][0]

    r = client.get(item["download_url"])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers["content-disposition"]
    assert ".pdf" in r.headers["content-disposition"]
    assert r.content[:5] == b"%PDF-"


def test_download_unknown_certificate_is_404(client):
    assert client.get("/certificates/nope/download").status_code == 404


def test_download_inline_renders_in_browser(client, payload):
    job_id = client.post("/jobs", json=payload).json()["job_id"]
    item = client.get(f"/jobs/{job_id}/certificates").json()["items"][0]

    r = client.get(item["download_url"], params={"inline": 1})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"].startswith("inline")
    assert r.content[:5] == b"%PDF-"
