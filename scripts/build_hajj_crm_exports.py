from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "deliverables" / "hajj_target_accounts_polyglot_aliases_companies.csv"
DEFAULT_OUTPUT_PREFIX = ROOT / "deliverables" / "hajj_target_accounts_polyglot_aliases"

CRM_FIELDS = [
    "company",
    "company_clean",
    "domain",
    "website",
    "country_inferred",
    "country_inference_source",
    "region_inferred",
    "tld",
    "email",
    "email_domain",
    "email_type",
    "role_email",
    "free_email_provider",
    "phone_raw",
    "phone_normalized",
    "contact_readiness",
    "outreach_priority",
    "recommended_channel",
    "consent_status",
    "verification_status",
    "overall_score",
    "raw_text_snippet",
]

SUMMARY_FIELDS = [
    "country_inferred",
    "region_inferred",
    "companies",
    "with_email",
    "with_phone",
    "with_both",
    "priority_a",
]

FREE_EMAIL_DOMAINS = {
    "gmail.com",
    "hotmail.com",
    "outlook.com",
    "yahoo.com",
    "yahoo.co.uk",
    "yahoo.com.my",
    "yahoo.com.pk",
    "live.com",
    "aol.com",
    "icloud.com",
    "gmx.com",
    "protonmail.com",
    "yandex.com",
    "yandex.ru",
}

ROLE_LOCAL_PARTS = {
    "admin",
    "booking",
    "bookings",
    "contact",
    "customerservice",
    "enquiries",
    "enquiry",
    "hello",
    "hajj",
    "info",
    "office",
    "quotes",
    "reservation",
    "reservations",
    "sales",
    "support",
    "tour",
    "tours",
    "travel",
    "umrah",
}

COUNTRY_BY_TLD = {
    "uk": "United Kingdom",
    "nl": "Netherlands",
    "au": "Australia",
    "de": "Germany",
    "za": "South Africa",
    "my": "Malaysia",
    "ca": "Canada",
    "nz": "New Zealand",
    "fr": "France",
    "sa": "Saudi Arabia",
    "us": "United States",
    "pk": "Pakistan",
    "bd": "Bangladesh",
    "be": "Belgium",
    "ma": "Morocco",
    "tn": "Tunisia",
    "tr": "Turkey",
    "id": "Indonesia",
    "ae": "United Arab Emirates",
    "eg": "Egypt",
    "qa": "Qatar",
    "sg": "Singapore",
    "ye": "Yemen",
}

REGION_BY_COUNTRY = {
    "Australia": "APAC",
    "Bangladesh": "APAC",
    "Egypt": "MENA",
    "Belgium": "Europe",
    "Canada": "North America",
    "France": "Europe",
    "Germany": "Europe",
    "Indonesia": "APAC",
    "Malaysia": "APAC",
    "Morocco": "MENA",
    "Netherlands": "Europe",
    "New Zealand": "APAC",
    "Pakistan": "APAC",
    "Qatar": "MENA",
    "Saudi Arabia": "MENA",
    "Singapore": "APAC",
    "South Africa": "Africa",
    "Tunisia": "MENA",
    "Turkey": "MENA",
    "United Arab Emirates": "MENA",
    "United Kingdom": "Europe",
    "United States": "North America",
    "Yemen": "MENA",
}

DIAL_CODE_BY_COUNTRY = {
    "Australia": "61",
    "Bangladesh": "880",
    "Belgium": "32",
    "Canada": "1",
    "Egypt": "20",
    "France": "33",
    "Germany": "49",
    "Indonesia": "62",
    "Malaysia": "60",
    "Morocco": "212",
    "Netherlands": "31",
    "New Zealand": "64",
    "Pakistan": "92",
    "Qatar": "974",
    "Saudi Arabia": "966",
    "Singapore": "65",
    "South Africa": "27",
    "Tunisia": "216",
    "Turkey": "90",
    "United Arab Emirates": "971",
    "United Kingdom": "44",
    "United States": "1",
    "Yemen": "967",
}

COUNTRY_BY_DIAL_CODE = {
    "966": "Saudi Arabia",
    "974": "Qatar",
    "971": "United Arab Emirates",
    "967": "Yemen",
    "880": "Bangladesh",
    "216": "Tunisia",
    "212": "Morocco",
    "92": "Pakistan",
    "64": "New Zealand",
    "65": "Singapore",
    "62": "Indonesia",
    "61": "Australia",
    "60": "Malaysia",
    "49": "Germany",
    "44": "United Kingdom",
    "33": "France",
    "32": "Belgium",
    "31": "Netherlands",
    "27": "South Africa",
    "20": "Egypt",
    "90": "Turkey",
    "1": "North America",
}

NANP_AREA_CODES = {
    "201": "United States",
    "204": "Canada",
    "202": "United States",
    "203": "United States",
    "206": "United States",
    "208": "United States",
    "212": "United States",
    "214": "United States",
    "215": "United States",
    "216": "United States",
    "224": "United States",
    "240": "United States",
    "248": "United States",
    "281": "United States",
    "289": "Canada",
    "305": "United States",
    "307": "United States",
    "312": "United States",
    "313": "United States",
    "323": "United States",
    "347": "United States",
    "403": "Canada",
    "404": "United States",
    "407": "United States",
    "408": "United States",
    "410": "United States",
    "415": "United States",
    "416": "Canada",
    "438": "Canada",
    "425": "United States",
    "437": "Canada",
    "514": "Canada",
    "587": "Canada",
    "602": "United States",
    "604": "Canada",
    "613": "Canada",
    "614": "United States",
    "617": "United States",
    "631": "United States",
    "647": "Canada",
    "650": "United States",
    "656": "United States",
    "667": "United States",
    "678": "United States",
    "703": "United States",
    "704": "United States",
    "713": "United States",
    "718": "United States",
    "773": "United States",
    "780": "Canada",
    "813": "United States",
    "832": "United States",
    "872": "United States",
    "888": "North America",
    "905": "Canada",
    "917": "United States",
    "919": "United States",
    "929": "United States",
    "980": "United States",
}

MARKETING_TOKENS = {
    "affordable",
    "agency",
    "agents",
    "approved",
    "best",
    "booking",
    "complete",
    "contact",
    "expert",
    "flight",
    "flights",
    "hotel",
    "hotels",
    "islamic",
    "package",
    "packages",
    "premium",
    "service",
    "services",
    "trusted",
}

DOMAIN_WORD_PATTERN = re.compile(
    r"(travels|travel|tours|tour|holidays|holiday|agency|group|hajj|umrah)",
    flags=re.IGNORECASE,
)

GENERIC_DOMAIN_LABELS = {
    "www",
    "booking",
    "bookings",
    "blog",
    "careers",
    "contact",
    "help",
    "info",
    "mail",
    "m",
    "portal",
    "shop",
    "support",
    "web",
}

GEO_DOMAIN_LABELS = {
    "africa",
    "america",
    "australia",
    "canada",
    "france",
    "germany",
    "indonesia",
    "malaysia",
    "pakistan",
    "saudi",
    "singapore",
    "turkey",
    "uk",
    "usa",
}

COMPANY_CONNECTOR_WORDS = {
    "and",
    "by",
    "co",
    "de",
    "des",
    "du",
    "et",
    "for",
    "from",
    "in",
    "ltd",
    "llc",
    "of",
    "the",
    "to",
}

LOW_SIGNAL_COMPANY_WORDS = MARKETING_TOKENS | {
    "book",
    "guide",
    "haji",
    "hotel",
    "hotels",
    "journey",
    "lane",
    "omra",
    "package",
    "packages",
    "pilgrimage",
    "price",
    "prices",
    "travel",
    "travels",
    "tour",
    "tours",
    "umrah",
    "umroh",
}

COUNTRY_HINT_RULES = [
    ("United States", (" usa ", " united states ", " usa based ", " usa citizens ", " texas ", " new york ", " michigan ", " ohio ", " washington ", " detroit ", " dallas ", " chicago ", " tampa ", " atlanta ", " houston ", " maryland ", " philadelphia ")),
    ("Canada", (" canada ", " canadian ", " montreal ", " toronto ", " mississauga ", " ottawa ", " vancouver ")),
    ("Australia", (" australia ", " australian ", " melbourne ", " sydney ")),
    ("United Kingdom", (" uk ", " united kingdom ", " britain ", " england ", " london ", " birmingham ", " manchester ")),
    ("Indonesia", (" indonesia ", " jakarta ", " haji khusus ", " travel umroh ")),
    ("France", (" france ", " paris ", " depuis la france ")),
    ("Singapore", (" singapore ",)),
    ("Egypt", (" egypt ", " cairo ",)),
    ("Qatar", (" qatar ", " doha ",)),
    ("United Arab Emirates", (" uae ", " dubai ", " abu dhabi ", " emirates ")),
    ("Saudi Arabia", (" saudi arabia ", " saudi ",)),
    ("Turkey", (" turkey ", " istanbul ",)),
    ("Morocco", (" morocco ", " maroc ", " casablanca ", " rabat ")),
    ("Bangladesh", (" bangladesh ", " dhaka ",)),
    ("Pakistan", (" pakistan ", " karachi ", " lahore ",)),
]


def main() -> None:
    args = parse_args()
    rows = load_csv(args.input)
    crm_rows = [build_crm_row(row) for row in rows]
    crm_rows.sort(key=lambda row: (priority_rank(row["outreach_priority"]), row["country_inferred"], row["domain"]))

    summary_rows = build_country_summary(crm_rows)
    priority_a_rows = [row for row in crm_rows if row["outreach_priority"] == "A"]

    crm_csv = args.output_prefix.with_name(f"{args.output_prefix.name}_crm_ready").with_suffix(".csv")
    crm_json = args.output_prefix.with_name(f"{args.output_prefix.name}_crm_ready").with_suffix(".json")
    summary_csv = args.output_prefix.with_name(f"{args.output_prefix.name}_country_summary").with_suffix(".csv")
    summary_json = args.output_prefix.with_name(f"{args.output_prefix.name}_country_summary").with_suffix(".json")
    priority_a_csv = args.output_prefix.with_name(f"{args.output_prefix.name}_priority_a").with_suffix(".csv")

    write_csv(crm_csv, CRM_FIELDS, crm_rows)
    write_json(crm_json, crm_rows)
    write_csv(summary_csv, SUMMARY_FIELDS, summary_rows)
    write_json(summary_json, summary_rows)
    write_csv(priority_a_csv, CRM_FIELDS, priority_a_rows)

    print(
        f"companies={len(crm_rows)} priority_a={len(priority_a_rows)} "
        f"countries={len(summary_rows)} with_email={sum(1 for row in crm_rows if row['email'])} "
        f"with_phone={sum(1 for row in crm_rows if row['phone_normalized'])}"
    )
    print(crm_csv)
    print(crm_json)
    print(summary_csv)
    print(summary_json)
    print(priority_a_csv)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build CRM-ready exports from Hajj/Umrah company-level public-web data.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Company-level CSV input file.")
    parser.add_argument("--output-prefix", type=Path, default=DEFAULT_OUTPUT_PREFIX, help="Output prefix without suffix.")
    return parser.parse_args()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_crm_row(row: dict[str, str]) -> dict[str, str]:
    domain = normalize_domain(row.get("domain", ""))
    email = normalize_email(row.get("email", ""))
    source_url = (row.get("source_url") or "").strip()
    phone_raw = normalize_whitespace(row.get("phone", ""))
    company_clean = clean_company_name(row.get("company", ""), domain)
    country, source = infer_country(row, domain, email, phone_raw)
    region = REGION_BY_COUNTRY.get(country, "Unknown")
    phone_normalized = normalize_phone(phone_raw, country)
    email_domain = email.split("@", 1)[1] if "@" in email else ""
    email_type = classify_email_type(email, domain)
    role_email = "yes" if is_role_email(email) else "no"
    free_email_provider = "yes" if email_domain in FREE_EMAIL_DOMAINS else "no"
    contact_readiness = classify_contact_readiness(bool(email), bool(phone_normalized))
    outreach_priority = classify_outreach_priority(email_type, bool(phone_normalized), safe_float(row.get("overall_score", "0")))
    recommended_channel = classify_recommended_channel(email_type, bool(email), bool(phone_normalized))

    return {
        "company": (row.get("company") or "").strip(),
        "company_clean": company_clean,
        "domain": domain,
        "website": source_url or (f"https://{domain}" if domain else ""),
        "country_inferred": country,
        "country_inference_source": source,
        "region_inferred": region,
        "tld": domain.rsplit(".", 1)[-1].lower() if "." in domain else "",
        "email": email,
        "email_domain": email_domain,
        "email_type": email_type,
        "role_email": role_email,
        "free_email_provider": free_email_provider,
        "phone_raw": phone_raw,
        "phone_normalized": phone_normalized,
        "contact_readiness": contact_readiness,
        "outreach_priority": outreach_priority,
        "recommended_channel": recommended_channel,
        "consent_status": (row.get("consent_status") or "").strip(),
        "verification_status": (row.get("verification_status") or "").strip(),
        "overall_score": f"{safe_float(row.get('overall_score', '0')):.2f}",
        "raw_text_snippet": (row.get("raw_text_snippet") or "").strip(),
    }


def build_country_summary(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        key = (row["country_inferred"], row["region_inferred"])
        grouped.setdefault(key, []).append(row)

    summary_rows: list[dict[str, str]] = []
    for (country, region), items in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0][0])):
        with_email = sum(1 for item in items if item["email"])
        with_phone = sum(1 for item in items if item["phone_normalized"])
        with_both = sum(1 for item in items if item["email"] and item["phone_normalized"])
        priority_a = sum(1 for item in items if item["outreach_priority"] == "A")
        summary_rows.append(
            {
                "country_inferred": country,
                "region_inferred": region,
                "companies": str(len(items)),
                "with_email": str(with_email),
                "with_phone": str(with_phone),
                "with_both": str(with_both),
                "priority_a": str(priority_a),
            }
        )
    return summary_rows


def normalize_domain(value: str) -> str:
    return (value or "").strip().lower().removeprefix("www.")


def normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def normalize_lookup_text(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value or "")
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    folded = folded.lower()
    folded = re.sub(r"[^a-z0-9]+", " ", folded)
    return normalize_whitespace(folded)


def clean_company_name(name: str, domain: str) -> str:
    current = normalize_whitespace(name)
    current = current.replace("»", " ").replace("|", " ")
    current = normalize_whitespace(current)
    derived = derive_company_name_from_domain(domain)

    if not current:
        return derived

    candidates = [current]
    for part in re.split(r"\s+[–—-]\s+|[|,:]+", current):
        cleaned = normalize_whitespace(part)
        if cleaned and cleaned not in candidates:
            candidates.append(cleaned)

    best = max(candidates, key=lambda candidate: company_name_score(candidate, derived))
    if should_use_derived_company_name(best, derived):
        return derived
    return best


def derive_company_name_from_domain(domain: str) -> str:
    labels = [label for label in normalize_domain(domain).split(".") if label]
    if len(labels) > 1:
        labels = labels[:-1]
    if not labels:
        return "Unknown Company"

    filtered = [label for label in labels if label not in GENERIC_DOMAIN_LABELS]
    if not filtered:
        filtered = labels

    non_geo = [label for label in filtered if label not in GEO_DOMAIN_LABELS]
    label = max(non_geo or filtered, key=len)
    if filtered and filtered[0] in GEO_DOMAIN_LABELS and filtered[0] != label:
        label = f"{label} {filtered[0]}"

    label = label.lower().replace("-", " ").replace("_", " ").strip()
    label = DOMAIN_WORD_PATTERN.sub(r" \1 ", label)
    label = normalize_whitespace(label)
    if not label:
        return "Unknown Company"
    return " ".join(part.capitalize() for part in label.split())


def infer_country(row: dict[str, str], domain: str, email: str, phone_raw: str) -> tuple[str, str]:
    country = infer_country_from_domain(domain)
    if country != "Unknown":
        return country, "domain_tld"

    email_domain = email.split("@", 1)[1] if "@" in email else ""
    country = infer_country_from_domain(email_domain)
    if country != "Unknown":
        return country, "email_tld"

    source_country = infer_country_from_domain(extract_domain(row.get("source_url", "")))
    if source_country != "Unknown":
        return source_country, "source_url_tld"

    text_country = infer_country_from_text(" ".join(filter(None, [row.get("company", ""), row.get("source_url", ""), row.get("raw_text_snippet", "")])))
    if text_country != "Unknown":
        return text_country, "text_hint"

    phone_country = infer_country_from_phone(phone_raw)
    if phone_country != "Unknown":
        return phone_country, "phone"

    return "Unknown", "unknown"


def infer_country_from_domain(domain: str) -> str:
    if not domain or "." not in domain:
        return "Unknown"
    tld = domain.rsplit(".", 1)[-1].lower()
    return COUNTRY_BY_TLD.get(tld, "Unknown")


def infer_country_from_phone(phone: str) -> str:
    for candidate in extract_phone_candidates(phone):
        digits = candidate.lstrip("+")
        nanp_country = infer_nanp_country(digits)
        if nanp_country != "Unknown":
            return nanp_country

        local_country = infer_country_from_local_phone(digits)
        if local_country != "Unknown":
            return local_country

        for length in (3, 2, 1):
            prefix = digits[:length]
            if prefix not in COUNTRY_BY_DIAL_CODE:
                continue
            if not candidate.startswith("+") and (len(digits) <= 10 or prefix == "1"):
                continue
            country = COUNTRY_BY_DIAL_CODE[prefix]
            if country != "North America":
                return country
            area_code = digits[length : length + 3]
            return NANP_AREA_CODES.get(area_code, "North America")
    return "Unknown"


def extract_domain(url: str) -> str:
    match = re.search(r"https?://([^/]+)", url or "")
    if not match:
        return ""
    return match.group(1).lower().removeprefix("www.")


def normalize_phone(phone: str, country_hint: str) -> str:
    best_value = ""
    best_score = -1
    for candidate in extract_phone_candidates(phone):
        formatted, score = format_phone_candidate(candidate, country_hint)
        if score > best_score:
            best_value = formatted
            best_score = score
    return best_value


def normalize_phone_like(phone: str) -> str:
    if not phone:
        return ""
    converted: list[str] = []
    for char in str(phone):
        if char.isdigit():
            try:
                converted.append(str(unicodedata.decimal(char)))
            except Exception:
                converted.append(char)
        else:
            converted.append(char)
    text = "".join(converted)
    text = re.sub(r"(?i)\b(?:ext|extension|x)\b\.?\s*\d+\s*$", "", text)
    text = text.replace("\u00a0", " ")
    text = normalize_whitespace(text)
    if text.startswith("00"):
        text = f"+{text[2:]}"
    plus = "+" if text.startswith("+") else ""
    digits = re.sub(r"\D", "", text)
    if not digits:
        return ""
    return f"{plus}{digits}" if plus else digits


def extract_phone_candidates(phone: str) -> list[str]:
    text = normalize_whitespace(phone)
    if not text:
        return []

    segments = [segment.strip() for segment in re.split(r"(?i)\b(?:or|and)\b|[|/;,]", text) if segment.strip()]
    if not segments:
        segments = [text]

    candidates: list[str] = []
    for segment in segments:
        normalized = normalize_phone_like(segment)
        if normalized:
            candidates.append(normalized)

        tokens = re.findall(r"\d+", segment)
        for start in range(len(tokens)):
            for end in range(start + 1, min(len(tokens), start + 5) + 1):
                combined = "".join(tokens[start:end])
                if len(combined) < 8:
                    continue
                if segment.lstrip().startswith("+") and start == 0:
                    candidates.append(f"+{combined}")
                else:
                    candidates.append(combined)

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            deduped.append(candidate)
    return deduped


def infer_country_from_text(text: str) -> str:
    normalized = normalize_lookup_text(text)
    if not normalized:
        return "Unknown"
    lookup = f" {normalized} "

    best_country = "Unknown"
    best_score = 0
    for country, keywords in COUNTRY_HINT_RULES:
        score = sum(1 for keyword in keywords if keyword in lookup)
        if score > best_score:
            best_country = country
            best_score = score
    return best_country if best_score else "Unknown"


def company_name_score(candidate: str, derived: str) -> int:
    lookup = normalize_lookup_text(candidate)
    if not lookup:
        return -999

    words = lookup.split()
    derived_words = set(normalize_lookup_text(derived).split())
    overlap = sum(1 for word in words if word in derived_words)
    low_signal = sum(1 for word in words if word in LOW_SIGNAL_COMPANY_WORDS)
    connectors = sum(1 for word in words if word in COMPANY_CONNECTOR_WORDS)

    score = overlap * 8
    score += max(0, 6 - abs(len(words) - 3))
    score -= low_signal * 3
    score -= max(0, len(words) - 6) * 3
    if re.search(r"\b20\d{2}\b", candidate):
        score -= 8
    if any(char in candidate for char in "!?"):
        score -= 6
    if "contact us" in candidate.lower():
        score -= 12
    if overlap == 0 and low_signal >= max(2, len(words) - connectors - 1):
        score -= 14
    return score


def should_use_derived_company_name(candidate: str, derived: str) -> bool:
    lowered = candidate.lower()
    if lowered in {"hajj", "umrah", "travel", "tour", "tours", "service", "services"}:
        return True
    if candidate.endswith(" S") or candidate.endswith(" s"):
        return True
    if "contact us" in lowered:
        return True

    words = normalize_lookup_text(candidate).split()
    derived_words = set(normalize_lookup_text(derived).split())
    overlap = sum(1 for word in words if word in derived_words)
    low_signal = sum(1 for word in words if word in LOW_SIGNAL_COMPANY_WORDS)
    if not words:
        return True
    if len(words) < 2 and overlap == 0:
        return True
    if re.search(r"\b20\d{2}\b", candidate) and overlap < 2:
        return True
    if any(char in candidate for char in "!?") and overlap == 0:
        return True
    if len(words) >= 4 and overlap < 2 and low_signal >= 2:
        return True
    if words and all(word in LOW_SIGNAL_COMPANY_WORDS or word in COMPANY_CONNECTOR_WORDS for word in words):
        return True
    return False


def infer_nanp_country(digits: str) -> str:
    if len(digits) == 11 and digits.startswith("1") and digits[1] in "23456789":
        return NANP_AREA_CODES.get(digits[1:4], "North America")
    if len(digits) == 10 and digits[0] in "23456789":
        return NANP_AREA_CODES.get(digits[:3], "North America")
    return "Unknown"


def infer_country_from_local_phone(digits: str) -> str:
    if len(digits) == 11 and digits.startswith("01"):
        return "Bangladesh"
    if len(digits) in {10, 11} and digits.startswith(("020", "011", "012", "013", "014", "015", "016", "017", "018", "019")):
        return "United Kingdom"
    if len(digits) == 11 and digits.startswith("07"):
        return "United Kingdom"
    if len(digits) == 10 and digits.startswith(("01", "02", "03", "04", "05", "06", "07", "09")):
        return "France"
    if len(digits) in {10, 11, 12, 13} and digits.startswith(("021", "08")):
        return "Indonesia"
    if len(digits) == 11 and digits.startswith(("010", "011", "012", "015")):
        return "Egypt"
    if len(digits) in {10, 11} and digits.startswith(("05", "5")):
        return "Turkey"
    return "Unknown"


def format_phone_candidate(candidate: str, country_hint: str) -> tuple[str, int]:
    digits = candidate.lstrip("+")
    if not digits:
        return "", -1

    if candidate.startswith("+"):
        for length in (3, 2, 1):
            prefix = digits[:length]
            if prefix not in COUNTRY_BY_DIAL_CODE:
                continue
            country = COUNTRY_BY_DIAL_CODE[prefix]
            if country == "North America":
                if len(digits) not in {10, 11}:
                    continue
                country = infer_nanp_country(digits)
            if country != "Unknown" and 8 <= len(digits) <= 15:
                score = 95
                if country_hint and country == country_hint:
                    score += 10
                return f"+{digits}", score

    nanp_value = format_nanp_phone(digits)
    if nanp_value:
        score = 90
        inferred_country = infer_nanp_country(nanp_value.lstrip("+"))
        if country_hint and inferred_country == country_hint:
            score += 10
        return nanp_value, score

    local_value = format_local_phone(digits, country_hint)
    if local_value:
        return local_value, 80

    for length in (3, 2, 1):
        prefix = digits[:length]
        if prefix not in COUNTRY_BY_DIAL_CODE:
            continue
        if prefix == "1":
            continue
        country = COUNTRY_BY_DIAL_CODE[prefix]
        if country == "North America":
            if len(digits) not in {10, 11}:
                continue
            country = infer_nanp_country(digits)
        if country != "Unknown" and 8 <= len(digits) <= 15:
            score = 70
            if country_hint and country == country_hint:
                score += 10
            return f"+{digits}", score

    if country_hint:
        dial_code = DIAL_CODE_BY_COUNTRY.get(country_hint, "")
        if dial_code and 8 <= len(digits) <= 12:
            local_digits = digits[1:] if digits.startswith("0") else digits
            return f"+{dial_code}{local_digits}", 65

    if 8 <= len(digits) <= 15 and candidate.startswith("+"):
        return f"+{digits}", 40
    return "", -1


def format_nanp_phone(digits: str) -> str:
    candidates = [digits]
    if len(digits) > 11:
        for start in range(0, len(digits) - 9):
            candidates.append(digits[start : start + 10])
        for start in range(0, len(digits) - 10):
            candidates.append(digits[start : start + 11])

    for candidate in candidates:
        if len(candidate) == 11 and candidate.startswith("1") and candidate[1] in "23456789" and candidate[4] in "23456789":
            return f"+{candidate}"
        if len(candidate) == 10 and candidate[0] in "23456789" and candidate[3] in "23456789":
            return f"+1{candidate}"
    return ""


def format_local_phone(digits: str, country_hint: str) -> str:
    if country_hint in {"United States", "Canada", "North America"}:
        return format_nanp_phone(digits)
    if country_hint == "United Kingdom" and len(digits) in {10, 11} and digits.startswith("0"):
        return f"+44{digits[1:]}"
    if country_hint == "France" and len(digits) == 10 and digits.startswith("0"):
        return f"+33{digits[1:]}"
    if country_hint == "Bangladesh" and len(digits) == 11 and digits.startswith("0"):
        return f"+880{digits[1:]}"
    if country_hint == "Indonesia" and len(digits) in {10, 11, 12, 13} and digits.startswith("0"):
        return f"+62{digits[1:]}"
    if country_hint == "Egypt" and len(digits) == 11 and digits.startswith("0"):
        return f"+20{digits[1:]}"
    if country_hint == "Turkey" and len(digits) == 11 and digits.startswith("0"):
        return f"+90{digits[1:]}"
    if country_hint == "Singapore" and len(digits) == 8:
        return f"+65{digits}"
    if country_hint == "Qatar" and len(digits) == 8:
        return f"+974{digits}"
    if country_hint == "United Arab Emirates" and len(digits) in {8, 9, 10}:
        return f"+971{digits[1:] if digits.startswith('0') else digits}"
    if country_hint == "Australia":
        if len(digits) == 10 and digits.startswith("0"):
            return f"+61{digits[1:]}"
        if len(digits) == 9 and digits.startswith(("2", "3", "4", "7", "8")):
            return f"+61{digits}"
    return ""


def clean_company_name(name: str, domain: str) -> str:
    current = normalize_whitespace(name)
    current = current.replace("禄", " ").replace("|", " ")
    current = normalize_whitespace(current)
    derived = derive_company_name_from_domain(domain)

    if not current:
        return derived

    candidates = [current]
    for part in re.split(r"\s+[-\u2013\u2014]\s+|[|,:]+", current):
        cleaned = normalize_whitespace(part)
        if cleaned and cleaned not in candidates:
            candidates.append(cleaned)

    best = max(candidates, key=lambda candidate: company_name_score(candidate, derived))
    if should_use_derived_company_name(best, derived):
        return derived
    return best


def classify_email_type(email: str, company_domain: str) -> str:
    if not email or "@" not in email:
        return "missing"
    email_domain = email.split("@", 1)[1].lower()
    if email_domain in FREE_EMAIL_DOMAINS:
        return "free_provider"
    if email_domain == company_domain:
        return "company_domain"
    return "external_domain"


def is_role_email(email: str) -> bool:
    if "@" not in email:
        return False
    local = email.split("@", 1)[0].lower()
    return local in ROLE_LOCAL_PARTS


def classify_contact_readiness(has_email: bool, has_phone: bool) -> str:
    if has_email and has_phone:
        return "email_and_phone"
    if has_email:
        return "email_only"
    if has_phone:
        return "phone_only"
    return "insufficient"


def classify_outreach_priority(email_type: str, has_phone: bool, overall_score: float) -> str:
    if email_type == "company_domain" and has_phone and overall_score >= 24:
        return "A"
    if email_type in {"company_domain", "external_domain"} and has_phone:
        return "B"
    if email_type != "missing" or has_phone:
        return "C"
    return "D"


def classify_recommended_channel(email_type: str, has_email: bool, has_phone: bool) -> str:
    if email_type == "company_domain":
        return "email_first"
    if has_phone and not has_email:
        return "phone_first"
    if has_email and has_phone:
        return "email_then_phone"
    if has_email:
        return "email_first"
    if has_phone:
        return "phone_first"
    return "manual_review"


def priority_rank(value: str) -> int:
    return {"A": 0, "B": 1, "C": 2, "D": 3}.get(value, 9)


def safe_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


if __name__ == "__main__":
    main()
