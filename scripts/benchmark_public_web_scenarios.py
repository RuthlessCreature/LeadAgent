from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.models import ICPDefinition, ProductProfile, ScoreWeights  # noqa: E402
from app.services.discovery import discover_public_urls  # noqa: E402
from app.services.public_web import crawl_public_web  # noqa: E402
from app.services.query_expansion import expand_public_web_queries  # noqa: E402
from app.services.scoring import score_leads  # noqa: E402
from app.services.search import extract_leads  # noqa: E402
from enrich_hajj_discovered_accounts import build_people_rows, lead_to_contact_row, merge_company_rows  # noqa: E402


DEFAULT_OUTPUT_DIR = ROOT / "deliverables" / "scenario_benchmarks"
DEFAULT_ENGINES = "yahoo"

CORE_LOCATIONS = [
    "Houston",
    "Chicago",
    "New York",
    "Toronto",
    "Mississauga",
    "London",
    "Birmingham",
    "Manchester",
    "Sydney",
    "Melbourne",
    "USA",
    "Canada",
    "UK",
    "Australia",
]

DEFAULT_BLOCKLIST = (
    "wikipedia",
    "britannica",
    "history.com",
    "guide",
    "reddit",
    "tripadvisor",
    "facebook",
    "instagram",
    "tiktok",
    "youtube",
    "x.com",
    "twitter",
    "linkedin.com",
)

DISCOVERY_FIELDS = ["company", "domain", "url", "query", "snippet"]
CONTACT_FIELDS = [
    "company",
    "contact_name",
    "role",
    "email",
    "phone",
    "domain",
    "source_url",
    "source_label",
    "consent_status",
    "verification_status",
    "overall_score",
    "raw_text_snippet",
]
SUMMARY_FIELDS = [
    "scenario_id",
    "product",
    "buyer_type",
    "queries",
    "discovered_domains",
    "seed_urls",
    "visited_urls",
    "contacts",
    "people",
    "people_with_email",
    "people_with_phone",
    "people_with_both",
    "companies",
]


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    product: str
    buyer_type: str
    query_terms: tuple[str, ...]
    translated_terms: dict[str, tuple[str, ...]]
    include_keywords: tuple[str, ...]
    product_profile: ProductProfile
    icp: ICPDefinition
    locations: tuple[str, ...] = tuple(CORE_LOCATIONS)
    languages: tuple[str, ...] = ("en",)


DEFAULT_SCENARIOS = [
    Scenario(
        scenario_id="hajj_kits_wholesale",
        product="Hajj and Umrah accessories wholesaler",
        buyer_type="Hajj and Umrah travel agencies",
        query_terms=("umrah travel agency", "hajj travel agency", "umrah tours"),
        translated_terms={
            "fr": ("agence omra",),
            "tr": ("umre seyahat acentesi",),
            "id": ("travel umrah",),
            "ms": ("agensi umrah",),
        },
        include_keywords=("hajj", "umrah", "travel", "tour", "agency", "pilgrim", "ziyarah"),
        product_profile=ProductProfile(
            product_name="Hajj and Umrah accessories",
            industry_tags=["travel", "pilgrimage", "retail"],
            feature_tags=["pilgrim kits", "ihram", "tasbih", "wholesale supply"],
            use_cases=["sales_outreach", "channel_sales"],
            target_roles=["owner", "operations manager", "travel consultant"],
            price_range="wholesale",
            exclude_tags=[],
            llm_provider="mock",
        ),
        icp=ICPDefinition(
            geography=["US", "UK", "Canada", "Australia"],
            industry=["travel", "tourism", "pilgrimage"],
            role_titles=["owner", "director", "operations manager", "travel consultant"],
            technology_stack=[],
        ),
        languages=("en", "fr", "tr", "id", "ms"),
    ),
    Scenario(
        scenario_id="modest_apparel_manufacturer",
        product="Modest apparel manufacturer",
        buyer_type="Hijab and abaya retailers",
        query_terms=("abaya boutique", "hijab store", "modest fashion boutique"),
        translated_terms={
            "fr": ("boutique abaya", "boutique hijab"),
            "tr": ("tesettur butik",),
        },
        include_keywords=("abaya", "hijab", "modest", "boutique", "fashion", "clothing"),
        product_profile=ProductProfile(
            product_name="Modest apparel manufacturing",
            industry_tags=["fashion", "apparel", "retail"],
            feature_tags=["abaya", "hijab", "private label", "wholesale production"],
            use_cases=["channel_sales", "retail_supply"],
            target_roles=["owner", "buyer", "store manager"],
            price_range="manufacturer",
            exclude_tags=[],
            llm_provider="mock",
        ),
        icp=ICPDefinition(
            geography=["US", "UK", "Canada", "Australia"],
            industry=["fashion", "retail", "apparel"],
            role_titles=["owner", "buyer", "store manager", "director"],
            technology_stack=[],
        ),
        languages=("en", "fr", "tr"),
    ),
    Scenario(
        scenario_id="islamic_books_distributor",
        product="Islamic books and gifts distributor",
        buyer_type="Islamic bookstores and Muslim gift shops",
        query_terms=("islamic bookstore", "muslim bookstore", "islamic gift shop"),
        translated_terms={
            "fr": ("librairie islamique",),
            "de": ("islamische buchhandlung",),
        },
        include_keywords=("islamic", "muslim", "bookstore", "bookshop", "book", "gift", "shop"),
        product_profile=ProductProfile(
            product_name="Islamic books and gifts distribution",
            industry_tags=["books", "retail", "distribution"],
            feature_tags=["islamic books", "gift items", "wholesale catalog"],
            use_cases=["channel_sales", "wholesale_outreach"],
            target_roles=["owner", "manager", "buyer"],
            price_range="wholesale",
            exclude_tags=[],
            llm_provider="mock",
        ),
        icp=ICPDefinition(
            geography=["US", "UK", "Canada", "Australia"],
            industry=["retail", "books", "gifts"],
            role_titles=["owner", "manager", "buyer", "director"],
            technology_stack=[],
        ),
        languages=("en", "fr", "de"),
    ),
    Scenario(
        scenario_id="islamic_school_supplier",
        product="School uniforms and classroom furniture manufacturer",
        buyer_type="Islamic schools and Muslim academies",
        query_terms=("islamic school", "muslim school", "islamic academy"),
        translated_terms={},
        include_keywords=("islamic", "muslim", "school", "academy", "madrasah"),
        product_profile=ProductProfile(
            product_name="Islamic school supply manufacturing",
            industry_tags=["education", "schools", "manufacturing"],
            feature_tags=["uniforms", "classroom furniture", "bulk supply"],
            use_cases=["institutional_sales", "channel_sales"],
            target_roles=["principal", "director", "administrator", "operations manager"],
            price_range="manufacturer",
            exclude_tags=[],
            llm_provider="mock",
        ),
        icp=ICPDefinition(
            geography=["US", "UK", "Canada", "Australia"],
            industry=["education", "schools"],
            role_titles=["principal", "director", "administrator", "operations manager"],
            technology_stack=[],
        ),
        languages=("en",),
    ),
    Scenario(
        scenario_id="mosque_tech_dealer",
        product="Prayer hall audio and digital signage dealer",
        buyer_type="Mosques and Islamic centers",
        query_terms=("islamic center", "mosque", "masjid"),
        translated_terms={},
        include_keywords=("islamic center", "mosque", "masjid", "muslim center"),
        product_profile=ProductProfile(
            product_name="Mosque audio and signage systems",
            industry_tags=["nonprofit", "religious institutions", "facilities"],
            feature_tags=["audio systems", "digital signage", "bulk installation"],
            use_cases=["institutional_sales", "facilities_supply"],
            target_roles=["director", "administrator", "operations manager", "imam"],
            price_range="dealer",
            exclude_tags=[],
            llm_provider="mock",
        ),
        icp=ICPDefinition(
            geography=["US", "UK", "Canada", "Australia"],
            industry=["religious institutions", "nonprofit"],
            role_titles=["director", "administrator", "operations manager", "imam"],
            technology_stack=[],
        ),
        languages=("en",),
    ),
]

BUSINESS_TITLE_HINTS = (
    "solutions",
    "systems",
    "group",
    "company",
    "co",
    "inc",
    "llc",
    "ltd",
    "clinic",
    "restaurant",
    "logistics",
    "warehouse",
    "distribution",
    "manufacturing",
    "industrial",
    "software",
    "automation",
    "engineering",
    "services",
    "contractor",
    "supply",
    "supplies",
    "dental",
    "medical",
)


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    scenarios = load_scenarios(args.scenario_file)
    selected = select_scenarios(args.scenarios, scenarios)
    engines = [engine.strip().lower() for engine in args.engines.split(",") if engine.strip()]

    summary_rows: list[dict[str, str]] = []
    for scenario in selected:
        result = run_scenario(scenario, args, engines, output_dir / scenario.scenario_id)
        summary_rows.append(result)

    summary_csv = output_dir / "summary.csv"
    summary_json = output_dir / "summary.json"
    write_csv(summary_csv, SUMMARY_FIELDS, summary_rows)
    write_json(summary_json, summary_rows)
    print(summary_csv)
    print(summary_json)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark multiple public-web lead scenarios with person-level extraction.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for scenario outputs.")
    parser.add_argument("--scenario-file", type=Path, default=None, help="Optional JSON file with scenario definitions.")
    parser.add_argument("--scenarios", type=str, default="all", help="Comma-separated scenario ids or 'all'.")
    parser.add_argument("--limit-per-query", type=int, default=5, help="Maximum results to keep per query.")
    parser.add_argument("--batch-size", type=int, default=8, help="Queries per discovery batch.")
    parser.add_argument("--pause-seconds", type=float, default=1.0, help="Delay between query batches.")
    parser.add_argument("--max-queries", type=int, default=180, help="Cap per-scenario expanded query count.")
    parser.add_argument("--max-seeds", type=int, default=80, help="Maximum unique domains to crawl per scenario.")
    parser.add_argument("--max-pages-per-domain", type=int, default=2, help="Maximum pages to crawl per domain.")
    parser.add_argument("--engines", type=str, default=DEFAULT_ENGINES, help="Comma-separated engines.")
    return parser.parse_args()


def load_scenarios(path: Path | None) -> list[Scenario]:
    if path is None:
        return list(DEFAULT_SCENARIOS)

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Scenario file must contain a JSON array.")
    return [scenario_from_dict(item) for item in payload]


def scenario_from_dict(payload: dict) -> Scenario:
    if not isinstance(payload, dict):
        raise ValueError("Each scenario must be a JSON object.")

    return Scenario(
        scenario_id=str(payload.get("scenario_id", "")).strip(),
        product=str(payload.get("product", "")).strip(),
        buyer_type=str(payload.get("buyer_type", "")).strip(),
        query_terms=tuple(str(item).strip() for item in payload.get("query_terms", []) if str(item).strip()),
        translated_terms={
            str(language).strip().lower(): tuple(str(term).strip() for term in terms if str(term).strip())
            for language, terms in (payload.get("translated_terms", {}) or {}).items()
        },
        include_keywords=tuple(str(item).strip().lower() for item in payload.get("include_keywords", []) if str(item).strip()),
        product_profile=ProductProfile.model_validate(payload.get("product_profile", {})),
        icp=ICPDefinition.model_validate(payload.get("icp", {})),
        locations=tuple(str(item).strip() for item in payload.get("locations", CORE_LOCATIONS) if str(item).strip()),
        languages=tuple(str(item).strip().lower() for item in payload.get("languages", ("en",)) if str(item).strip()),
    )


def select_scenarios(raw: str, scenarios: list[Scenario]) -> list[Scenario]:
    requested = [item.strip().lower() for item in raw.split(",") if item.strip()]
    if not requested or requested == ["all"]:
        return list(scenarios)

    by_id = {scenario.scenario_id: scenario for scenario in scenarios}
    return [by_id[item] for item in requested if item in by_id]


def run_scenario(scenario: Scenario, args: argparse.Namespace, engines: list[str], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    queries = expand_public_web_queries(
        query_terms=list(scenario.query_terms),
        translated_terms=scenario.translated_terms,
        languages=scenario.languages,
        locations=scenario.locations,
        include_global_queries=True,
        max_queries=args.max_queries,
        use_location_aliases=True,
    )

    discovered_by_domain: dict[str, dict[str, str]] = {}
    total_batches = max(1, math.ceil(len(queries) / max(1, args.batch_size)))
    for index, batch in enumerate(chunked(queries, args.batch_size), start=1):
        rows = discover_public_urls(batch, limit_per_query=args.limit_per_query, exclude_social=True, engines=engines)
        for row in rows:
            normalized = normalize_discovery_row(row.query, row.title, row.url, row.snippet, scenario)
            if normalized is None:
                continue
            existing = discovered_by_domain.get(normalized["domain"])
            if existing is None or result_score(normalized, scenario) > result_score(existing, scenario):
                discovered_by_domain[normalized["domain"]] = normalized
        print(
            f"scenario={scenario.scenario_id} batch={index}/{total_batches} "
            f"queries={len(batch)} unique_domains={len(discovered_by_domain)}"
        )
        if index < total_batches and args.pause_seconds > 0:
            time.sleep(args.pause_seconds)

    discovered_rows = sorted(discovered_by_domain.values(), key=lambda row: row["domain"])
    seed_urls = [row["url"] for row in sorted(discovered_rows, key=lambda row: result_score(row, scenario), reverse=True)[: args.max_seeds]]

    crawl = crawl_public_web(seed_urls=seed_urls, max_pages_per_domain=args.max_pages_per_domain, respect_robots=True)
    leads = score_leads(extract_leads(crawl.raw_results), scenario.product_profile, scenario.icp, ScoreWeights())

    name_map = {row["domain"]: row["company"] for row in discovered_rows}
    contact_rows = [lead_to_contact_row(lead, name_map) for lead in leads]
    people_rows = build_people_rows(contact_rows)
    company_rows = merge_company_rows([contact_to_company_row(row) for row in contact_rows])

    write_csv(output_dir / "discovered.csv", DISCOVERY_FIELDS, discovered_rows)
    write_json(output_dir / "discovered.json", discovered_rows)
    write_csv(output_dir / "contacts.csv", CONTACT_FIELDS, contact_rows)
    write_json(output_dir / "contacts.json", contact_rows)
    write_csv(output_dir / "people.csv", CONTACT_FIELDS, people_rows)
    write_json(output_dir / "people.json", people_rows)
    write_csv(output_dir / "companies.csv", COMPANY_FIELDS(), company_rows)
    write_json(output_dir / "companies.json", company_rows)

    people_with_email = sum(1 for row in people_rows if row["email"])
    people_with_phone = sum(1 for row in people_rows if row["phone"])
    people_with_both = sum(1 for row in people_rows if row["email"] and row["phone"])
    summary_row = {
        "scenario_id": scenario.scenario_id,
        "product": scenario.product,
        "buyer_type": scenario.buyer_type,
        "queries": str(len(queries)),
        "discovered_domains": str(len(discovered_rows)),
        "seed_urls": str(len(seed_urls)),
        "visited_urls": str(len(crawl.visited_urls)),
        "contacts": str(len(contact_rows)),
        "people": str(len(people_rows)),
        "people_with_email": str(people_with_email),
        "people_with_phone": str(people_with_phone),
        "people_with_both": str(people_with_both),
        "companies": str(len(company_rows)),
    }
    write_json(output_dir / "summary.json", [summary_row])
    print(
        f"scenario={scenario.scenario_id} queries={len(queries)} discovered={len(discovered_rows)} "
        f"contacts={len(contact_rows)} people={len(people_rows)} companies={len(company_rows)}"
    )
    return summary_row


def normalize_discovery_row(query: str, title: str, url: str, snippet: str, scenario: Scenario) -> dict[str, str] | None:
    clean_url = (url or "").strip()
    domain = clean_domain(clean_url)
    if not domain:
        return None

    haystack = " ".join([title, domain, clean_url, snippet]).lower()
    if any(block in haystack for block in DEFAULT_BLOCKLIST):
        return None
    if not any(keyword in haystack for keyword in scenario.include_keywords):
        return None

    return {
        "company": normalize_title(title, domain, scenario.include_keywords),
        "domain": domain,
        "url": clean_url,
        "query": (query or "").strip(),
        "snippet": normalize_snippet(snippet),
    }


def clean_domain(url: str) -> str:
    parsed = urlparse(url or "")
    domain = (parsed.netloc or "").lower().replace("www.", "")
    return domain


def normalize_title(title: str, domain: str, keywords: tuple[str, ...] = ()) -> str:
    value = re.sub(r"\s+", " ", (title or "").strip())
    if not value:
        return fallback_company_name(domain)
    pieces = [piece.strip(" .") for piece in re.split(r"\s*[|:]\s*", value) if piece.strip(" .")]
    best = max(pieces or [value], key=lambda piece: title_score(piece, keywords))
    return best or fallback_company_name(domain)


def title_score(value: str, keywords: tuple[str, ...] = ()) -> int:
    lowered = value.lower()
    score = 0
    if 4 <= len(value) <= 48:
        score += 10
    if any(token in lowered for token in keywords):
        score += 12
    if any(token in lowered for token in BUSINESS_TITLE_HINTS):
        score += 8
    if any(token in lowered for token in ("best ", "affordable ", "guide", "what is ")):
        score -= 8
    if "..." in value:
        score -= 4
    return score


def fallback_company_name(domain: str) -> str:
    label = domain.split(".", 1)[0].replace("-", " ").replace("_", " ").strip()
    label = re.sub(r"\s+", " ", label)
    return " ".join(part.capitalize() for part in label.split())


def normalize_snippet(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())[:320]


def result_score(row: dict[str, str], scenario: Scenario) -> int:
    haystack = " ".join([row.get("company", ""), row.get("query", ""), row.get("snippet", ""), row.get("url", "")]).lower()
    score = 0
    for keyword in scenario.include_keywords:
        if keyword in haystack:
            score += 6
    score += len(row.get("company", "")) // 6
    if any(keyword in row.get("query", "").lower() for keyword in scenario.query_terms):
        score += 8
    return score


def chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), max(1, size))]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def COMPANY_FIELDS() -> list[str]:
    return [
        "company",
        "email",
        "phone",
        "domain",
        "source_url",
        "consent_status",
        "verification_status",
        "overall_score",
        "raw_text_snippet",
    ]


def contact_to_company_row(row: dict[str, str]) -> dict[str, str]:
    return {
        "company": row.get("company", ""),
        "email": row.get("email", ""),
        "phone": row.get("phone", ""),
        "domain": row.get("domain", ""),
        "source_url": row.get("source_url", ""),
        "consent_status": row.get("consent_status", ""),
        "verification_status": row.get("verification_status", ""),
        "overall_score": row.get("overall_score", "0"),
        "raw_text_snippet": row.get("raw_text_snippet", ""),
    }


if __name__ == "__main__":
    main()
