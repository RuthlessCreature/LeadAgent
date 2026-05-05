from __future__ import annotations

from app.models import LeadCandidate, LeadCard, LeadContact, ProductProfile


def to_lead_card(lead: LeadCandidate, product_profile: ProductProfile | None = None) -> LeadCard:
    fit_summary = "基于行业、意向和联系方式信号判断为潜在匹配。"
    if product_profile and product_profile.feature_tags:
        fit_summary = (
            "更适合 "
            + ", ".join(product_profile.feature_tags[:3])
            + " 相关场景，判断依据是已观察到的购买/业务信号。"
        )

    contact = LeadContact(
        name=lead.contact_name,
        role=lead.role,
        email=lead.email,
        linkedin=lead.linkedin,
        phone=lead.phone,
    )
    source_labels = {
        "demo": "演示数据",
        "public_web": "公开网页",
        "first_party_social": "第一方社媒线索",
        "licensed_database": "授权数据库",
        "first_party": "第一方入站",
        "customer_import": "客户自有导入",
        "partner_referral": "合作伙伴推荐",
    }
    verification_labels = {
        "unverified": "未验证",
        "company_verified": "公司已验证",
        "email_verified": "邮箱已验证",
        "phone_verified": "电话已验证",
        "fully_verified": "完整验证",
    }
    source_bits = [source_labels.get(lead.source_type.value, lead.source_type.value)]
    if lead.source_label:
        source_bits.append(lead.source_label)
    if lead.verification_status.value != "unverified":
        source_bits.append(verification_labels.get(lead.verification_status.value, lead.verification_status.value))
    return LeadCard(
        lead_id=lead.lead_id,
        company=lead.company,
        contacts=[contact] if lead.contact_name or lead.email else [],
        product_fit_summary=fit_summary,
        scores=lead.scores,
        snippets=[lead.raw_text_snippet],
        source_platform=lead.platform,
        source_summary=" · ".join(source_bits),
        consent_status=lead.consent_status,
        verification_status=lead.verification_status,
    )
