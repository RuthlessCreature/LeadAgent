from __future__ import annotations

import os
import random
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse
from uuid import uuid4

import requests
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - optional dependency at runtime.
    PlaywrightError = Exception
    PlaywrightTimeoutError = Exception
    sync_playwright = None

from app.models import ICPDefinition, LeadCandidate, Platform, RawSearchResult
from app.services.text_utils import tokenize


SEARCH_MODE_ENV = "SEARCH_MODE"
SEARCH_MODE_LIVE = "live"
SEARCH_MODE_MOCK = "mock"
SEARCH_TARGET_ENV = "SEARCH_TARGET"
SEARCH_TARGET_PEOPLE = "people"
SEARCH_TARGET_COMPANY = "company"
SEARCH_DRIVER_ENV = "SEARCH_DRIVER"
SEARCH_DRIVER_PLAYWRIGHT = "playwright"
SEARCH_DRIVER_HTTP = "http"


def _int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


SEARCH_TIMEOUT = _int_env("SEARCH_TIMEOUT", default=8, minimum=2, maximum=60)
SEARCH_QUERY_VARIANTS = _int_env("SEARCH_QUERY_VARIANTS", default=2, minimum=1, maximum=6)
SEARCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


ROLE_HINTS = [
    "head of procurement",
    "procurement manager",
    "sourcing manager",
    "purchasing manager",
    "vp supply chain",
    "director procurement",
    "supply chain director",
    "business development manager",
]

NON_NAME_TOKENS = {
    "head",
    "procurement",
    "supply",
    "chain",
    "global",
    "director",
    "manager",
    "vp",
    "operations",
    "lead",
    "senior",
    "buyer",
}


@dataclass
class WebSearchResult:
    title: str
    snippet: str
    url: str


SEARCH_KB: dict[Platform, list[dict[str, str]]] = {
    Platform.linkedin: [
        {
            "company": "Nordic Freight Systems",
            "contact_name": "Emily Carter",
            "role": "Head of Procurement",
            "email": "emily@nordicfreight.com",
            "linkedin": "https://linkedin.com/in/emily-carter-logistics",
            "domain": "nordicfreight.com",
            "phone": "+1-415-555-0101",
            "snippet": "Hiring procurement analyst for supplier expansion in cross-border shipping.",
            "industry": "logistics",
            "source_url": "https://linkedin.com/company/nordic-freight",
        },
        {
            "company": "Atlas Commerce Cloud",
            "contact_name": "Nathan Hall",
            "role": "VP Growth",
            "email": "nathan@atlascommerce.io",
            "linkedin": "https://linkedin.com/in/nathanhallgrowth",
            "domain": "atlascommerce.io",
            "phone": "+1-206-555-0160",
            "snippet": "Looking for new automation tools to improve outbound lead workflows.",
            "industry": "ecommerce",
            "source_url": "https://linkedin.com/company/atlas-commerce-cloud",
        },
        {
            "company": "MediFlow Labs",
            "contact_name": "Sarah Lee",
            "role": "Business Development Director",
            "email": "sarah.lee@mediflowlabs.com",
            "linkedin": "https://linkedin.com/in/sarahlee-mediflow",
            "domain": "mediflowlabs.com",
            "phone": "+1-617-555-0134",
            "snippet": "Evaluating vendors for multilingual CRM outreach in medical device markets.",
            "industry": "healthcare",
            "source_url": "https://linkedin.com/company/mediflow-labs",
        },
    ],
    Platform.facebook: [
        {
            "company": "Global Seller Network",
            "contact_name": "Ivan Gomez",
            "role": "Community Admin",
            "email": "ivan@globalseller.net",
            "linkedin": "",
            "domain": "globalseller.net",
            "phone": "+34-91-555-0198",
            "snippet": "Group post: Looking for suppliers and B2B lead generation software.",
            "industry": "ecommerce",
            "source_url": "https://facebook.com/groups/global-seller-network",
        },
        {
            "company": "OEM Deals Hub",
            "contact_name": "Marta Novak",
            "role": "Marketplace Manager",
            "email": "marta@oemdealshub.com",
            "linkedin": "",
            "domain": "oemdealshub.com",
            "phone": "+48-22-555-0102",
            "snippet": "Marketplace sellers seeking better quote tracking and supplier discovery.",
            "industry": "manufacturing",
            "source_url": "https://facebook.com/oemdealshub",
        },
    ],
    Platform.tiktok: [
        {
            "company": "ScaleOps Studio",
            "contact_name": "Jasmine Park",
            "role": "Creator Partnerships",
            "email": "jasmine@scaleops.studio",
            "linkedin": "",
            "domain": "scaleops.studio",
            "phone": "",
            "snippet": "Creator business account discussing B2B automation and lead scoring stacks.",
            "industry": "saas",
            "source_url": "https://tiktok.com/@scaleopsstudio",
        },
        {
            "company": "CrossBorderBoost",
            "contact_name": "Leo Martin",
            "role": "Growth Lead",
            "email": "leo@crossborderboost.co",
            "linkedin": "",
            "domain": "crossborderboost.co",
            "phone": "",
            "snippet": "Helping exporters identify qualified distributors and wholesale buyers.",
            "industry": "logistics",
            "source_url": "https://tiktok.com/@crossborderboost",
        },
    ],
    Platform.youtube: [
        {
            "company": "Revenue Systems Weekly",
            "contact_name": "Olivia Chen",
            "role": "Channel Host",
            "email": "olivia@revenuesystemsweekly.com",
            "linkedin": "https://linkedin.com/in/olivia-chen-rsw",
            "domain": "revenuesystemsweekly.com",
            "phone": "",
            "snippet": "Recent video: Comparing Apollo and CRM outreach tools for export SaaS teams.",
            "industry": "saas",
            "source_url": "https://youtube.com/@RevenueSystemsWeekly",
        },
        {
            "company": "B2B Ops Blueprint",
            "contact_name": "Daniel Ortiz",
            "role": "Operations Consultant",
            "email": "daniel@b2bopsblueprint.com",
            "linkedin": "https://linkedin.com/in/daniel-ortiz-ops",
            "domain": "b2bopsblueprint.com",
            "phone": "",
            "snippet": "Interview with procurement teams looking for supplier databases and automation.",
            "industry": "manufacturing",
            "source_url": "https://youtube.com/@B2BOpsBlueprint",
        },
    ],
    Platform.google: [
        {
            "company": "BluePeak Components",
            "contact_name": "Grace Kim",
            "role": "Purchasing Manager",
            "email": "grace.kim@bluepeakcomponents.com",
            "linkedin": "https://linkedin.com/in/gracekim-bluepeak",
            "domain": "bluepeakcomponents.com",
            "phone": "+1-303-555-0186",
            "snippet": "Request for quotation posted for industrial IoT devices and supplier audits.",
            "industry": "manufacturing",
            "source_url": "https://bluepeakcomponents.com/rfq",
        },
        {
            "company": "EuroTrade Cloud",
            "contact_name": "Noah Wright",
            "role": "Sales Operations Manager",
            "email": "noah@eurotradecloud.com",
            "linkedin": "https://linkedin.com/in/noahwright-eurotrade",
            "domain": "eurotradecloud.com",
            "phone": "+49-30-555-0155",
            "snippet": "Announced need for multilingual outbound campaigns in EU and LATAM.",
            "industry": "saas",
            "source_url": "https://eurotradecloud.com/blog/outbound-plan",
        },
    ],
    Platform.b2b_db: [
        {
            "company": "Summit Industrial Tech",
            "contact_name": "Priya Das",
            "role": "Director of Strategic Sourcing",
            "email": "priya.das@summitindtech.com",
            "linkedin": "https://linkedin.com/in/priyadas-sourcing",
            "domain": "summitindtech.com",
            "phone": "+1-212-555-0124",
            "snippet": "Intent signal: comparing supplier enrichment platforms this quarter.",
            "industry": "manufacturing",
            "source_url": "https://example-db.local/summit-industrial-tech",
        },
        {
            "company": "Helio Payments",
            "contact_name": "Victor Stone",
            "role": "Head of Partnerships",
            "email": "victor@heliopayments.com",
            "linkedin": "https://linkedin.com/in/victorstone-payments",
            "domain": "heliopayments.com",
            "phone": "+1-646-555-0170",
            "snippet": "Strong buying intent for AI-driven lead qualification and CRM sync.",
            "industry": "finance",
            "source_url": "https://example-db.local/helio-payments",
        },
    ],
}


def build_platform_query(query: str, icp: ICPDefinition, platform: Platform) -> str:
    industry_part = " ".join(icp.industry[:2]) if icp.industry else ""
    role_part = " ".join(icp.role_titles[:2]) if icp.role_titles else ""
    if _search_target() == SEARCH_TARGET_PEOPLE:
        people_prefix = {
            Platform.linkedin: "site:linkedin.com/in",
            Platform.facebook: "site:facebook.com/people OR site:facebook.com/profile.php",
            Platform.tiktok: "site:tiktok.com/@",
            Platform.youtube: "site:youtube.com/@ OR site:youtube.com/channel",
            Platform.google: "site:linkedin.com/in",
            Platform.b2b_db: "site:apollo.io/people OR site:zoominfo.com/p",
        }[platform]
        people_terms = "contact profile"
        return " ".join(
            part for part in [people_prefix, query, industry_part, role_part, people_terms] if part
        ).strip()

    platform_prefix = {
        Platform.linkedin: "site:linkedin.com",
        Platform.facebook: "site:facebook.com",
        Platform.tiktok: "site:tiktok.com",
        Platform.youtube: "site:youtube.com",
        Platform.google: "",
        Platform.b2b_db: "(site:apollo.io OR site:zoominfo.com OR site:crunchbase.com)",
    }[platform]
    return " ".join(part for part in [platform_prefix, query, industry_part, role_part] if part).strip()


def _search_mode() -> str:
    return os.getenv(SEARCH_MODE_ENV, SEARCH_MODE_LIVE).strip().lower()


def _search_driver() -> str:
    value = os.getenv(SEARCH_DRIVER_ENV, SEARCH_DRIVER_PLAYWRIGHT).strip().lower()
    if value in {SEARCH_DRIVER_PLAYWRIGHT, SEARCH_DRIVER_HTTP}:
        return value
    return SEARCH_DRIVER_PLAYWRIGHT


def _search_target() -> str:
    value = os.getenv(SEARCH_TARGET_ENV, SEARCH_TARGET_PEOPLE).strip().lower()
    if value in {SEARCH_TARGET_PEOPLE, SEARCH_TARGET_COMPANY}:
        return value
    return SEARCH_TARGET_PEOPLE


def _primary_role_hint(icp: ICPDefinition) -> str:
    if icp.role_titles:
        return icp.role_titles[0]
    return ROLE_HINTS[0]


def _candidate_live_queries(query: str, icp: ICPDefinition, platform: Platform) -> list[str]:
    full = build_platform_query(query=query, icp=icp, platform=platform)
    industry = " ".join(icp.industry[:1]).strip()
    role = _primary_role_hint(icp).strip()
    simple = query.strip()
    target = _search_target()

    if platform == Platform.google and target == SEARCH_TARGET_PEOPLE:
        candidates = [
            f'site:linkedin.com/in "{role}" {industry} {simple}'.strip(),
            f'site:linkedin.com/in "{role}" {simple}'.strip(),
            f'"{role}" "{industry}" contact'.strip(),
        ]
        return [item for item in candidates if item]

    if platform == Platform.google:
        candidates = [full, f"{simple} {industry}".strip(), simple]
        return [item for item in candidates if item]

    site_map = {
        Platform.linkedin: "site:linkedin.com/in",
        Platform.facebook: "site:facebook.com/people OR site:facebook.com/profile.php",
        Platform.tiktok: "site:tiktok.com/@",
        Platform.youtube: "site:youtube.com/@ OR site:youtube.com/channel",
        Platform.b2b_db: "site:apollo.io OR site:zoominfo.com OR site:crunchbase.com",
        Platform.google: "",
    }
    site = site_map[platform]

    if target == SEARCH_TARGET_PEOPLE:
        candidates = [
            f'{site} "{role}" "{industry}"'.strip(),
            f"{site} {role}".strip(),
            f"{site} {simple} {role}".strip(),
            f"{site} buyer".strip(),
        ]
        if platform == Platform.linkedin:
            candidates.append('site:linkedin.com/in "procurement manager"')
        if platform == Platform.b2b_db:
            candidates.append(f"{site} people {role}".strip())
    else:
        candidates = [
            full,
            f"{site} {simple}".strip(),
            f"{site} {industry}".strip(),
            f"{site} {role}".strip(),
        ]
        if platform == Platform.linkedin:
            candidates.append(f"{site} procurement")
        if platform == Platform.b2b_db:
            candidates.append(f"{site} b2b company profile")

    deduped: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        cleaned = " ".join(item.split())
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)
    return deduped[:SEARCH_QUERY_VARIANTS]


def _decode_duckduckgo_url(raw_url: str) -> str:
    if not raw_url:
        return ""
    if raw_url.startswith("//"):
        return "https:" + raw_url
    if raw_url.startswith("/l/?"):
        raw_url = "https://duckduckgo.com" + raw_url
    if "duckduckgo.com/l/?" in raw_url:
        parsed = urlparse(raw_url)
        q = parse_qs(parsed.query)
        target = q.get("uddg", [""])[0]
        if target:
            return unquote(target)
    return raw_url


def _extract_domain(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def _platform_domain_allowlist(platform: Platform) -> list[str]:
    return {
        Platform.linkedin: ["linkedin.com"],
        Platform.facebook: ["facebook.com"],
        Platform.tiktok: ["tiktok.com"],
        Platform.youtube: ["youtube.com", "youtu.be"],
        Platform.google: [],
        Platform.b2b_db: ["apollo.io", "zoominfo.com", "crunchbase.com", "pitchbook.com", "owler.com"],
    }[platform]


def _url_allowed_for_platform(url: str, platform: Platform) -> bool:
    allowlist = _platform_domain_allowlist(platform)
    if not allowlist:
        return True
    lowered = url.lower()
    return any(domain in lowered for domain in allowlist)


def _is_person_url(url: str, platform: Platform) -> bool:
    lowered = (url or "").lower()
    if not lowered:
        return False

    if platform == Platform.linkedin:
        return "/in/" in lowered or "/pub/" in lowered
    if platform == Platform.facebook:
        parsed = urlparse(lowered)
        path = (parsed.path or "").strip("/")
        if path.startswith("people/"):
            segments = [segment for segment in path.split("/") if segment]
            if len(segments) < 2:
                return False
            slug = segments[1].strip()
            if slug in {"", "_"}:
                return False
            return bool(re.search(r"[a-z]", slug))
        return "profile.php" in lowered
    if platform == Platform.tiktok:
        if "tiktok.com/@" not in lowered:
            return False
        if "/video/" in lowered:
            return False
        return bool(re.search(r"tiktok\.com/@[^/]+/?$", lowered))
    if platform == Platform.youtube:
        if "/watch" in lowered:
            return False
        parsed = urlparse(lowered)
        path = (parsed.path or "").strip("/")
        if path.startswith("@"):
            handle = path[1:].split("/")[0]
            if not handle or "%" in handle or "?" in handle:
                return False
            return bool(re.match(r"^[a-z0-9._-]{2,}$", handle))
        if path.startswith("channel/"):
            channel_id = path.split("/", 1)[1].split("/")[0]
            return bool(re.match(r"^[a-z0-9_-]{10,}$", channel_id))
        if path.startswith("user/"):
            user = path.split("/", 1)[1].split("/")[0]
            return bool(re.match(r"^[a-z0-9._-]{3,}$", user))
        return False
    if platform == Platform.b2b_db:
        return any(
            token in lowered
            for token in ["/people/", "/person/", "/contact/", "zoominfo.com/p/", "apollo.io/people"]
        )
    if platform == Platform.google:
        return any(
            token in lowered
            for token in [
                "linkedin.com/in/",
                "linkedin.com/pub/",
                "zoominfo.com/p/",
                "tiktok.com/@",
                "youtube.com/@",
                "facebook.com/people/",
            ]
        )
    return False


def _title_has_person_name(title: str) -> bool:
    return bool(re.search(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", title))


def _person_confidence(row: WebSearchResult, platform: Platform) -> int:
    score = 0
    if _is_person_url(row.url, platform):
        score += 4
    if _title_has_person_name(row.title):
        score += 2

    text = f"{row.title} {row.snippet}".lower()
    if any(keyword in text for keyword in ROLE_HINTS):
        score += 2
    if any(keyword in text for keyword in ["procurement", "sourcing", "purchasing", "supply chain"]):
        score += 1
    if "@" in row.url and platform in {Platform.youtube, Platform.tiktok}:
        score += 1
    return score


def _looks_like_people_result(row: WebSearchResult, platform: Platform) -> bool:
    confidence = _person_confidence(row, platform)
    if platform in {Platform.linkedin, Platform.tiktok, Platform.youtube, Platform.facebook}:
        return confidence >= 4
    return confidence >= 3


def _infer_company(title: str, domain: str) -> str:
    clean_title = title.strip()
    for splitter in [" | ", " - ", " — ", ": "]:
        if splitter in clean_title:
            left = clean_title.split(splitter)[0].strip()
            if left:
                return left[:120]
    if clean_title:
        return clean_title[:120]
    if domain:
        return domain.split(".")[0].replace("-", " ").title()
    return "Unknown Company"


def _infer_role(title: str, snippet: str) -> str:
    text = f"{title} {snippet}".lower()
    role_keywords = {
        "head of procurement": ["head of procurement", "procurement head"],
        "purchasing manager": ["purchasing manager"],
        "vp growth": ["vp growth", "vice president growth"],
        "sales operations manager": ["sales operations manager", "sales ops manager"],
        "director": ["director"],
        "business development": ["business development"],
    }
    for role, keywords in role_keywords.items():
        if any(keyword in text for keyword in keywords):
            return role.title()
    return ""


def _infer_contact_name(title: str) -> str:
    def valid_name(value: str) -> bool:
        words = value.split()
        if len(words) < 2:
            return False
        lowered = [word.lower() for word in words[:2]]
        if any(word in NON_NAME_TOKENS for word in lowered):
            return False
        return True

    parts = [part.strip() for part in re.split(r"[|\-—:]", title) if part.strip()]
    for part in parts[:2]:
        if re.match(r"^[A-Z][a-z]+ [A-Z][a-z]+$", part) and valid_name(part):
            return part
    match = re.search(r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b", title)
    if match and valid_name(match.group(1)):
        return match.group(1)
    return ""


def _infer_contact_from_url(url: str, platform: Platform) -> str:
    parsed = urlparse(url)
    path = (parsed.path or "").strip("/")
    if not path:
        return ""

    if platform == Platform.linkedin:
        if path.startswith("in/"):
            slug = path.split("/", 1)[1]
        elif path.startswith("pub/"):
            slug = path.split("/", 1)[1]
        else:
            return ""
        slug = slug.split("/")[0]
        parts = [part for part in re.split(r"[-_]", slug) if part and not part.isdigit()]
        if len(parts) >= 2:
            return f"{parts[0].title()} {parts[1].title()}"
        if parts:
            return parts[0].title()
        return ""

    if platform == Platform.tiktok:
        at_index = path.find("@")
        if at_index >= 0:
            handle = path[at_index + 1 :].split("/")[0]
            return handle
        return ""

    if platform == Platform.youtube:
        if path.startswith("@"):
            handle = unquote(path[1:].split("/")[0])
            if not handle or "%" in handle or "?" in handle:
                return ""
            return handle
        segments = [segment for segment in path.split("/") if segment]
        if segments:
            return segments[-1]
        return ""

    if platform == Platform.facebook:
        if path.startswith("people/"):
            segments = [segment for segment in path.split("/") if segment]
            if len(segments) >= 2:
                name_parts = [p for p in segments[1].split("-") if p and not p.isdigit()]
                name_parts = [p for p in name_parts if re.match(r"^[A-Za-z][A-Za-z']*$", p)]
                if len(name_parts) >= 2:
                    return f"{name_parts[0].title()} {name_parts[1].title()}"
                return " ".join(part.title() for part in name_parts[:2])
        return ""

    return ""


def _detect_source_platform_from_url(url: str) -> Platform | None:
    lowered = (url or "").lower()
    if "linkedin.com" in lowered:
        return Platform.linkedin
    if "facebook.com" in lowered:
        return Platform.facebook
    if "tiktok.com" in lowered:
        return Platform.tiktok
    if "youtube.com" in lowered or "youtu.be" in lowered:
        return Platform.youtube
    if any(token in lowered for token in ["apollo.io", "zoominfo.com", "crunchbase.com"]):
        return Platform.b2b_db
    return None


def _infer_industry(title: str, snippet: str) -> str:
    text = f"{title} {snippet}".lower()
    hints = {
        "manufacturing": ["manufacturing", "factory", "industrial", "components", "oem"],
        "logistics": ["logistics", "shipping", "freight", "warehouse"],
        "saas": ["saas", "software", "crm", "automation", "platform"],
        "ecommerce": ["ecommerce", "marketplace", "seller", "retail", "shop"],
        "finance": ["fintech", "payment", "banking", "finance"],
        "healthcare": ["medical", "healthcare", "pharma", "hospital"],
    }
    for industry, keywords in hints.items():
        if any(keyword in text for keyword in keywords):
            return industry
    return ""


def _extract_email(text: str) -> str:
    match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return match.group(0) if match else ""


def _extract_phone(text: str) -> str:
    match = re.search(r"\+?\d[\d\s().-]{7,}\d", text)
    return match.group(0).strip() if match else ""


def _parse_duckduckgo_results(html: str, max_results: int) -> list[WebSearchResult]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[WebSearchResult] = []
    for block in soup.select("div.result"):
        title_tag = block.select_one("a.result__a")
        if not title_tag:
            continue

        raw_href = title_tag.get("href", "")
        url = _decode_duckduckgo_url(raw_href)
        title = title_tag.get_text(" ", strip=True)

        snippet_tag = block.select_one(".result__snippet")
        snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""

        if not url or not title:
            continue
        rows.append(WebSearchResult(title=title, snippet=snippet, url=url))
        if len(rows) >= max_results:
            break

    return rows


def _search_duckduckgo(query: str, max_results: int) -> list[WebSearchResult]:
    try:
        response = requests.get(
            "https://duckduckgo.com/html/",
            params={"q": query, "kl": "us-en"},
            headers=SEARCH_HEADERS,
            timeout=SEARCH_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException:
        return []
    return _parse_duckduckgo_results(response.text, max_results=max_results)


def _search_bing(query: str, max_results: int) -> list[WebSearchResult]:
    try:
        response = requests.get(
            "https://www.bing.com/search",
            params={"q": query, "count": max_results},
            headers=SEARCH_HEADERS,
            timeout=SEARCH_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    rows: list[WebSearchResult] = []
    for block in soup.select("li.b_algo"):
        title_tag = block.select_one("h2 a")
        if not title_tag:
            continue
        title = title_tag.get_text(" ", strip=True)
        url = title_tag.get("href", "")
        snippet_tag = block.select_one(".b_caption p")
        snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""
        if not url or not title:
            continue
        rows.append(WebSearchResult(title=title, snippet=snippet, url=url))
        if len(rows) >= max_results:
            break
    return rows


def _decode_yahoo_redirect(url: str) -> str:
    if "/RU=" not in url:
        return url
    match = re.search(r"/RU=([^/]+)/", url)
    if not match:
        return url
    decoded = unquote(match.group(1))
    return decoded if decoded.startswith("http") else url


def _clean_result_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    if "›" in title:
        segments = [segment.strip() for segment in title.split("›") if segment.strip()]
        if segments:
            title = segments[-1]
    return title


def _search_yahoo(query: str, max_results: int) -> list[WebSearchResult]:
    try:
        response = requests.get(
            "https://search.yahoo.com/search",
            params={"p": query},
            headers=SEARCH_HEADERS,
            timeout=SEARCH_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    rows: list[WebSearchResult] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a"):
        anchor_classes = anchor.get("class", [])
        if "d-ib" not in anchor_classes:
            continue
        comp_title_parent = anchor.find_parent("div", class_=lambda c: c and "compTitle" in c)
        if comp_title_parent is None:
            continue

        href = anchor.get("href", "").strip()
        if not href:
            continue
        target_url = _decode_yahoo_redirect(href)
        title = _clean_result_title(anchor.get_text(" ", strip=True))
        if not _is_useful_result(target_url, title):
            continue
        if target_url in seen:
            continue

        parent = anchor.find_parent("div", class_=lambda c: c and "algo-sr" in c)
        snippet = ""
        if parent:
            text = parent.get_text(" ", strip=True)
            snippet = re.sub(r"\s+", " ", text).strip()
            snippet = snippet.replace(title, "", 1).strip()
        rows.append(WebSearchResult(title=title[:140], snippet=snippet[:240], url=target_url))
        seen.add(target_url)
        if len(rows) >= max_results:
            break

    return rows


def _clean_markdown_title(title: str) -> str:
    title = title.replace("###", " ")
    title = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def _is_useful_result(url: str, title: str) -> bool:
    if not url or not title:
        return False
    lowered_url = url.lower()
    if not lowered_url.startswith("http://") and not lowered_url.startswith("https://"):
        return False

    blocked_domains = [
        "google.com/search",
        "google.com/webhp",
        "google.com/policies",
        "support.google.com",
        "accounts.google.com",
        "policies.google.com",
        "maps.google.com",
        "google.com/aclk",
        "googleadservices.com",
        "gstatic.com",
        "googleusercontent.com",
        "encrypted-tbn0.gstatic.com",
        "search.yahoo.com/search",
        "guce.yahoo.com",
        "advertising.yahoo.com",
        "yahoo.uservoice.com",
        "bing.com/search",
        "duckduckgo.com/",
    ]
    if any(blocked in lowered_url for blocked in blocked_domains):
        return False
    domain = _extract_domain(url)
    if domain.endswith("yahoo.com"):
        return False
    if domain in {"google.com", "bing.com", "duckduckgo.com"}:
        return False
    if domain.endswith(".google.com") or domain.endswith(".bing.com"):
        return False
    lowered_title = title.lower()
    if lowered_title.startswith("image "):
        return False
    if "skip to main content" in lowered_title:
        return False
    if lowered_title in {"read more", "more", "youtube", "linkedin", "facebook"}:
        return False
    if _search_target() == SEARCH_TARGET_PEOPLE:
        lowered_url = url.lower()
        if any(token in lowered_url for token in ["/blog/", "/news/", "/article/", "/articles/", "/watch?"]):
            return False
        if any(token in lowered_title for token in ["how to", "top 10", "best ", "review", "software tools"]):
            return False
    return True


def _extract_snippet(lines: list[str], start_index: int) -> str:
    snippet_parts: list[str] = []
    for idx in range(start_index + 1, min(start_index + 5, len(lines))):
        line = lines[idx].strip()
        if not line:
            continue
        if line.startswith("[") or line.startswith("*") or line.endswith("==="):
            continue
        if line.startswith("http://") or line.startswith("https://"):
            continue
        cleaned = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", line).strip()
        if not cleaned:
            continue
        snippet_parts.append(cleaned)
        if len(" ".join(snippet_parts)) >= 180:
            break
    return " ".join(snippet_parts)[:240]


def _search_google_via_rjina(query: str, max_results: int) -> list[WebSearchResult]:
    url = f"https://r.jina.ai/http://www.google.com/search?q={quote_plus(query)}"
    try:
        response = requests.get(url, headers=SEARCH_HEADERS, timeout=SEARCH_TIMEOUT + 4)
        response.raise_for_status()
    except requests.RequestException:
        return []

    lines = response.text.splitlines()
    rows: list[WebSearchResult] = []
    seen_urls: set[str] = set()
    link_pattern = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
    heading_pattern = re.compile(r"\[###\s*([^\]]+)\]\((https?://[^)\s]+)\)")

    def add_match(raw_title: str, raw_url: str, line_index: int) -> None:
        title = _clean_markdown_title(raw_title)
        url = raw_url.strip()

        if not _is_useful_result(url, title):
            return
        if "adurl=" in url.lower():
            return
        if url in seen_urls:
            return

        snippet = _extract_snippet(lines, line_index)
        rows.append(WebSearchResult(title=title, snippet=snippet, url=url))
        seen_urls.add(url)

    # Pass 1: prioritize Google result headings.
    for index, line in enumerate(lines):
        matches = heading_pattern.findall(line)
        for raw_title, raw_url in matches:
            add_match(raw_title, raw_url, index)
            if len(rows) >= max_results:
                return rows

    # Pass 2: fall back to generic markdown links.
    for index, line in enumerate(lines):
        matches = link_pattern.findall(line)
        if not matches:
            continue

        for raw_title, raw_url in matches:
            add_match(raw_title, raw_url, index)

            if len(rows) >= max_results:
                return rows

    return rows


def _normalize_result_url(raw_url: str, base_url: str = "") -> str:
    if not raw_url:
        return ""
    url = raw_url.strip()
    if url.startswith("/"):
        url = urljoin(base_url, url)

    lowered = url.lower()
    if lowered.startswith("https://duckduckgo.com/l/?") or lowered.startswith("http://duckduckgo.com/l/?"):
        return _decode_duckduckgo_url(url)
    if lowered.startswith("/l/?"):
        return _decode_duckduckgo_url(urljoin("https://duckduckgo.com", lowered))

    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    # Google redirect result URLs.
    if "google." in parsed.netloc and parsed.path == "/url":
        candidate = query.get("q", [""])[0] or query.get("url", [""])[0]
        if candidate:
            return unquote(candidate)

    # Yahoo redirect URLs.
    if "r.search.yahoo.com" in parsed.netloc and "/RU=" in parsed.path:
        return _decode_yahoo_redirect(url)

    return url


def _extract_playwright_rows(page, max_results: int) -> list[dict]:
    script = """
    (limit) => {
      const blocks = [];
      const addBlocks = (selector) => {
        document.querySelectorAll(selector).forEach((el) => blocks.push(el));
      };
      addBlocks('li.b_algo');
      addBlocks('div#search .g');
      addBlocks('article[data-testid="result"]');
      addBlocks('div.result');
      addBlocks('div[data-testid="result"]');
      addBlocks('ytd-video-renderer');
      if (!blocks.length) {
        document.querySelectorAll('a[href]').forEach((el) => blocks.push(el));
      }

      const rows = [];
      const seen = new Set();
      for (const block of blocks) {
        const anchor = block.matches('a[href]')
          ? block
          : block.querySelector('h3 a, h2 a, a.result__a, a[data-testid="result-title-a"], a[href]');
        if (!anchor) continue;

        const href = anchor.href || anchor.getAttribute('href') || '';
        if (!href) continue;

        const titleNode = block.querySelector('h3, h2') || anchor;
        let title = (titleNode.innerText || titleNode.textContent || '').trim();
        if (!title) {
          title = (anchor.innerText || anchor.textContent || '').trim();
        }
        if (!title) continue;

        const snippetNode =
          block.querySelector('.VwiC3b, .b_caption p, .result__snippet, [data-result="snippet"], p');
        let snippet = '';
        if (snippetNode) {
          snippet = (snippetNode.innerText || snippetNode.textContent || '').trim();
        }

        const key = `${href}|${title}`;
        if (seen.has(key)) continue;
        seen.add(key);
        rows.push({ title, snippet, url: href });
        if (rows.length >= limit * 3) break;
      }
      return rows;
    }
    """
    return page.evaluate(script, max_results)


def _extract_playwright_yahoo_rows(page, max_results: int) -> list[dict]:
    script = """
    (limit) => {
      const rows = [];
      const seen = new Set();
      const anchors = document.querySelectorAll('div.compTitle a.d-ib[href]');
      for (const a of anchors) {
        const href = a.href || a.getAttribute('href') || '';
        const title = (a.innerText || a.textContent || '').trim();
        if (!href || !title) continue;

        const container = a.closest('div.algo-sr') || a.closest('div.dd');
        let snippet = '';
        if (container) {
          const textEl = container.querySelector('p, div.compText');
          if (textEl) {
            snippet = (textEl.innerText || textEl.textContent || '').trim();
          }
        }

        const key = `${href}|${title}`;
        if (seen.has(key)) continue;
        seen.add(key);
        rows.push({ title, snippet, url: href });
        if (rows.length >= limit) break;
      }
      return rows;
    }
    """
    return page.evaluate(script, max_results)


def _extract_playwright_bing_rows(page, max_results: int) -> list[dict]:
    script = """
    (limit) => {
      const rows = [];
      const seen = new Set();
      const blocks = document.querySelectorAll('li.b_algo');
      for (const block of blocks) {
        const a = block.querySelector('h2 a[href]');
        if (!a) continue;
        const href = a.href || a.getAttribute('href') || '';
        const title = (a.innerText || a.textContent || '').trim();
        if (!href || !title) continue;
        const snippetEl = block.querySelector('.b_caption p');
        const snippet = snippetEl ? (snippetEl.innerText || snippetEl.textContent || '').trim() : '';
        const key = `${href}|${title}`;
        if (seen.has(key)) continue;
        seen.add(key);
        rows.push({ title, snippet, url: href });
        if (rows.length >= limit) break;
      }
      return rows;
    }
    """
    return page.evaluate(script, max_results)


def _search_with_playwright(query: str, max_results: int) -> list[WebSearchResult]:
    if sync_playwright is None:
        return []

    providers = [
        ("yahoo", f"https://search.yahoo.com/search?p={quote_plus(query)}"),
        ("bing", f"https://www.bing.com/search?q={quote_plus(query)}&count={max_results * 3}"),
        ("google", f"https://www.google.com/search?q={quote_plus(query)}&num={max_results * 3}"),
        ("duckduckgo", f"https://duckduckgo.com/?q={quote_plus(query)}"),
    ]

    merged: list[WebSearchResult] = []
    seen_urls: set[str] = set()

    def launch_browser(pw):
        launch_attempts = [
            {
                "headless": True,
                "channel": "msedge",
                "args": ["--disable-blink-features=AutomationControlled", "--disable-gpu"],
            },
            {
                "headless": True,
                "channel": "chrome",
                "args": ["--disable-blink-features=AutomationControlled", "--disable-gpu"],
            },
            {
                "headless": True,
                "args": ["--disable-blink-features=AutomationControlled", "--disable-gpu"],
            },
        ]
        for options in launch_attempts:
            try:
                return pw.chromium.launch(**options)
            except Exception:
                continue
        return None

    try:
        with sync_playwright() as pw:
            browser = launch_browser(pw)
            if browser is None:
                return []
            context = browser.new_context(
                user_agent=SEARCH_HEADERS["User-Agent"],
                viewport={"width": 1366, "height": 900},
                locale="en-US",
            )
            page = context.new_page()

            for provider_name, provider_url in providers:
                try:
                    page.goto(
                        provider_url,
                        wait_until="domcontentloaded",
                        timeout=SEARCH_TIMEOUT * 1000,
                    )
                    page.wait_for_timeout(1200)
                    if provider_name == "yahoo":
                        raw_rows = _extract_playwright_yahoo_rows(page, max_results=max_results * 2)
                    elif provider_name == "bing":
                        raw_rows = _extract_playwright_bing_rows(page, max_results=max_results * 2)
                    else:
                        raw_rows = _extract_playwright_rows(page, max_results=max_results)
                except (PlaywrightTimeoutError, PlaywrightError, Exception):
                    continue

                for raw in raw_rows:
                    title = (raw.get("title") or "").strip()
                    snippet = (raw.get("snippet") or "").strip()
                    raw_url = (raw.get("url") or "").strip()
                    url = _normalize_result_url(raw_url, base_url=provider_url)
                    if not _is_useful_result(url, title):
                        continue
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    merged.append(WebSearchResult(title=title, snippet=snippet, url=url))
                    if len(merged) >= max_results:
                        context.close()
                        browser.close()
                        return merged[:max_results]

            context.close()
            browser.close()
    except Exception:
        return []

    return merged[:max_results]


def _run_live_search(query: str, max_results: int) -> list[WebSearchResult]:
    rows: list[WebSearchResult] = []

    if _search_driver() == SEARCH_DRIVER_PLAYWRIGHT:
        rows = _search_with_playwright(query, max_results=max_results)
        if len(rows) >= max_results:
            return rows[:max_results]

    http_rows = _search_google_via_rjina(query, max_results=max_results)
    if http_rows:
        seen = {row.url for row in rows}
        for row in http_rows:
            if row.url in seen:
                continue
            rows.append(row)
            seen.add(row.url)
            if len(rows) >= max_results:
                return rows[:max_results]

    if len(rows) >= max_results:
        return rows[:max_results]

    yahoo_rows = _search_yahoo(query, max_results=max_results)
    if yahoo_rows:
        seen = {row.url for row in rows}
        for row in yahoo_rows:
            if row.url in seen:
                continue
            rows.append(row)
            seen.add(row.url)
            if len(rows) >= max_results:
                return rows[:max_results]

    extra = _search_duckduckgo(query, max_results=max_results)
    if extra:
        seen = {row.url for row in rows}
        for row in extra:
            if row.url in seen:
                continue
            rows.append(row)
            seen.add(row.url)
            if len(rows) >= max_results:
                return rows[:max_results]

    if len(rows) >= max_results:
        return rows[:max_results]

    fallback = _search_bing(query, max_results=max_results)
    merged: list[WebSearchResult] = []
    seen: set[str] = set()
    for row in rows + fallback:
        key = row.url
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)
        if len(merged) >= max_results:
            break
    return merged


def _build_payload_from_web_result(row: WebSearchResult, platform: Platform) -> dict[str, str]:
    combined = f"{row.title} {row.snippet}"
    domain = _extract_domain(row.url)
    company = _infer_company(row.title, domain)
    contact = _infer_contact_name(row.title)
    if not contact:
        contact = _infer_contact_from_url(row.url, platform)
    if not contact:
        inferred_platform = _detect_source_platform_from_url(row.url)
        if inferred_platform:
            contact = _infer_contact_from_url(row.url, inferred_platform)
    role = _infer_role(row.title, row.snippet)
    email = _extract_email(combined)
    phone = _extract_phone(combined)
    industry = _infer_industry(row.title, row.snippet)

    return {
        "company": company,
        "contact_name": contact,
        "role": role,
        "email": email,
        "linkedin": row.url if platform == Platform.linkedin else "",
        "domain": domain,
        "phone": phone,
        "snippet": row.snippet,
        "industry": industry,
        "source_url": row.url,
    }


def _search_mock(
    query: str, icp: ICPDefinition, platform: Platform, limit_per_platform: int
) -> list[RawSearchResult]:
    query_tokens = set(tokenize(query))
    icp_tokens = set(icp.industry + icp.role_titles + icp.technology_stack)
    candidates = SEARCH_KB.get(platform, [])

    scored: list[tuple[float, dict[str, str]]] = []
    for candidate in candidates:
        text_blob = " ".join(
            [
                candidate.get("company", ""),
                candidate.get("contact_name", ""),
                candidate.get("role", ""),
                candidate.get("snippet", ""),
                candidate.get("industry", ""),
            ]
        ).lower()
        token_set = set(tokenize(text_blob))
        overlap = len(query_tokens.intersection(token_set)) + len(icp_tokens.intersection(token_set))
        random_boost = random.random() * 0.2
        scored.append((overlap + random_boost, candidate))

    scored.sort(key=lambda row: row[0], reverse=True)
    if not scored:
        return []

    return [
        RawSearchResult(
            platform=platform,
            title=f"{item['company']} - {item['role']}",
            snippet=item["snippet"],
            payload=item,
        )
        for _, item in scored[:limit_per_platform]
    ]


def search_platform(
    query: str, icp: ICPDefinition, platform: Platform, limit_per_platform: int
) -> list[RawSearchResult]:
    if _search_mode() == SEARCH_MODE_MOCK:
        return _search_mock(query, icp, platform, limit_per_platform)

    target = _search_target()
    collected: list[WebSearchResult] = []
    seen_urls: set[str] = set()
    for candidate_query in _candidate_live_queries(query=query, icp=icp, platform=platform):
        rows = _run_live_search(candidate_query, max_results=limit_per_platform)
        rows = [row for row in rows if _url_allowed_for_platform(row.url, platform)]
        if target == SEARCH_TARGET_PEOPLE:
            rows = [row for row in rows if _looks_like_people_result(row, platform)]
            rows.sort(key=lambda row: _person_confidence(row, platform), reverse=True)
        for row in rows:
            if row.url in seen_urls:
                continue
            collected.append(row)
            seen_urls.add(row.url)
            if len(collected) >= limit_per_platform:
                break
        if len(collected) >= limit_per_platform:
            break

    raw_results: list[RawSearchResult] = []
    for row in collected:
        payload = _build_payload_from_web_result(row, platform=platform)
        if target == SEARCH_TARGET_PEOPLE and not payload.get("contact_name"):
            continue
        raw_results.append(
            RawSearchResult(
                platform=platform,
                title=row.title,
                snippet=row.snippet,
                payload=payload,
            )
        )
        if len(raw_results) >= limit_per_platform:
            break
    return raw_results


def extract_leads(raw_results: list[RawSearchResult]) -> list[LeadCandidate]:
    leads: list[LeadCandidate] = []
    for row in raw_results:
        payload = row.payload
        leads.append(
            LeadCandidate(
                lead_id=str(uuid4()),
                company=payload.get("company", "Unknown Company"),
                contact_name=payload.get("contact_name", ""),
                role=payload.get("role", ""),
                platform=row.platform,
                raw_text_snippet=row.snippet,
                email=payload.get("email", ""),
                linkedin=payload.get("linkedin", ""),
                phone=payload.get("phone", ""),
                domain=payload.get("domain", ""),
                source_url=payload.get("source_url", ""),
                industry=[payload.get("industry", "")] if payload.get("industry") else [],
            )
        )
    return leads
