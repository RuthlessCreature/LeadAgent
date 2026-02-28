from __future__ import annotations

from app.models import ComplianceResult, LeadCandidate


SENSITIVE_HINTS = ["passport", "ssn", "social security", "id number", "bank account"]


def scan_lead_compliance(lead: LeadCandidate) -> ComplianceResult:
    snippet = lead.raw_text_snippet.lower()
    sensitive_fields: list[str] = []

    if lead.email:
        sensitive_fields.append("email")
    if lead.phone:
        sensitive_fields.append("phone")
    if any(hint in snippet for hint in SENSITIVE_HINTS):
        sensitive_fields.append("raw_text_sensitive_marker")

    unsubscribe_detected = "unsubscribe" in snippet or "opt-out" in snippet
    contains_sensitive = len(sensitive_fields) > 0

    return ComplianceResult(
        lead_id=lead.lead_id,
        contains_sensitive=contains_sensitive,
        sensitive_fields=sensitive_fields,
        unsubscribe_detected=unsubscribe_detected,
        retention_days=365 if not contains_sensitive else 180,
    )
