"""Renders one certificate PDF from the predefined template.

Pure function: takes recipient + job details, writes one PDF, returns nothing.
Raises on any failure so the caller (service.process_job) can record the error
against that single certificate without affecting the rest of the batch.

ReportLab: pure Python, no system binaries (unlike WeasyPrint / wkhtmltopdf),
so `pip install` is the entire setup.
"""

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

PAGE_SIZE = landscape(A4)
ACCENT = colors.HexColor("#1F3A5F")


def render_certificate(
    *,
    path: Path,
    recipient_name: str,
    event_name: str,
    issuer: str,
    issue_date: date,
    completion_date: date | None,
    certificate_id: str,
) -> None:
    if not recipient_name or not recipient_name.strip():
        raise ValueError("recipient_name is required to render a certificate")

    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = PAGE_SIZE
    c = canvas.Canvas(str(path), pagesize=PAGE_SIZE)
    c.setTitle(f"Certificate - {recipient_name}")
    c.setAuthor(issuer)

    # Double border
    c.setStrokeColor(ACCENT)
    c.setLineWidth(6)
    c.rect(1.0 * cm, 1.0 * cm, width - 2.0 * cm, height - 2.0 * cm)
    c.setLineWidth(1.5)
    c.rect(1.4 * cm, 1.4 * cm, width - 2.8 * cm, height - 2.8 * cm)

    # Heading
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 34)
    c.drawCentredString(width / 2, height - 4.0 * cm, "CERTIFICATE OF COMPLETION")

    # Body
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 16)
    c.drawCentredString(width / 2, height - 6.0 * cm, "This is to certify that")

    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(width / 2, height - 8.0 * cm, recipient_name.strip())
    c.setLineWidth(1)
    c.line(width / 2 - 9 * cm, height - 8.5 * cm, width / 2 + 9 * cm, height - 8.5 * cm)

    c.setFont("Helvetica", 16)
    c.drawCentredString(width / 2, height - 10.0 * cm, "has successfully completed")

    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(width / 2, height - 11.8 * cm, event_name)

    done_on = completion_date or issue_date
    c.setFont("Helvetica", 13)
    c.drawCentredString(width / 2, height - 13.5 * cm, f"Completed on {done_on.strftime('%d %B %Y')}")

    # Footer
    c.drawString(3 * cm, 3.2 * cm, f"Issued by: {issuer}")
    c.drawRightString(width - 3 * cm, 3.2 * cm, f"Issue date: {issue_date.strftime('%d %B %Y')}")

    c.setFont("Helvetica", 8)
    c.setFillColor(colors.grey)
    c.drawCentredString(width / 2, 1.9 * cm, f"Certificate ID: {certificate_id}")

    c.showPage()
    c.save()
