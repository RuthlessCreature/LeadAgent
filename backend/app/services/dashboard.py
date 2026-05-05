from __future__ import annotations

from collections import Counter

from app.models import ConsentStatus, DashboardMetrics, LeadCandidate, OutreachEvent


def build_dashboard(leads: list[LeadCandidate], events: list[OutreachEvent]) -> DashboardMetrics:
    new_leads = len(leads)
    high_score = len([lead for lead in leads if lead.scores.overall >= 75])
    high_ratio = (high_score / new_leads) if new_leads else 0.0

    sent = len([event for event in events if event.event_type.value == "sent"])
    opened = len([event for event in events if event.event_type.value == "opened"])
    replied = len([event for event in events if event.event_type.value == "replied"])

    open_rate = (opened / sent) if sent else 0.0
    reply_rate = (replied / sent) if sent else 0.0

    platform_counts = Counter(lead.platform.value for lead in leads)
    source_counts = Counter(lead.source_type.value for lead in leads)
    compliant_leads = len([lead for lead in leads if lead.consent_status != ConsentStatus.do_not_contact])

    return DashboardMetrics(
        new_leads=new_leads,
        high_score_ratio=round(high_ratio, 4),
        email_open_rate=round(open_rate, 4),
        email_reply_rate=round(reply_rate, 4),
        platform_contribution=dict(platform_counts),
        source_contribution=dict(source_counts),
        compliant_leads=compliant_leads,
    )
