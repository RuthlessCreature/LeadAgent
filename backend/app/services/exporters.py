from __future__ import annotations

import csv
import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.models import LeadCard


def _flatten_cards(cards: list[LeadCard]) -> list[dict[str, str]]:
    rows = []
    for card in cards:
        primary = card.contacts[0] if card.contacts else None
        rows.append(
            {
                "lead_id": card.lead_id,
                "company": card.company,
                "contact_name": primary.name if primary else "",
                "role": primary.role if primary else "",
                "email": primary.email if primary else "",
                "linkedin": primary.linkedin if primary else "",
                "industry_score": f"{card.scores.industry:.2f}",
                "intent_score": f"{card.scores.intent:.2f}",
                "contact_score": f"{card.scores.contact:.2f}",
                "overall_score": f"{card.scores.overall:.2f}",
                "source_platform": card.source_platform.value,
                "summary": card.product_fit_summary,
            }
        )
    return rows


def export_cards_csv(cards: list[LeadCard]) -> bytes:
    rows = _flatten_cards(cards)
    output = io.StringIO()
    fieldnames = [
        "lead_id",
        "company",
        "contact_name",
        "role",
        "email",
        "linkedin",
        "industry_score",
        "intent_score",
        "contact_score",
        "overall_score",
        "source_platform",
        "summary",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def export_cards_pdf(cards: list[LeadCard]) -> bytes:
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream, pagesize=A4)
    width, height = A4
    x = 40
    y = height - 40

    pdf.setTitle("Lead Cards Export")
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(x, y, "Lead Cards Export")
    y -= 24

    for card in cards:
        if y < 120:
            pdf.showPage()
            y = height - 40
            pdf.setFont("Helvetica", 10)

        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(x, y, f"{card.company} ({card.source_platform.value})")
        y -= 14

        pdf.setFont("Helvetica", 10)
        summary = f"Scores I:{card.scores.industry:.1f}  N:{card.scores.intent:.1f}  C:{card.scores.contact:.1f}  O:{card.scores.overall:.1f}"
        pdf.drawString(x, y, summary)
        y -= 14

        if card.contacts:
            contact = card.contacts[0]
            contact_line = f"Contact: {contact.name} | {contact.role} | {contact.email}"
            pdf.drawString(x, y, contact_line[:110])
            y -= 14

        if card.product_fit_summary:
            pdf.drawString(x, y, f"Fit: {card.product_fit_summary[:110]}")
            y -= 14

        y -= 8

    pdf.save()
    stream.seek(0)
    return stream.read()


def simulate_crm_sync(target: str, cards: list[LeadCard]) -> dict:
    return {
        "target": target,
        "synced_records": len(cards),
        "status": "ok",
        "message": (
            "Native connector simulated. Replace with provider SDK for production sync."
        ),
    }
