from __future__ import annotations

from app.models import LeadCandidate, LeadCard, LeadContact, ProductProfile


def to_lead_card(lead: LeadCandidate, product_profile: ProductProfile | None = None) -> LeadCard:
    fit_summary = "Potential fit based on industry/intent/contact signals."
    if product_profile and product_profile.feature_tags:
        fit_summary = (
            "Best fit for "
            + ", ".join(product_profile.feature_tags[:3])
            + " workflows based on observed buying signals."
        )

    contact = LeadContact(
        name=lead.contact_name,
        role=lead.role,
        email=lead.email,
        linkedin=lead.linkedin,
        phone=lead.phone,
    )
    return LeadCard(
        lead_id=lead.lead_id,
        company=lead.company,
        contacts=[contact] if lead.contact_name or lead.email else [],
        product_fit_summary=fit_summary,
        scores=lead.scores,
        snippets=[lead.raw_text_snippet],
        source_platform=lead.platform,
    )
