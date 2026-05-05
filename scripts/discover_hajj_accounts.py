from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.discovery import discover_public_urls  # noqa: E402
from app.services.query_expansion import expand_public_web_queries  # noqa: E402
from collect_hajj_targets import MANUAL_SEED_URLS  # noqa: E402


DEFAULT_OUTPUT_PREFIX = ROOT / "deliverables" / "hajj_discovered_accounts"

CORE_CITIES = [
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
    "Minneapolis",
    "Columbus",
    "Cleveland",
    "Baltimore",
    "Raleigh",
]

WIDE_CITIES = [
    *CORE_CITIES,
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
    "Blackburn",
    "Paris",
    "Marseille",
    "Lyon",
    "Berlin",
    "Frankfurt",
    "Amsterdam",
    "Rotterdam",
    "Brussels",
    "Antwerp",
    "Dublin",
    "Stockholm",
    "Oslo",
    "Copenhagen",
    "Sydney",
    "Melbourne",
    "Brisbane",
    "Perth",
    "Adelaide",
    "Auckland",
    "Johannesburg",
    "Cape Town",
    "Durban",
]
COUNTRY_MARKETS = [
    "USA",
    "Canada",
    "UK",
    "Australia",
    "South Africa",
    "Ireland",
    "New Zealand",
    "Netherlands",
    "Germany",
    "France",
]

BUSINESS_KEYWORDS = (
    "umrah",
    "hajj",
    "travel",
    "tour",
    "tours",
    "pilgrim",
    "ziyarah",
    "package",
    "packages",
    "visa",
)
HIGH_INTENT_KEYWORDS = (
    "travel",
    "tour",
    "tours",
    "agency",
    "services",
    "group",
    "package",
    "packages",
    "visa",
)
BLOCKLIST = (
    "wikipedia",
    "britannica",
    "history.com",
    "guide",
    "what is hajj",
    "what is umrah",
    "aljazeera",
    "gulfnews",
    "islamicfinder",
    "islamonline",
    "pilgrim.co",
    "houseofsaud",
    "haj.gov.sa",
    "apnews",
    "news",
    "forum",
    "forums",
    "reddit",
    "tripadvisor",
    "youtube",
    "facebook",
    "instagram",
    "tiktok",
    "x.com",
    "twitter",
    "mixedmartialarts",
    "sherdog",
)


def main() -> None:
    args = parse_args()
    output_csv = args.output_prefix.with_suffix(".csv")
    output_json = args.output_prefix.with_suffix(".json")
    engines = [engine.strip().lower() for engine in args.engines.split(",") if engine.strip()]
    languages = [language.strip().lower() for language in args.languages.split(",") if language.strip()]
    locations = [*city_scope(args.city_scope), *COUNTRY_MARKETS]
    queries = expand_public_web_queries(
        query_preset=args.query_preset,
        languages=languages,
        locations=locations,
        include_global_queries=True,
        use_location_aliases=not args.disable_location_aliases,
        max_queries=args.max_queries,
    )
    results_by_domain: dict[str, dict[str, str]] = {}
    raw_count = 0
    total_batches = math.ceil(len(queries) / args.batch_size)

    for index, batch in enumerate(chunked(queries, args.batch_size), start=1):
        rows = discover_public_urls(
            batch,
            limit_per_query=args.limit_per_query,
            exclude_social=True,
            engines=engines,
        )
        raw_count += len(rows)
        for row in rows:
            normalized = normalize_discovery_row(row.query, row.title, row.url, row.snippet)
            if normalized is None:
                continue
            existing = results_by_domain.get(normalized["domain"])
            if existing is None or result_score(normalized) > result_score(existing):
                results_by_domain[normalized["domain"]] = normalized
        print(f"batch={index}/{total_batches} queries={len(batch)} raw={len(rows)} unique={len(results_by_domain)}")
        if index < total_batches and args.pause_seconds > 0:
            time.sleep(args.pause_seconds)

    for seed_url in MANUAL_SEED_URLS:
        manual = manual_seed_row(seed_url)
        existing = results_by_domain.get(manual["domain"])
        if existing is None or result_score(manual) > result_score(existing):
            results_by_domain[manual["domain"]] = manual

    items = sorted(results_by_domain.values(), key=lambda row: (0 if row["query"] == "manual_seed" else 1, row["domain"]))
    write_csv(output_csv, items)
    write_json(output_json, items)

    print(f"queries={len(queries)} raw={raw_count} unique={len(items)}")
    print(output_csv)
    print(output_json)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover public Hajj/Umrah company websites across cities and countries.")
    parser.add_argument(
        "--output-prefix",
        type=Path,
        default=DEFAULT_OUTPUT_PREFIX,
        help="Output prefix path without extension.",
    )
    parser.add_argument(
        "--limit-per-query",
        type=int,
        default=6,
        help="Maximum deduplicated URLs to keep per query.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=12,
        help="Number of queries to send in each batch.",
    )
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=1.2,
        help="Delay between discovery batches.",
    )
    parser.add_argument(
        "--engines",
        type=str,
        default="yahoo",
        help="Comma-separated discovery engines. Supported values: yahoo,duckduckgo,bing.",
    )
    parser.add_argument(
        "--languages",
        type=str,
        default="en,ar,ur,fr,tr,id,ms,bn,de,nl",
        help="Comma-separated language codes used by the query preset.",
    )
    parser.add_argument(
        "--query-preset",
        type=str,
        default="hajj_umrah",
        help="Multilingual query preset name.",
    )
    parser.add_argument(
        "--city-scope",
        type=str,
        choices=["core", "wide", "none"],
        default="core",
        help="Location preset for city-based query expansion.",
    )
    parser.add_argument(
        "--max-queries",
        type=int,
        default=1500,
        help="Safety cap on expanded multilingual query count.",
    )
    parser.add_argument(
        "--disable-location-aliases",
        action="store_true",
        help="Disable built-in language-specific location aliases.",
    )
    return parser.parse_args()


def city_scope(scope: str) -> list[str]:
    if scope == "wide":
        return WIDE_CITIES
    if scope == "none":
        return []
    return CORE_CITIES


def chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), max(1, size))]


def normalize_discovery_row(query: str, title: str, url: str, snippet: str) -> dict[str, str] | None:
    clean_url = (url or "").strip()
    domain = clean_domain(clean_url)
    if not domain:
        return None

    haystack = " ".join([title, domain, clean_url, snippet]).lower()
    if any(block in haystack for block in BLOCKLIST):
        return None
    if not any(keyword in haystack for keyword in BUSINESS_KEYWORDS):
        return None

    return {
        "company": normalize_title(title, domain),
        "domain": domain,
        "url": clean_url,
        "query": (query or "").strip(),
        "snippet": normalize_snippet(snippet),
    }


def normalize_title(title: str, domain: str) -> str:
    value = re.sub(r"\s+", " ", (title or "").strip())
    if not value:
        return fallback_company_name(domain)

    pieces = [piece.strip(" .") for piece in re.split(r"\s*[|:]\s*", value) if piece.strip(" .")]
    best = max(pieces or [value], key=title_score)
    return best or fallback_company_name(domain)


def title_score(value: str) -> int:
    lowered = value.lower()
    score = 0
    if 4 <= len(value) <= 48:
        score += 10
    if any(token in lowered for token in HIGH_INTENT_KEYWORDS):
        score += 8
    if any(token in lowered for token in ("best ", "affordable ", "book ", "start ", "what is ", "guide")):
        score -= 8
    if "..." in value:
        score -= 5
    return score


def result_score(row: dict[str, str]) -> int:
    haystack = " ".join([row["company"], row["domain"], row["url"], row["snippet"]]).lower()
    score = title_score(row["company"])
    score += 6 if row["query"] == "manual_seed" else 0
    score += sum(3 for keyword in ("travel", "tour", "tours", "agency", "services") if keyword in haystack)
    score += sum(2 for keyword in ("hajj", "umrah", "visa", "package", "packages") if keyword in haystack)
    return score


def manual_seed_row(seed_url: str) -> dict[str, str]:
    domain = clean_domain(seed_url)
    return {
        "company": fallback_company_name(domain),
        "domain": domain,
        "url": seed_url.strip(),
        "query": "manual_seed",
        "snippet": "Known public Hajj/Umrah company website seed.",
    }


def clean_domain(url: str) -> str:
    parsed = urlparse(url or "")
    return (parsed.netloc or "").strip().lower().removeprefix("www.")


def normalize_snippet(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())[:320]


def fallback_company_name(domain: str) -> str:
    label = (domain or "").split(".", 1)[0].replace("-", " ").replace("_", " ").strip()
    return label.title() if label else "Unknown Company"


def unique(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["company", "domain", "url", "query", "snippet"])
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
