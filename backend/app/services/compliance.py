from __future__ import annotations

from app.models import ComplianceResult, ConsentStatus, LeadCandidate, LeadSourceType


SENSITIVE_HINTS = ["passport", "ssn", "social security", "id number", "bank account"]
HIGH_RISK_SOURCES = {LeadSourceType.demo}
MEDIUM_RISK_SOURCES = {LeadSourceType.public_web, LeadSourceType.partner_referral}


def scan_lead_compliance(lead: LeadCandidate) -> ComplianceResult:
    snippet = lead.raw_text_snippet.lower()
    sensitive_fields: list[str] = []

    if lead.email:
        sensitive_fields.append("email")
    if lead.phone:
        sensitive_fields.append("phone")
    if any(hint in snippet for hint in SENSITIVE_HINTS):
        sensitive_fields.append("raw_text_sensitive_marker")

    unsubscribe_detected = "unsubscribe" in snippet or "opt-out" in snippet or lead.consent_status == ConsentStatus.do_not_contact
    contains_sensitive = len(sensitive_fields) > 0
    if lead.consent_status == ConsentStatus.do_not_contact:
        source_risk_level = "high"
        recommended_action = "禁止触达，仅为退订合规保留必要记录。"
    elif lead.source_type in HIGH_RISK_SOURCES:
        source_risk_level = "high"
        recommended_action = "这是演示记录，真实触达前请替换为客户自有或授权数据。"
    elif lead.source_type in MEDIUM_RISK_SOURCES or lead.consent_status == ConsentStatus.unknown:
        source_risk_level = "medium"
        recommended_action = "触达前请核验来源 URL、法律依据和联系方式准确性。"
    else:
        source_risk_level = "low"
        recommended_action = "可进入人工审核。发送前确认触达依据，并尊重退订请求。"

    return ComplianceResult(
        lead_id=lead.lead_id,
        contains_sensitive=contains_sensitive,
        sensitive_fields=sensitive_fields,
        unsubscribe_detected=unsubscribe_detected,
        retention_days=90 if source_risk_level == "high" else (180 if contains_sensitive else 365),
        source_risk_level=source_risk_level,
        recommended_action=recommended_action,
    )
