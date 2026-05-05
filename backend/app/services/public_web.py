from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from collections import deque
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import unquote, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from app.models import ConsentStatus, LeadSourceType, Platform, VerificationStatus


DEFAULT_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

EMAIL_RE = re.compile(r"([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})", flags=re.IGNORECASE)
PHONE_RE = re.compile(r"(\+?\d[\d()\-\s]{6,}\d)")
CONTACT_HINTS = (
    "contact",
    "about",
    "team",
    "staff",
    "leadership",
    "management",
    "company",
    "sales",
    "support",
    "advisor",
    "consultant",
    "kontakt",
    "impressum",
)
GENERIC_LOCAL_PARTS = {"info", "sales", "contact", "hello", "support", "team", "office"}
MAX_TEXT_LEN = 320
PLACEHOLDER_PHONE_DIGITS = {"0123456789", "123456789", "1234567890"}
GENERIC_TITLE_PARTS = {
    "about",
    "about us",
    "contact",
    "contact us",
    "home",
    "all",
    "hajj",
    "umrah",
    "packages",
}
GENERIC_BUSINESS_TITLE_HINTS = {
    "solutions",
    "systems",
    "group",
    "company",
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
    "travel",
    "tours",
    "agency",
}
PERSON_BLOCK_HINTS = (
    "team",
    "staff",
    "member",
    "employee",
    "leadership",
    "management",
    "advisor",
    "consult",
    "profile",
    "agent",
    "person",
    "director",
    "founder",
)
PERSON_BLOCK_SKIP_PHRASES = (
    "design by",
    "powered by",
    "created by",
    "developed by",
    "website by",
    "follow us",
    "register now",
)
PERSON_CONTAINER_TAGS = {"article", "section", "div", "li", "tr", "td", "p", "address"}
PERSON_ROLE_LABELS = [
    ("managing director", "Managing Director"),
    ("general manager", "General Manager"),
    ("operations manager", "Operations Manager"),
    ("sales manager", "Sales Manager"),
    ("marketing manager", "Marketing Manager"),
    ("business development manager", "Business Development Manager"),
    ("travel consultant", "Travel Consultant"),
    ("customer service", "Customer Service"),
    ("reservation manager", "Reservation Manager"),
    ("reservations manager", "Reservations Manager"),
    ("booking manager", "Booking Manager"),
    ("founder", "Founder"),
    ("co-founder", "Co-Founder"),
    ("cofounder", "Co-Founder"),
    ("owner", "Owner"),
    ("director", "Director"),
    ("manager", "Manager"),
    ("consultant", "Consultant"),
    ("advisor", "Advisor"),
    ("agent", "Agent"),
    ("ceo", "CEO"),
    ("chief executive", "CEO"),
]
PERSON_NAME_PREFIXES = {
    "mr",
    "mrs",
    "ms",
    "dr",
    "haji",
    "hajji",
    "imam",
    "sheikh",
    "shaykh",
    "sister",
    "brother",
    "ustadh",
    "ustaz",
}
PERSON_NAME_CONNECTORS = {"al", "el", "bin", "binti", "ibn", "van", "de", "del", "da", "di", "la", "le"}
PERSON_NAME_STOPWORDS = {
    "about",
    "account",
    "address",
    "admin",
    "advisor",
    "agency",
    "agent",
    "booking",
    "call",
    "ceo",
    "company",
    "consultant",
    "contact",
    "customer",
    "department",
    "desk",
    "director",
    "email",
    "founder",
    "general",
    "group",
    "guide",
    "hajj",
    "hello",
    "hotel",
    "info",
    "leadership",
    "manager",
    "member",
    "office",
    "operations",
    "owner",
    "package",
    "packages",
    "person",
    "phone",
    "profile",
    "reservation",
    "reservations",
    "sales",
    "service",
    "services",
    "staff",
    "support",
    "team",
    "tour",
    "tours",
    "travel",
    "travels",
    "umrah",
    "advice",
    "app",
    "ask",
    "arayin",
    "baltimore",
    "bel",
    "berat",
    "beratung",
    "cape",
    "chat",
    "clear",
    "created",
    "details",
    "email",
    "fastest",
    "find",
    "follow",
    "free",
    "get",
    "help",
    "hemen",
    "hubungi",
    "investing",
    "interested",
    "kami",
    "kuala",
    "libur",
    "limited",
    "lizenz",
    "lumpur",
    "makkah",
    "malaysia",
    "message",
    "minggu",
    "money",
    "nasional",
    "need",
    "now",
    "nummer",
    "online",
    "ons",
    "operasi",
    "pemasaran",
    "pejabat",
    "price",
    "questions",
    "quote",
    "register",
    "remaining",
    "response",
    "rufe",
    "saudi",
    "sende",
    "sketch",
    "sky",
    "social",
    "society",
    "specialists",
    "spots",
    "still",
    "toll",
    "touch",
    "town",
    "transfer",
    "tutup",
    "utama",
    "waktu",
    "visa",
    "view",
    "whatsapp",
}


@dataclass
class CrawlOutcome:
    raw_results: list[dict]
    visited_urls: list[str]
    blocked_urls: list[str]


@dataclass
class FetchResult:
    final_url: str
    text: str


def crawl_public_web(
    seed_urls: list[str],
    max_pages_per_domain: int = 4,
    respect_robots: bool = True,
) -> CrawlOutcome:
    raw_results: list[dict] = []
    visited_urls: list[str] = []
    blocked_urls: list[str] = []
    normalized_seeds = [normalized for normalized in (_normalize_url(seed) for seed in seed_urls) if normalized]
    max_workers = max(1, min(8, len(normalized_seeds)))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(_crawl_seed, seed_url, max_pages_per_domain, respect_robots): seed_url
            for seed_url in normalized_seeds
        }
        for future in as_completed(future_map):
            outcome = future.result()
            raw_results.extend(outcome.raw_results)
            visited_urls.extend(outcome.visited_urls)
            blocked_urls.extend(outcome.blocked_urls)

    return CrawlOutcome(
        raw_results=_deduplicate_raw_results(raw_results),
        visited_urls=visited_urls,
        blocked_urls=blocked_urls,
    )


def _crawl_seed(seed_url: str, max_pages_per_domain: int, respect_robots: bool) -> CrawlOutcome:
    session = requests.Session()
    session.headers.update({"User-Agent": DEFAULT_BROWSER_UA})

    raw_results: list[dict] = []
    visited_urls: list[str] = []
    blocked_urls: list[str] = []

    domain = _domain(seed_url)
    robots = _load_robots_parser(session, seed_url) if respect_robots else None
    queue: deque[str] = deque([seed_url])
    seen_urls: set[str] = set()
    pages_crawled = 0

    while queue and pages_crawled < max_pages_per_domain:
        current = queue.popleft()
        if current in seen_urls:
            continue
        seen_urls.add(current)

        if robots is not None and not robots.can_fetch(session.headers["User-Agent"], current):
            blocked_urls.append(current)
            continue

        fetched = _fetch_html(session, current)
        if fetched is None:
            continue

        pages_crawled += 1
        visited_urls.append(fetched.final_url)
        soup = BeautifulSoup(fetched.text, "html.parser")

        raw_results.extend(_extract_contacts_from_page(soup, fetched.final_url))

        for link in _candidate_links(soup, fetched.final_url, domain):
            if link not in seen_urls and link not in queue:
                queue.append(link)

    return CrawlOutcome(
        raw_results=raw_results,
        visited_urls=visited_urls,
        blocked_urls=blocked_urls,
    )


def _normalize_url(url: str) -> str:
    value = (url or "").strip()
    if not value:
        return ""
    if "://" not in value:
        value = f"https://{value}"

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""

    path = parsed.path or "/"
    normalized = urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", "", ""))
    return normalized.rstrip("/") or normalized


def _domain(url: str) -> str:
    return (urlparse(url).netloc or "").lower()


def _load_robots_parser(session: requests.Session, url: str) -> RobotFileParser | None:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        response = session.get(robots_url, timeout=6)
        if response.status_code >= 400:
            return None
        parser = RobotFileParser()
        parser.parse(response.text.splitlines())
        return parser
    except requests.RequestException:
        return None


def _fetch_html(session: requests.Session, url: str) -> FetchResult | None:
    try:
        response = session.get(url, timeout=10, allow_redirects=True)
        response.raise_for_status()
    except requests.RequestException:
        return None

    content_type = (response.headers.get("content-type") or "").lower()
    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        return None

    return FetchResult(
        final_url=_normalize_url(response.url),
        text=response.text[:1_500_000],
    )


def _candidate_links(soup: BeautifulSoup, base_url: str, domain: str) -> Iterable[str]:
    for anchor in soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        if not href:
            continue
        absolute = _normalize_url(urljoin(base_url, href))
        if not absolute or _domain(absolute) != domain:
            continue

        combined = f"{href} {anchor.get_text(' ', strip=True)}".lower()
        if any(hint in combined for hint in CONTACT_HINTS):
            yield absolute


def _extract_contacts_from_page(soup: BeautifulSoup, page_url: str) -> list[dict]:
    company = _company_name(soup, page_url)
    page_text = soup.get_text(" ", strip=True)
    snippet = _page_snippet(soup, page_text)
    emails = _emails_from_page(soup, page_text)
    phones = _phones_from_text(page_text)
    domain = _domain(page_url).replace("www.", "")
    person_records = _person_records_from_page(soup, page_url, company, domain)

    if person_records:
        return person_records

    if not emails and not phones:
        return []

    records: list[dict] = []
    if emails:
        for email in emails:
            records.append(
                {
                    "company": company,
                    "contact_name": "",
                    "role": "",
                    "email": email,
                    "phone": phones[0] if phones else "",
                    "linkedin": "",
                    "domain": domain,
                    "industry": [],
                    "snippet": snippet,
                    "platform": Platform.public_web.value,
                    "source_type": LeadSourceType.public_web.value,
                    "source_label": "Public website crawl",
                    "source_url": page_url,
                    "consent_status": _consent_status_for_email(email).value,
                    "verification_status": VerificationStatus.email_verified.value,
                }
            )
    else:
        records.append(
            {
                "company": company,
                "contact_name": "",
                "role": "",
                "email": "",
                "phone": phones[0],
                "linkedin": "",
                "domain": domain,
                "industry": [],
                "snippet": snippet,
                "platform": Platform.public_web.value,
                "source_type": LeadSourceType.public_web.value,
                "source_label": "Public website crawl",
                "source_url": page_url,
                "consent_status": ConsentStatus.unknown.value,
                "verification_status": VerificationStatus.phone_verified.value,
            }
        )

    return records


def _person_records_from_page(soup: BeautifulSoup, page_url: str, company: str, domain: str) -> list[dict]:
    records: list[dict] = []
    seen: set[str] = set()

    for block in _candidate_contact_blocks(soup):
        block_text = block.get_text(" ", strip=True)
        if not block_text:
            continue
        lowered_block = block_text.lower()
        if any(phrase in lowered_block for phrase in PERSON_BLOCK_SKIP_PHRASES):
            continue

        emails = _emails_from_page(block, block_text)
        phones = _phones_from_text(block_text)
        if not emails and not phones:
            continue

        name = _person_name_from_block(block, company)
        if not name:
            continue

        role = _person_role_from_text(block_text)
        name_score = _person_name_score(name, company)
        email = _best_person_email(emails)
        phone = phones[0] if phones else ""
        if not email and not phone:
            continue
        if name_score < 16 and (not role or _is_generic_business_email(email)):
            continue

        verification_status = (
            VerificationStatus.fully_verified.value
            if email and phone
            else VerificationStatus.email_verified.value
            if email
            else VerificationStatus.phone_verified.value
        )
        consent_status = _consent_status_for_email(email).value if email else ConsentStatus.unknown.value
        record = {
            "company": company,
            "contact_name": name,
            "role": role,
            "email": email,
            "phone": phone,
            "linkedin": "",
            "domain": domain,
            "industry": [],
            "snippet": block_text[:MAX_TEXT_LEN],
            "platform": Platform.public_web.value,
            "source_type": LeadSourceType.public_web.value,
            "source_label": "Public website crawl",
            "source_url": page_url,
            "consent_status": consent_status,
            "verification_status": verification_status,
        }
        key = "|".join(
            [
                name.lower(),
                role.lower(),
                email.lower(),
                phone,
                page_url.lower(),
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        records.append(record)

    return records


def _company_name(soup: BeautifulSoup, page_url: str) -> str:
    for selector, attr in (
        ("meta[property='og:site_name']", "content"),
        ("meta[name='application-name']", "content"),
        ("meta[name='twitter:title']", "content"),
    ):
        tag = soup.select_one(selector)
        if tag and tag.get(attr):
            return str(tag.get(attr)).strip()[:160]

    title = (soup.title.string if soup.title and soup.title.string else "").strip()
    if title:
        chosen = _best_title_segment(title)
        if chosen:
            return chosen[:160]

    host = _domain(page_url).replace("www.", "")
    return host.split(".", 1)[0].replace("-", " ").title()[:160]


def _best_title_segment(title: str) -> str:
    raw_parts = re.split(r"\s+[|\-–—]\s+|[|\-–—]", title)
    parts = [part.strip() for part in raw_parts if part.strip()]
    if not parts:
        return ""

    scored_parts: list[tuple[int, str]] = []
    for part in parts:
        lowered = part.lower()
        if lowered in GENERIC_TITLE_PARTS:
            score = 0
        else:
            score = len(part)
            if any(token in lowered for token in GENERIC_BUSINESS_TITLE_HINTS):
                score += 12
            if any(char.isdigit() for char in part):
                score -= 8
        scored_parts.append((score, part))

    best_score, best_part = max(scored_parts, key=lambda row: row[0])
    if best_score <= 0:
        return ""
    return best_part


def _page_snippet(soup: BeautifulSoup, page_text: str) -> str:
    description = soup.select_one("meta[name='description']")
    if description and description.get("content"):
        return str(description.get("content")).strip()[:MAX_TEXT_LEN]

    for selector in ("h1", "main p", "p"):
        node = soup.select_one(selector)
        if node:
            text = node.get_text(" ", strip=True)
            if text:
                return text[:MAX_TEXT_LEN]

    return page_text[:MAX_TEXT_LEN]


def _candidate_contact_blocks(soup: BeautifulSoup) -> list:
    blocks: list = []
    seen: set[int] = set()

    def add_block(node) -> None:  # noqa: ANN001
        current = node
        depth = 0
        while current is not None and depth < 5:
            if getattr(current, "name", None) in PERSON_CONTAINER_TAGS:
                text = current.get_text(" ", strip=True)
                if 20 <= len(text) <= 700:
                    identifier = id(current)
                    if identifier not in seen:
                        seen.add(identifier)
                        blocks.append(current)
                return
            current = getattr(current, "parent", None)
            depth += 1

    for anchor in soup.select("a[href^='mailto:'], a[href^='tel:']"):
        add_block(anchor)

    for node in soup.find_all(list(PERSON_CONTAINER_TAGS)):
        attrs = " ".join([*node.get("class", []), str(node.get("id") or "")]).lower()
        if any(hint in attrs for hint in PERSON_BLOCK_HINTS):
            add_block(node)

    return blocks[:80]


def _person_name_from_block(block, company: str) -> str:  # noqa: ANN001
    candidates: list[str] = []
    for selector in ("[itemprop='name']", "h1", "h2", "h3", "h4", "strong", "b", "[class*='name']"):
        for node in block.select(selector):
            text = node.get_text(" ", strip=True)
            if _looks_like_person_name(text, company):
                candidates.append(_clean_person_name(text))

    lines = [line.strip() for line in block.get_text("\n", strip=True).splitlines() if line.strip()]
    for line in lines[:8]:
        if _looks_like_person_name(line, company):
            candidates.append(_clean_person_name(line))

    if not candidates:
        return ""
    return max(candidates, key=lambda value: _person_name_score(value, company))


def _clean_person_name(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", (value or "").strip())
    cleaned = cleaned.strip(" |,:;-")
    return cleaned[:120]


def _looks_like_person_name(value: str, company: str) -> bool:
    cleaned = _clean_person_name(value)
    if not cleaned or len(cleaned) > 80 or "@" in cleaned or any(char.isdigit() for char in cleaned):
        return False
    raw_tokens = [token.strip() for token in cleaned.split() if token.strip()]
    normalized_tokens = [re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿ'’-]", "", token).strip(".'’-") for token in raw_tokens]
    tokens = [token.lower() for token in normalized_tokens if token]
    if len(tokens) < 2 or len(tokens) > 5:
        return False

    company_tokens = {token.lower() for token in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", company or "")}
    name_like = 0
    for raw_token, token in zip(raw_tokens, tokens):
        if token in PERSON_NAME_PREFIXES or token in PERSON_NAME_CONNECTORS:
            continue
        if token in PERSON_NAME_STOPWORDS:
            return False
        if token in company_tokens:
            return False
        if len(token) < 2:
            return False
        if raw_token[:1].islower():
            return False
        name_like += 1

    return name_like >= 2


def _person_name_score(value: str, company: str) -> int:
    tokens = [token for token in _clean_person_name(value).split() if token]
    company_tokens = {token.lower() for token in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", company or "")}
    score = 10
    if 2 <= len(tokens) <= 4:
        score += 8
    if any(token.lower() in PERSON_NAME_PREFIXES for token in tokens):
        score -= 2
    if any(token.lower() in company_tokens for token in tokens):
        score -= 10
    if any(token.isupper() for token in tokens):
        score += 1
    return score


def _person_role_from_text(text: str) -> str:
    lowered = re.sub(r"\s+", " ", (text or "").strip().lower())
    for needle, label in PERSON_ROLE_LABELS:
        if needle in lowered:
            return label
    return ""


def _best_person_email(emails: list[str]) -> str:
    if not emails:
        return ""
    ranked = sorted(emails, key=lambda email: (1 if _is_generic_business_email(email) else 0, email))
    return ranked[0]


def _emails_from_page(soup: BeautifulSoup, page_text: str) -> list[str]:
    emails: list[str] = []
    for anchor in soup.select("a[href^='mailto:']"):
        href = (anchor.get("href") or "").strip()
        email = _clean_email_candidate(href)
        if email:
            emails.append(email)

    for match in EMAIL_RE.findall(page_text):
        email = _clean_email_candidate(match)
        if email:
            emails.append(email)

    unique: list[str] = []
    seen: set[str] = set()
    for email in emails:
        if _ignore_email(email) or email in seen:
            continue
        seen.add(email)
        unique.append(email)

    unique.sort(key=lambda row: (0 if _is_generic_business_email(row) else 1, row))
    return unique[:5]


def _phones_from_text(page_text: str) -> list[str]:
    unique: list[tuple[int, str]] = []
    seen: set[str] = set()
    for match in PHONE_RE.findall(page_text):
        phone = _clean_phone_candidate(match)
        digits = re.sub(r"\D", "", phone)
        if (
            len(digits) < 7
            or len(digits) > 15
            or (not phone.startswith("+") and len(digits) < 10)
            or phone in seen
            or _looks_like_placeholder_phone(phone, digits)
        ):
            continue
        seen.add(phone)
        unique.append((_phone_rank(phone, digits), phone))
    unique.sort(key=lambda row: (-row[0], row[1]))
    return [phone for _, phone in unique[:3]]


def _clean_email_candidate(value: str) -> str:
    email = unquote((value or "").strip())
    email = email.replace("mailto:", "", 1).split("?", 1)[0].strip().lower()
    email = email.strip(".,;:<>[](){}\"'")
    if not email or " " in email:
        return ""

    match = EMAIL_RE.fullmatch(email)
    if match is None:
        return ""

    return match.group(1).lower()


def _clean_phone_candidate(value: str) -> str:
    phone = re.sub(r"(?i)\b(?:ext|extension|x)\b\.?\s*\d+\s*$", "", value or "")
    phone = re.sub(r"\s+", " ", phone).strip(" ,;./")
    return phone


def _looks_like_placeholder_phone(phone: str, digits: str) -> bool:
    if digits in PLACEHOLDER_PHONE_DIGITS:
        return True

    chunks = re.findall(r"\d+", phone)
    single_digit_chunks = sum(1 for chunk in chunks if len(chunk) == 1)
    if len(chunks) >= 6 and single_digit_chunks >= 6:
        return True

    return False


def _phone_rank(phone: str, digits: str) -> int:
    score = len(digits) * 10
    if phone.startswith("+"):
        score += 3
    if digits.startswith("0"):
        score += 1
    return score


def _ignore_email(email: str) -> bool:
    lowered = email.lower()
    blocked_domains = ("example.com", "example.org", "example.net", "wixpress.com", "sentry.io")
    return any(domain in lowered for domain in blocked_domains)


def _is_generic_business_email(email: str) -> bool:
    local = email.split("@", 1)[0].lower()
    return local in GENERIC_LOCAL_PARTS


def _consent_status_for_email(email: str) -> ConsentStatus:
    if _is_generic_business_email(email):
        return ConsentStatus.legitimate_interest
    return ConsentStatus.unknown


def _deduplicate_raw_results(records: list[dict]) -> list[dict]:
    unique: list[dict] = []
    seen: set[str] = set()
    for record in records:
        key = "|".join(
            [
                str(record.get("domain") or "").lower(),
                str(record.get("contact_name") or "").lower(),
                str(record.get("role") or "").lower(),
                str(record.get("email") or "").lower(),
                str(record.get("phone") or "").lower(),
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique
