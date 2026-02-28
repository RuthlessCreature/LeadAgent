from __future__ import annotations

from app.models import LeadCard, TemplateSet


LANG_SUBJECTS = {
    "EN": {
        "first": "Potential fit for {company}'s sourcing goals",
        "follow": "Quick follow-up on supplier expansion support",
        "restart": "Re-opening this idea for {company}",
    },
    "ES": {
        "first": "Posible ajuste para los objetivos de compras de {company}",
        "follow": "Seguimiento rapido sobre expansion de proveedores",
        "restart": "Retomando esta idea para {company}",
    },
    "FR": {
        "first": "Piste pertinente pour les objectifs achats de {company}",
        "follow": "Relance rapide sur l'expansion fournisseurs",
        "restart": "Reprise de cette idee pour {company}",
    },
    "DE": {
        "first": "Moeglicher Fit fuer die Beschaffungsziele von {company}",
        "follow": "Kurzes Follow-up zur Lieferantenerweiterung",
        "restart": "Diese Idee fuer {company} erneut aufgreifen",
    },
    "CN": {
        "first": "[CN] Potential fit for {company} sourcing goals",
        "follow": "[CN] Follow-up on supplier expansion support",
        "restart": "[CN] Re-opening this idea for {company}",
    },
}


def _pain_points(lead: LeadCard) -> str:
    snippets = " ".join(lead.snippets).lower()
    points = []
    if "supplier" in snippets or "sourcing" in snippets:
        points.append("supplier discovery")
    if "multilingual" in snippets:
        points.append("multilingual outreach")
    if "crm" in snippets:
        points.append("crm synchronization")
    if "automation" in snippets or "workflow" in snippets:
        points.append("workflow automation")
    return ", ".join(points) if points else "qualified lead acquisition"


def generate_templates(lead: LeadCard, language: str = "EN") -> TemplateSet:
    lang = language.upper()
    if lang not in LANG_SUBJECTS:
        lang = "EN"

    subject = LANG_SUBJECTS[lang]
    pain_points = _pain_points(lead)
    contact_name = lead.contacts[0].name if lead.contacts else "there"

    first_touch = (
        f"Subject: {subject['first'].format(company=lead.company)}\n\n"
        f"Hi {contact_name},\n"
        f"We noticed {lead.company} may be improving {pain_points}. "
        "Our platform helps teams find, score, and activate high-intent B2B leads faster.\n"
        "Would you like a 20-minute walkthrough this week?"
    )

    follow_up = (
        f"Subject: {subject['follow'].format(company=lead.company)}\n\n"
        f"Hi {contact_name},\n"
        "Just checking in. We can share examples of lead scoring and CRM sync "
        "used by teams with similar sourcing workflows.\n"
        "Open to a brief call?"
    )

    restart = (
        f"Subject: {subject['restart'].format(company=lead.company)}\n\n"
        f"Hi {contact_name},\n"
        "Revisiting this in case timing is better now. "
        "If helpful, we can start with a pilot focused on one region and one ICP profile."
    )

    return TemplateSet(first_touch=first_touch, follow_up=follow_up, restart=restart, language=lang)
