from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Protocol
from uuid import NAMESPACE_URL, uuid4, uuid5

from app.models import (
    ProductOffer,
    SourcingPlan,
    SourcingPlanRequest,
    SourcingQuery,
    SourcingReport,
    SourcingReportRequest,
    SupplierCandidate,
)


PLATFORM_LABELS = {
    "1688": "1688",
    "alibaba": "Alibaba.com",
    "made_in_china": "Made-in-China",
    "globalsources": "GlobalSources",
    "public_web": "Public supplier web",
}

ZH_HINTS = {
    "bag": "包",
    "bottle": "瓶",
    "box": "盒",
    "cable": "线缆",
    "cap": "帽子",
    "case": "保护壳",
    "charger": "充电器",
    "cup": "杯",
    "fabric": "面料",
    "gift": "礼品",
    "glove": "手套",
    "kit": "套装",
    "lamp": "灯",
    "led": "LED",
    "light": "灯",
    "machine": "机器",
    "packaging": "包装",
    "phone": "手机",
    "plastic": "塑料",
    "shirt": "衬衫",
    "shoe": "鞋",
    "stainless": "不锈钢",
    "steel": "钢",
    "toy": "玩具",
    "usb": "USB",
    "watch": "手表",
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "for",
    "from",
    "in",
    "of",
    "or",
    "that",
    "the",
    "to",
    "with",
}


class SupplierSourceConnector(Protocol):
    source_key: str

    def search_offers(self, plan: SourcingPlan, limit: int) -> tuple[list[ProductOffer], list[SupplierCandidate]]:
        ...


def build_sourcing_plan(request: SourcingPlanRequest) -> SourcingPlan:
    product_name = _extract_product_name(request.product_description)
    tokens = _keywords(request.product_description)
    translated_terms = _translated_terms(tokens)
    target_platforms = [_normalize_platform(platform) for platform in request.target_platforms if platform.strip()]
    if not target_platforms:
        target_platforms = ["1688"]

    query_terms = _dedupe([product_name, *tokens[:6], *translated_terms[:6]])
    queries: list[SourcingQuery] = []
    for platform in target_platforms:
        for term in query_terms[:8]:
            language = "zh" if _contains_cjk(term) else "en"
            queries.append(SourcingQuery(platform=platform, query=term, language=language))

    constraints: dict[str, str] = {}
    if request.price_min is not None:
        constraints["price_min"] = str(request.price_min)
    if request.price_max is not None:
        constraints["price_max"] = str(request.price_max)
    if request.moq:
        constraints["moq"] = request.moq
    if request.certifications:
        constraints["certifications"] = ", ".join(request.certifications)

    notes = [
        "Use official or permitted marketplace connectors before any automated collection.",
        "Compare suppliers by price, MOQ, verification badges, response evidence, and source risk.",
    ]
    if "1688" in target_platforms:
        notes.append("1688 is scaffolded through a connector interface; replace mock data with official/partner API credentials.")

    confidence = 0.72 if tokens else 0.45
    return SourcingPlan(
        plan_id=str(uuid4()),
        product_name=product_name,
        product_summary=request.product_description.strip()[:500],
        target_platforms=target_platforms,
        supplier_regions=request.supplier_regions,
        query_terms=query_terms,
        queries=queries,
        constraints=constraints,
        confidence=confidence,
        notes=notes,
    )


def search_sourcing_plan(plan: SourcingPlan, limit_per_platform: int = 8) -> tuple[list[ProductOffer], list[SupplierCandidate]]:
    connectors = _connectors_for_plan(plan)
    all_offers: list[ProductOffer] = []
    suppliers_by_id: dict[str, SupplierCandidate] = {}

    for connector in connectors:
        offers, suppliers = connector.search_offers(plan, limit=limit_per_platform)
        all_offers.extend(offers)
        for supplier in suppliers:
            suppliers_by_id[supplier.supplier_id] = supplier

    return _dedupe_offers(all_offers), sorted(suppliers_by_id.values(), key=lambda row: row.score, reverse=True)


def generate_sourcing_report(request: SourcingReportRequest, query_terms: list[str] | None = None) -> SourcingReport:
    offers = sorted(request.offers, key=lambda row: row.score, reverse=True)
    suppliers = sorted(request.suppliers, key=lambda row: row.score, reverse=True)
    product_name = request.product_name or (offers[0].title if offers else "Sourcing Report")
    language = request.report_language.strip().upper()
    summary = _report_summary(product_name, offers, suppliers, language=language)
    recommendations = _recommendations(offers, suppliers, language=language)
    markdown = _report_markdown(product_name, query_terms or [], offers, suppliers, summary, recommendations, language=language)

    return SourcingReport(
        report_id=str(uuid4()),
        product_name=product_name,
        query_terms=query_terms or [],
        offers=offers,
        suppliers=suppliers,
        summary=summary,
        recommendations=recommendations,
        report_markdown=markdown,
        generated_at=datetime.now(timezone.utc),
    )


class Mock1688Connector:
    source_key = "1688"

    def search_offers(self, plan: SourcingPlan, limit: int) -> tuple[list[ProductOffer], list[SupplierCandidate]]:
        return _mock_marketplace_results(plan, self.source_key, limit)


class MockMarketplaceConnector:
    def __init__(self, source_key: str) -> None:
        self.source_key = source_key

    def search_offers(self, plan: SourcingPlan, limit: int) -> tuple[list[ProductOffer], list[SupplierCandidate]]:
        return _mock_marketplace_results(plan, self.source_key, limit)


def _connectors_for_plan(plan: SourcingPlan) -> list[SupplierSourceConnector]:
    connectors: list[SupplierSourceConnector] = []
    for platform in plan.target_platforms:
        if platform == "1688":
            connectors.append(Mock1688Connector())
        else:
            connectors.append(MockMarketplaceConnector(platform))
    return connectors or [Mock1688Connector()]


def _mock_marketplace_results(
    plan: SourcingPlan,
    platform: str,
    limit: int,
) -> tuple[list[ProductOffer], list[SupplierCandidate]]:
    platform_label = PLATFORM_LABELS.get(platform, platform)
    base_terms = [term for term in plan.query_terms if term][: max(1, min(limit, 5))]
    if not base_terms:
        base_terms = [plan.product_name]

    suppliers: list[SupplierCandidate] = []
    offers: list[ProductOffer] = []
    for index, term in enumerate(base_terms[:limit], start=1):
        supplier_name = _supplier_name(platform_label, term, index)
        supplier_url = _supplier_url(platform, term, index)
        supplier_id = str(uuid5(NAMESPACE_URL, f"{platform}|{supplier_name}|{supplier_url}"))
        score = max(55.0, 88.0 - index * 4)
        supplier = SupplierCandidate(
            supplier_id=supplier_id,
            platform=platform,
            supplier_name=supplier_name,
            supplier_url=supplier_url,
            location=plan.supplier_regions[0] if plan.supplier_regions else "China",
            years_active=3 + index,
            verification_badges=_badges(platform, index),
            response_rate=f"{max(72, 96 - index * 3)}%",
            transaction_signals=[
                "支持样品单",
                "支持定制包装",
            ][: 1 + (index % 2)],
            risk_flags=[] if index <= 3 else ["付款前需要人工核验供应商"],
            score=score,
        )
        suppliers.append(supplier)

        offer_id = str(uuid5(NAMESPACE_URL, f"{supplier_id}|{term}|offer"))
        price_floor = round(1.8 + index * 0.65, 2)
        offer = ProductOffer(
            offer_id=offer_id,
            supplier_id=supplier_id,
            platform=platform,
            title=f"{term} 批发货源 - {platform_label}",
            product_url=f"{supplier_url.rstrip('/')}/offer/{index}",
            image_url="",
            price_min=price_floor,
            price_max=round(price_floor * 1.55, 2),
            currency="CNY" if platform == "1688" else "USD",
            moq=plan.constraints.get("moq") or f"{100 * index} pcs",
            attributes={
                "platform": platform_label,
                "customization": "logo / 包装",
                "sample": "可提供",
            },
            source_evidence=[supplier_url],
            score=max(50.0, score - 3),
        )
        offers.append(offer)

    return offers, suppliers


def _extract_product_name(description: str) -> str:
    lines = [line.strip() for line in description.splitlines() if line.strip()]
    for line in lines[:3]:
        lowered = line.lower()
        if lowered.startswith("product:") or line.startswith("商品:"):
            return line.split(":", 1)[1].strip()[:120] or "Unnamed Product"
        if line.startswith("商品："):
            return line.split("：", 1)[1].strip()[:120] or "Unnamed Product"
    if lines:
        return lines[0][:120]
    return "Unnamed Product"


def _keywords(description: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9+\-]{1,}", description.lower())
    values = [word for word in words if word not in STOPWORDS and len(word) > 2]
    joined_pairs = [" ".join(values[index : index + 2]) for index in range(max(0, min(len(values) - 1, 4)))]
    return _dedupe([*joined_pairs, *values])


def _translated_terms(tokens: list[str]) -> list[str]:
    translated: list[str] = []
    for token in tokens:
        pieces = [ZH_HINTS.get(part) for part in re.split(r"[\s+\-]", token.lower()) if ZH_HINTS.get(part)]
        if pieces:
            translated.append("".join(pieces))
            translated.append(" ".join(pieces))
    return _dedupe(translated)


def _normalize_platform(platform: str) -> str:
    lowered = platform.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "alibaba.com": "alibaba",
        "madeinchina": "made_in_china",
        "made_in_china_com": "made_in_china",
        "global_sources": "globalsources",
        "global_sources_com": "globalsources",
    }
    return aliases.get(lowered, lowered)


def _dedupe(values: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = re.sub(r"\s+", " ", str(value or "").strip())
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(cleaned)
    return unique


def _dedupe_offers(offers: list[ProductOffer]) -> list[ProductOffer]:
    unique: list[ProductOffer] = []
    seen: set[str] = set()
    for offer in offers:
        key = f"{offer.platform}|{offer.title.lower()}|{offer.supplier_id}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(offer)
    return sorted(unique, key=lambda row: row.score, reverse=True)


def _contains_cjk(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def _supplier_name(platform_label: str, term: str, index: int) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff ]", "", term).strip().title()
    cleaned = cleaned or "Product"
    return f"{cleaned} 货源 {index}（{platform_label}）"


def _supplier_url(platform: str, term: str, index: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-") or "product"
    if platform == "1688":
        return f"https://mock.1688.example/supplier/{slug}-{index}"
    if platform == "alibaba":
        return f"https://mock.alibaba.example/supplier/{slug}-{index}"
    if platform == "made_in_china":
        return f"https://mock.made-in-china.example/supplier/{slug}-{index}"
    if platform == "globalsources":
        return f"https://mock.globalsources.example/supplier/{slug}-{index}"
    return f"https://mock.suppliers.example/{platform}/{slug}-{index}"


def _badges(platform: str, index: int) -> list[str]:
    if platform == "1688":
        badges = ["认证供应商", "源头工厂"]
    elif platform == "alibaba":
        badges = ["金牌供应商", "交易保障"]
    else:
        badges = ["已收录供应商"]
    if index <= 2:
        badges.append("优先 shortlist")
    return badges


def _report_summary(
    product_name: str,
    offers: list[ProductOffer],
    suppliers: list[SupplierCandidate],
    language: str = "EN",
) -> str:
    if not offers:
        if language in {"CN", "ZH", "ZH-CN"}:
            return f"暂未找到 {product_name} 的供应商货源。建议扩大关键词或增加官方平台连接器。"
        return f"No supplier offers were found for {product_name}. Add more source platforms or broader query terms."
    prices = [offer.price_min for offer in offers if offer.price_min is not None]
    if prices:
        price_range = f"{min(prices):.2f}-{max(prices):.2f}"
    else:
        price_range = "unknown"
    if language in {"CN", "ZH", "ZH-CN"}:
        return (
            f"已为 {product_name} 找到 {len(offers)} 个货源候选，来自 {len(suppliers)} 个供应商。"
            f"观察到的起始价格区间为 {price_range}。建议优先联系有认证标识的供应商，并在大货前确认样品。"
        )
    return (
        f"Found {len(offers)} offer candidates from {len(suppliers)} suppliers for {product_name}. "
        f"Observed starting price range: {price_range}. Shortlist suppliers with verification badges "
        "and confirm samples before bulk purchase."
    )


def _recommendations(
    offers: list[ProductOffer],
    suppliers: list[SupplierCandidate],
    language: str = "EN",
) -> list[str]:
    if not offers:
        if language in {"CN", "ZH", "ZH-CN"}:
            return ["扩大商品关键词，并至少增加一个官方或授权的市场平台连接器。"]
        return ["Broaden product keywords and add at least one official marketplace connector."]
    top_supplier = suppliers[0].supplier_name if suppliers else "the top-ranked supplier"
    if language in {"CN", "ZH", "ZH-CN"}:
        return [
            f"优先向 {top_supplier} 和后续两家供应商发 RFQ，用来校验价格和交期。",
            "询问样品费用、交期、包装定制、认证证明和出口贸易条款。",
            "在确认供应商主体、发票主体和物流条款前，不建议脱离平台付款。",
        ]
    return [
        f"Start RFQ with {top_supplier} and the next two suppliers for price validation.",
        "Ask for sample cost, lead time, packaging options, certification proof, and export terms.",
        "Do not pay off-platform until supplier identity, invoice entity, and shipping terms are verified.",
    ]


def _report_markdown(
    product_name: str,
    query_terms: list[str],
    offers: list[ProductOffer],
    suppliers: list[SupplierCandidate],
    summary: str,
    recommendations: list[str],
    language: str = "EN",
) -> str:
    if language in {"CN", "ZH", "ZH-CN"}:
        lines = [
            f"# 找货报告：{product_name}",
            "",
            "## 摘要",
            summary,
            "",
            "## 搜索词",
            ", ".join(query_terms) if query_terms else "-",
            "",
            "## 供应商 shortlist",
        ]
        if suppliers:
            for supplier in suppliers[:8]:
                badges = ", ".join(supplier.verification_badges) or "-"
                lines.append(f"- {supplier.supplier_name} | {supplier.platform} | 评分 {supplier.score:.1f} | {badges}")
        else:
            lines.append("- 暂无供应商。")

        lines.extend(["", "## 货源对比"])
        if offers:
            for offer in offers[:12]:
                price = "-"
                if offer.price_min is not None and offer.price_max is not None:
                    price = f"{offer.price_min:.2f}-{offer.price_max:.2f} {offer.currency}"
                lines.append(f"- {offer.title} | {price} | 起订量 {offer.moq} | 评分 {offer.score:.1f}")
        else:
            lines.append("- 暂无货源。")

        lines.extend(["", "## 建议"])
        lines.extend(f"- {item}" for item in recommendations)
        return "\n".join(lines)

    lines = [
        f"# Sourcing Report: {product_name}",
        "",
        "## Summary",
        summary,
        "",
        "## Query Terms",
        ", ".join(query_terms) if query_terms else "-",
        "",
        "## Supplier Shortlist",
    ]
    if suppliers:
        for supplier in suppliers[:8]:
            badges = ", ".join(supplier.verification_badges) or "-"
            lines.append(f"- {supplier.supplier_name} | {supplier.platform} | score {supplier.score:.1f} | {badges}")
    else:
        lines.append("- No suppliers found.")

    lines.extend(["", "## Offer Comparison"])
    if offers:
        for offer in offers[:12]:
            price = "-"
            if offer.price_min is not None and offer.price_max is not None:
                price = f"{offer.price_min:.2f}-{offer.price_max:.2f} {offer.currency}"
            lines.append(f"- {offer.title} | {price} | MOQ {offer.moq} | score {offer.score:.1f}")
    else:
        lines.append("- No offers found.")

    lines.extend(["", "## Recommendations"])
    lines.extend(f"- {item}" for item in recommendations)
    return "\n".join(lines)
