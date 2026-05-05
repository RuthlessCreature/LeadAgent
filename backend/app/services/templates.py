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
        "first": "{company} 的采购/增长目标可能有匹配机会",
        "follow": "关于供应商拓展支持的快速跟进",
        "restart": "重新同步 {company} 的找客想法",
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


def _pain_points_cn(lead: LeadCard) -> str:
    snippets = " ".join(lead.snippets).lower()
    points = []
    if "supplier" in snippets or "sourcing" in snippets:
        points.append("供应商发现")
    if "multilingual" in snippets:
        points.append("多语言触达")
    if "crm" in snippets:
        points.append("CRM 同步")
    if "automation" in snippets or "workflow" in snippets:
        points.append("流程自动化")
    return "、".join(points) if points else "高质量线索获取"


def generate_templates(lead: LeadCard, language: str = "EN") -> TemplateSet:
    lang = language.upper()
    if lang not in LANG_SUBJECTS:
        lang = "EN"

    subject = LANG_SUBJECTS[lang]
    pain_points = _pain_points_cn(lead) if lang == "CN" else _pain_points(lead)
    contact_name = lead.contacts[0].name if lead.contacts else "there"

    if lang == "CN":
        first_touch = (
            f"主题：{subject['first'].format(company=lead.company)}\n\n"
            f"{contact_name} 您好，\n"
            f"我们注意到 {lead.company} 可能正在优化 {pain_points}。"
            "LeadAgent 可以帮助团队发现、评分并激活高意向 B2B 线索，同时保留来源证据。\n"
            "这周是否方便安排 20 分钟快速沟通？"
        )

        follow_up = (
            f"主题：{subject['follow'].format(company=lead.company)}\n\n"
            f"{contact_name} 您好，\n"
            "简单跟进一下。我们可以分享类似团队如何做线索评分、来源审核和 CRM 交接。\n"
            "您这周是否方便简单聊一下？"
        )

        restart = (
            f"主题：{subject['restart'].format(company=lead.company)}\n\n"
            f"{contact_name} 您好，\n"
            "重新同步一下这个方向。如果现在时机更合适，我们可以先从一个地区和一个客户画像做小范围试点。"
        )
    else:
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
