"""The root path serves the web client."""


def test_root_serves_html_ui(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "Bulk Certificate Generator" in r.text
    # The page talks to the real endpoints; make sure it references them.
    for path in ("/jobs", "/docs"):
        assert path in r.text


def test_root_is_not_in_openapi_schema(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/" not in paths
    assert "/jobs" in paths
