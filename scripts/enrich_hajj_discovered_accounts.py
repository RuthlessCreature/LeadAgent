from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.models import LeadCandidate, ScoreWeights  # noqa: E402
from app.services.public_web import crawl_public_web  # noqa: E402
from app.services.scoring import score_leads  # noqa: E402
from app.services.search import extract_leads  # noqa: E402
from collect_hajj_targets import build_icp, build_product_profile  # noqa: E402


DEFAULT_DISCOVERY_INPUT = ROOT / "deliverables" / "hajj_discovered_accounts.csv"
DEFAULT_EXISTING_COMPANIES_INPUT = ROOT / "deliverables" / "hajj_target_accounts_companies.csv"
DEFAULT_OUTPUT_PREFIX = ROOT / "deliverables" / "hajj_target_accounts_expanded"

BUSINESS_KEYWORDS = (
    "hajj",
    "umrah",
    "ziyarah",
    "pilgrim",
    "travel",
    "tours",
    "package",
    "visa",
)
BLOCKLIST = (
    "apnews",
    "forums.",
    "sherdog",
    "mixedmartialarts",
    "wikipedia",
    "britannica",
    "history.com",
    "tripadvisor",
    "reddit",
    "youtube",
    "facebook",
    "instagram",
    "tiktok",
    "twitter",
    "x.com",
)
GENERIC_COMPANY_NAMES = {
    "contact",
    "contact us",
    "home",
    "hajj",
    "umrah",
    "travel",
    "tour",
    "tours",
    "service",
    "services",
    "visa",
    "packages",
    "umrah package",
    "umrah packages",
    "hajj package",
    "hajj packages",
}
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
PEOPLE_FIELDS = CONTACT_FIELDS
COMPANY_FIELDS = [
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


def main() -> None:
    args = parse_args()
    output_contacts_json = args.output_prefix.with_suffix(".json")
    output_contacts_csv = args.output_prefix.with_suffix(".csv")
    output_people_json = args.output_prefix.with_name(f"{args.output_prefix.name}_people").with_suffix(".json")
    output_people_csv = args.output_prefix.with_name(f"{args.output_prefix.name}_people").with_suffix(".csv")
    output_companies_json = args.output_prefix.with_name(f"{args.output_prefix.name}_companies").with_suffix(".json")
    output_companies_csv = args.output_prefix.with_name(f"{args.output_prefix.name}_companies").with_suffix(".csv")

    discovered_rows = load_csv(args.discovery_input)
    relevant_rows = [row for row in discovered_rows if is_relevant_discovery_result(row)]
    discovered_name_map = build_discovered_name_map(relevant_rows)
    seed_urls = unique([row["url"].strip() for row in relevant_rows if row.get("url")])

    crawl = crawl_public_web(
        seed_urls=seed_urls,
        max_pages_per_domain=args.max_pages_per_domain,
        respect_robots=not args.ignore_robots,
    )
    leads = score_leads(
        extract_leads(crawl.raw_results),
        build_product_profile(),
        build_icp(),
        ScoreWeights(),
    )

    contact_payload = [lead_to_contact_row(lead, discovered_name_map) for lead in leads]
    people_payload = build_people_rows(contact_payload)
    existing_company_rows = load_csv(args.existing_companies_input) if args.existing_companies_input.exists() else []
    merged_companies = merge_company_rows([*existing_company_rows, *[contact_to_company_row(row) for row in contact_payload]])

    write_json(output_contacts_json, contact_payload)
    write_csv(output_contacts_csv, CONTACT_FIELDS, contact_payload)
    write_json(output_people_json, people_payload)
    write_csv(output_people_csv, PEOPLE_FIELDS, people_payload)
    write_json(output_companies_json, merged_companies)
    write_csv(output_companies_csv, COMPANY_FIELDS, merged_companies)

    print(
        f"discovered={len(discovered_rows)} relevant={len(relevant_rows)} seeds={len(seed_urls)} "
        f"visited={len(crawl.visited_urls)} blocked={len(crawl.blocked_urls)} contacts={len(contact_payload)} "
        f"people={len(people_payload)} "
        f"companies={len(merged_companies)}"
    )
    print(output_contacts_json)
    print(output_contacts_csv)
    print(output_people_json)
    print(output_people_csv)
    print(output_companies_json)
    print(output_companies_csv)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich discovered Hajj/Umrah company domains with public website contacts.")
    parser.add_argument(
        "--discovery-input",
        type=Path,
        default=DEFAULT_DISCOVERY_INPUT,
        help="CSV file produced by discovery with company/domain/url/query/snippet columns.",
    )
    parser.add_argument(
        "--existing-companies-input",
        type=Path,
        default=DEFAULT_EXISTING_COMPANIES_INPUT,
        help="Optional company-level CSV to merge into the final company output.",
    )
    parser.add_argument(
        "--output-prefix",
        type=Path,
        default=DEFAULT_OUTPUT_PREFIX,
        help="Output prefix path without extension. Script writes .csv/.json and *_companies.* variants.",
    )
    parser.add_argument(
        "--max-pages-per-domain",
        type=int,
        default=2,
        help="Maximum number of pages to crawl per domain.",
    )
    parser.add_argument(
        "--ignore-robots",
        action="store_true",
        help="Ignore robots.txt. Disabled by default.",
    )
    return parser.parse_args()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def is_relevant_discovery_result(row: dict[str, str]) -> bool:
    haystack = " ".join(
        [
            row.get("company", ""),
            row.get("domain", ""),
            row.get("snippet", ""),
            row.get("url", ""),
        ]
    ).lower()
    if any(block in haystack for block in BLOCKLIST):
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


def lead_to_contact_row(lead: LeadCandidate, discovered_name_map: dict[str, str]) -> dict[str, str]:
    company = resolve_company_name(lead.domain, lead.company, discovered_name_map)
    return {
        "company": company,
        "contact_name": lead.contact_name,
        "role": lead.role,
        "email": lead.email,
        "phone": clean_company_phone(lead.phone),
        "domain": lead.domain,
        "source_url": lead.source_url,
        "source_label": lead.source_label,
        "consent_status": lead.consent_status.value,
        "verification_status": lead.verification_status.value,
        "overall_score": f"{lead.scores.overall:.2f}",
        "raw_text_snippet": lead.raw_text_snippet,
    }


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


def build_people_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        contact_name = (row.get("contact_name") or "").strip()
        if not contact_name:
            continue
        normalized = {field: str(row.get(field, "") or "").strip() for field in CONTACT_FIELDS}
        key = "|".join(
            [
                normalized.get("domain", "").lower(),
                contact_name.lower(),
                normalized.get("email", "").lower(),
                normalized.get("phone", ""),
            ]
        )
        grouped.setdefault(key, []).append(normalized)

    people_rows: list[dict[str, str]] = []
    for key, group in grouped.items():
        ranked = sorted(group, key=contact_row_quality, reverse=True)
        merged = {
            "company": first_non_empty(ranked, "company"),
            "contact_name": first_non_empty(ranked, "contact_name"),
            "role": first_non_empty(ranked, "role"),
            "email": first_non_empty(ranked, "email"),
            "phone": first_non_empty(ranked, "phone"),
            "domain": first_non_empty(ranked, "domain"),
            "source_url": first_non_empty(ranked, "source_url"),
            "source_label": first_non_empty(ranked, "source_label"),
            "consent_status": first_non_empty(ranked, "consent_status"),
            "verification_status": first_non_empty(ranked, "verification_status"),
            "overall_score": f"{max(parse_float(item.get('overall_score', '0')) for item in ranked):.2f}",
            "raw_text_snippet": first_non_empty(ranked, "raw_text_snippet"),
        }
        people_rows.append(merged)

    people_rows.sort(
        key=lambda row: (
            0 if row["email"] else 1,
            0 if row["phone"] else 1,
            row["domain"],
            row["contact_name"],
        )
    )
    return people_rows


def merge_company_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        domain = (row.get("domain") or "").strip().lower()
        if not domain:
            continue
        normalized = {field: str(row.get(field, "") or "").strip() for field in COMPANY_FIELDS}
        normalized["domain"] = domain
        normalized["company"] = resolve_company_name(domain, normalized["company"], {})
        normalized["phone"] = clean_company_phone(normalized["phone"])
        grouped.setdefault(domain, []).append(normalized)

    merged_rows: list[dict[str, str]] = []
    for domain, group in grouped.items():
        ranked = sorted(group, key=row_quality, reverse=True)
        merged = {
            "company": first_non_empty(ranked, "company") or fallback_company_name(domain),
            "email": first_non_empty(ranked, "email"),
            "phone": first_non_empty(ranked, "phone"),
            "domain": domain,
            "source_url": first_non_empty(ranked, "source_url"),
            "consent_status": first_non_empty(ranked, "consent_status"),
            "verification_status": first_non_empty(ranked, "verification_status"),
            "overall_score": f"{max(parse_float(item.get('overall_score', '0')) for item in ranked):.2f}",
            "raw_text_snippet": first_non_empty(ranked, "raw_text_snippet"),
        }
        merged_rows.append(merged)

    merged_rows.sort(key=lambda row: (0 if row["email"] else 1, row["domain"]))
    return merged_rows


def row_quality(row: dict[str, str]) -> tuple[int, int, float, int, int]:
    return (
        1 if row.get("email") else 0,
        1 if row.get("phone") else 0,
        parse_float(row.get("overall_score", "0")),
        len(row.get("raw_text_snippet", "")),
        len(row.get("company", "")),
    )


def contact_row_quality(row: dict[str, str]) -> tuple[int, int, int, int, float, int]:
    return (
        1 if row.get("contact_name") else 0,
        1 if row.get("email") else 0,
        1 if row.get("phone") else 0,
        1 if row.get("role") else 0,
        parse_float(row.get("overall_score", "0")),
        len(row.get("raw_text_snippet", "")),
    )


def first_non_empty(rows: list[dict[str, str]], field: str) -> str:
    for row in rows:
        value = row.get(field, "").strip()
        if value:
            return value
    return ""


def build_discovered_name_map(rows: list[dict[str, str]]) -> dict[str, str]:
    by_domain: dict[str, tuple[int, str]] = {}
    for row in rows:
        domain = (row.get("domain") or "").strip().lower()
        company = normalize_company_name_candidate((row.get("company") or "").strip())
        if not domain or not company:
            continue
        score = company_name_score(company)
        best = by_domain.get(domain)
        if best is None or score > best[0]:
            by_domain[domain] = (score, company)
    return {domain: name for domain, (_, name) in by_domain.items()}


def resolve_company_name(domain: str, current_name: str, discovered_name_map: dict[str, str]) -> str:
    current_candidate = normalize_company_name_candidate(current_name)
    discovered_candidate = normalize_company_name_candidate(discovered_name_map.get(domain, ""))
    fallback_candidate = fallback_company_name(domain)
    candidates = [
        (company_name_score(current_candidate), current_candidate),
        (company_name_score(discovered_candidate), discovered_candidate),
        (company_name_score(fallback_candidate), fallback_candidate),
    ]
    best_score, best_name = max(candidates, key=lambda item: item[0])
    if best_score > 0 and best_name:
        return best_name
    return fallback_company_name(domain)


def normalize_company_name_candidate(name: str) -> str:
    value = re.sub(r"\s+", " ", (name or "").strip())
    if not value:
        return ""

    segments = [segment.strip(" .") for segment in re.split(r"\s*[|:\-]\s*", value) if segment.strip(" .")]
    if not segments:
        return value

    best_score, best_segment = max(((company_name_score(segment), segment) for segment in segments), key=lambda item: item[0])
    if best_score > 0:
        return best_segment
    return value


def company_name_score(name: str) -> int:
    value = re.sub(r"\s+", " ", (name or "").strip())
    if not value:
        return 0

    lowered = value.lower()
    if lowered in GENERIC_COMPANY_NAMES:
        return 0

    score = 0
    length = len(value)
    if 4 <= length <= 40:
        score += 10
    elif length <= 64:
        score += 4
    else:
        score -= 4

    if any(token in lowered for token in ("travel", "tours", "tour", "hajj", "umrah", "pilgrim", "agency", "service")):
        score += 8
    if any(token in lowered for token in ("packages", "tickets", "visa", "pilgrims")) and not any(
        token in lowered for token in ("travel", "tours", "agency", "service")
    ):
        score -= 12
    if lowered.startswith(("best ", "affordable ", "book ", "fulfil ", "start ", "contact ")):
        score -= 8
    if any(phrase in lowered for phrase in (" package from ", " packages from ", " package for ", " packages for ")):
        score -= 10
    if "..." in value:
        score -= 6
    if sum(char.isdigit() for char in value) >= 4 and not any(
        token in lowered for token in ("travel", "tours", "hajj", "umrah")
    ):
        score -= 12
    return max(score, 0)


def fallback_company_name(domain: str) -> str:
    label = domain.split(".", 1)[0].lower().replace("-", " ").replace("_", " ").strip()
    for token in ("travels", "travel", "tours", "tour", "hajj", "umrah", "holidays", "holiday"):
        label = label.replace(token, f" {token} ")
    label = re.sub(r"\s+", " ", label).strip()
    return " ".join(part.capitalize() for part in label.split())


def clean_company_phone(value: str) -> str:
    phone = (value or "").strip()
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return ""
    if len(digits) < 10 and not phone.startswith("+"):
        return ""
    return phone


def parse_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


if __name__ == "__main__":
    main()
