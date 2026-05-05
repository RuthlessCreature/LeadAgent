from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.models import ICPDefinition, ProductProfile, ScoreWeights  # noqa: E402
from app.services.discovery import discover_public_urls  # noqa: E402
from app.services.public_web import crawl_public_web  # noqa: E402
from app.services.scoring import score_leads  # noqa: E402
from app.services.search import extract_leads  # noqa: E402


CITIES = [
    "Houston",
    "Chicago",
    "New York",
    "Dallas",
    "Los Angeles",
    "Atlanta",
    "Detroit",
    "New Jersey",
    "Philadelphia",
    "Washington DC",
    "Miami",
    "Orlando",
    "Tampa",
    "Boston",
    "Seattle",
    "Phoenix",
    "Charlotte",
    "San Francisco",
    "San Jose",
    "Toronto",
    "Mississauga",
    "Ottawa",
    "Montreal",
    "Calgary",
    "Edmonton",
    "Vancouver",
    "Winnipeg",
    "London",
    "Birmingham",
    "Manchester",
    "Leicester",
    "Bradford",
    "Luton",
    "Leeds",
    "Glasgow",
    "Sheffield",
    "Nottingham",
    "Coventry",
    "Cardiff",
    "Liverpool",
    "Paris",
    "Sydney",
    "Melbourne",
    "Brisbane",
    "Perth",
    "Adelaide",
]

QUERY_PATTERNS = [
    "umrah packages {city}",
    "hajj packages {city}",
    "umrah travel agency {city}",
    "hajj and umrah {city}",
    "umrah from {city}",
]

COUNTRY_QUERIES = [
    "umrah packages usa",
    "hajj packages usa",
    "umrah packages uk",
    "hajj packages uk",
    "umrah packages canada",
    "hajj packages canada",
    "umrah packages australia",
]

MANUAL_SEED_URLS = [
    "https://taqwatours.us/umrah-packages/dallas/",
    "https://hisartour.com/tour/hajj-package-chicago-ord-gold/",
    "https://umrahpackageschicago.com/",
    "https://www.alhamdtravel.com/umrah-from-houston.html",
    "https://umrahpackageshouston.com/",
    "https://internationalhajj.com/umrah-packages/",
    "https://www.bismillahtours.com/houston-umrah-packages.html",
    "https://darelmecca.com/houston-umrah-packages/",
    "https://www.tarteeltravel.com/umrah-packages/houston/",
    "https://alshafietravels.com/umrah-packages-houston/",
    "https://sherytravels.com/umrah/usa-packages/chicago",
    "https://ilinktours.com/chicago-umrah-package/",
    "https://alsafwatours.com/hajj/",
    "https://www.hajjumrahhub.com/chicago-umrah-packages.html",
    "https://royaltraveltexas.com/houston-texas-umrah-packages/",
    "https://alhaqtours.com/chicago-umrah-packages.html",
    "https://www.eurobanglatours.co.uk/",
    "https://www.hajjpackagesuk.co.uk/",
    "https://www.haleema.co.uk/umrah-birmingham/birmingham-umrah-packages",
    "https://www.alhaqtravel.co.uk/buy/umrah-packages-birmingham/",
    "https://almaknoontravels.co.uk/umrah-packages-from-birmingham",
    "https://www.ibadahtours.com/hajj-packages",
    "https://holymakkah.co.uk/",
    "https://www.labbaikhajjumrah.co.uk/umrah-packages-birmingham/",
    "https://bismillahhajj.com/",
    "https://kingtravelcan.com/",
    "https://www.kiswatours.com/product/umrah-package-january-2025/",
    "https://uama.us/umrah/",
    "https://horizonumrah.com/custom-package/",
    "https://www.dareleiman.com/",
    "https://kasfahhajj.com/umrah-packages/",
    "https://labaykhajj.ca/hajj-umrah/",
    "https://fjtravels.ca/umrah-packages/",
    "https://www.bismillahtravels.ca/",
]

BUSINESS_KEYWORDS = (
    "umrah",
    "hajj",
    "travel",
    "tours",
    "pilgrim",
    "ziyarah",
    "package",
)


def main() -> None:
    queries = [pattern.format(city=city) for city in CITIES for pattern in QUERY_PATTERNS]
    queries.extend(COUNTRY_QUERIES)
    discovered = discover_public_urls(queries, limit_per_query=8, exclude_social=True)
    filtered = [row for row in discovered if is_relevant_result(row.title, row.url, row.snippet)]

    seed_urls = unique([*MANUAL_SEED_URLS, *[row.url for row in filtered]])[:140]
    crawl = crawl_public_web(seed_urls=seed_urls, max_pages_per_domain=2, respect_robots=True)
    leads = extract_leads(crawl.raw_results)
    scored = score_leads(leads, build_product_profile(), build_icp(), ScoreWeights())

    output_dir = ROOT / "deliverables"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "hajj_target_accounts.json"
    csv_path = output_dir / "hajj_target_accounts.csv"

    json_payload = [
        {
            "company": lead.company,
            "contact_name": lead.contact_name,
            "role": lead.role,
            "email": lead.email,
            "phone": lead.phone,
            "domain": lead.domain,
            "source_url": lead.source_url,
            "source_label": lead.source_label,
            "consent_status": lead.consent_status.value,
            "verification_status": lead.verification_status.value,
            "overall_score": lead.scores.overall,
            "raw_text_snippet": lead.raw_text_snippet,
        }
        for lead in scored
    ]
    json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
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
            ],
        )
        writer.writeheader()
        writer.writerows(json_payload)

    print(f"queries={len(queries)} discovered={len(discovered)} filtered={len(filtered)} visited={len(crawl.visited_urls)} leads={len(scored)}")
    print(json_path)
    print(csv_path)


def is_relevant_result(title: str, url: str, snippet: str) -> bool:
    haystack = " ".join([title, url, snippet]).lower()
    if any(block in haystack for block in ("wikipedia", "britannica", "history.com", "aljazeera", "guide", "what is hajj")):
        return False
    return any(keyword in haystack for keyword in BUSINESS_KEYWORDS)


def unique(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def build_product_profile() -> ProductProfile:
    return ProductProfile(
        product_name="Hajj and Umrah supplies",
        industry_tags=["travel", "retail", "ecommerce"],
        feature_tags=["pilgrimage accessories", "group kits", "wholesale supply"],
        use_cases=["market_expansion", "sales_outreach"],
        target_roles=["operations", "business_development"],
        price_range="wholesale",
        exclude_tags=[],
        llm_provider="mock",
    )


def build_icp() -> ICPDefinition:
    return ICPDefinition(
        geography=["US", "UK", "Canada"],
        industry=["travel", "tourism", "retail", "pilgrimage"],
        role_titles=["owner", "operations", "travel agent", "director"],
        technology_stack=[],
    )


if __name__ == "__main__":
    main()
