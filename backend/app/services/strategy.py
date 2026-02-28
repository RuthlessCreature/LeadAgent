from __future__ import annotations

from collections import Counter

from app.models import LeadCandidate, Platform, StrategyDecision


PLATFORM_ORDER = [
    Platform.linkedin,
    Platform.google,
    Platform.b2b_db,
    Platform.facebook,
    Platform.youtube,
    Platform.tiktok,
]


def decide_next_actions(query: str, leads: list[LeadCandidate]) -> StrategyDecision:
    if not leads:
        return StrategyDecision(
            continue_search=True,
            next_queries=[f"{query} suppliers", f"{query} procurement", f"{query} buyer intent"],
            next_platforms=[Platform.linkedin, Platform.google, Platform.b2b_db],
            reason="No leads found; broaden query and retry high-yield platforms.",
        )

    high = [lead for lead in leads if lead.scores.overall >= 75]
    medium = [lead for lead in leads if 50 <= lead.scores.overall < 75]
    avg_score = sum(lead.scores.overall for lead in leads) / max(len(leads), 1)

    platform_counts = Counter(lead.platform for lead in leads)
    weak_platforms = [platform for platform in PLATFORM_ORDER if platform_counts.get(platform, 0) == 0]

    if len(high) >= 5:
        return StrategyDecision(
            continue_search=False,
            next_queries=[],
            next_platforms=[],
            reason="Enough high-score leads were found.",
        )

    next_queries = []
    if avg_score < 45:
        next_queries.extend([f"{query} hiring procurement", f"{query} RFQ", f"{query} sourcing director"])
    elif len(high) < 3:
        next_queries.extend([f"{query} b2b buyers", f"{query} crm sync", f"{query} supplier search"])
    else:
        next_queries.extend([f"{query} expansion"])

    next_platforms = weak_platforms[:3]
    if not next_platforms:
        next_platforms = [Platform.linkedin, Platform.b2b_db]

    reason = (
        "High-score leads are limited; continue search with intent-heavy keywords."
        if len(high) < 3
        else "Lead pool is moderate; run one more targeted iteration."
    )

    if medium and avg_score > 60:
        reason = "Medium/high score distribution is healthy; one precision pass is recommended."

    return StrategyDecision(
        continue_search=True,
        next_queries=next_queries,
        next_platforms=next_platforms,
        reason=reason,
    )
