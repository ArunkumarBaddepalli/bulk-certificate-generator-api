"""Certificate generation produces real PDFs."""

from datetime import date

import pytest


def test_pdf_written_to_disk_for_each_recipient(client, payload):
    job_id = client.post("/jobs", json=payload).json()["job_id"]
    items = client.get(f"/jobs/{job_id}/certificates").json()["items"]
    assert len(items) == 3

    from app import config

    for item in items:
        assert item["status"] == "GENERATED"
        pdf = config.CERT_STORAGE_DIR / job_id / f"{item['id']}.pdf"
        assert pdf.exists(), f"missing {pdf}"
        assert pdf.read_bytes()[:5] == b"%PDF-"


def test_render_function_directly(tmp_path):
    """Unit-level check of the template, independent of the API."""
    from app.generator import render_certificate

    out = tmp_path / "x.pdf"
    render_certificate(
        path=out,
        recipient_name="Test Person",
        event_name="Event",
        issuer="Issuer",
        issue_date=date(2026, 10, 7),
        completion_date=None,
        certificate_id="abc",
    )
    data = out.read_bytes()
    assert data.startswith(b"%PDF-")
    assert len(data) > 1000


def test_render_creates_missing_parent_folders(tmp_path):
    from app.generator import render_certificate

    out = tmp_path / "a" / "b" / "c.pdf"
    render_certificate(
        path=out,
        recipient_name="P",
        event_name="E",
        issuer="I",
        issue_date=date(2026, 1, 1),
        completion_date=date(2025, 12, 31),
        certificate_id="id",
    )
    assert out.exists()


def test_render_requires_a_name(tmp_path):
    from app.generator import render_certificate

    with pytest.raises(ValueError):
        render_certificate(
            path=tmp_path / "x.pdf",
            recipient_name="   ",
            event_name="E",
            issuer="I",
            issue_date=date(2026, 1, 1),
            completion_date=None,
            certificate_id="id",
        )
