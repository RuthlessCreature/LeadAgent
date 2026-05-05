from __future__ import annotations

from collections.abc import Mapping, Sequence


DEFAULT_DISCOVERY_LANGUAGES = ("en", "ar", "ur", "fr", "tr", "id", "ms", "bn", "de", "nl")

QUERY_PRESETS: dict[str, dict[str, list[str]]] = {
    "hajj_umrah": {
        "en": [
            "umrah packages",
            "hajj packages",
            "umrah travel agency",
        ],
        "ar": [
            "باقات العمرة",
            "باقات الحج",
            "وكالة الحج والعمرة",
        ],
        "ur": [
            "عمرہ پیکج",
            "حج پیکج",
            "حج و عمرہ ٹریول ایجنسی",
        ],
        "fr": [
            "forfait omra",
            "forfait hajj",
            "agence omra",
        ],
        "tr": [
            "umre paketleri",
            "hac paketleri",
            "umre seyahat acentesi",
        ],
        "id": [
            "paket umrah",
            "paket haji",
            "travel umrah",
        ],
        "ms": [
            "pakej umrah",
            "pakej haji",
            "agensi umrah",
        ],
        "bn": [
            "ওমরাহ প্যাকেজ",
            "হজ প্যাকেজ",
            "হজ ও ওমরাহ ট্রাভেল",
        ],
        "de": [
            "umrah pakete",
            "hajj pakete",
            "umrah reisebüro",
        ],
        "nl": [
            "umrah pakketten",
            "hajj pakketten",
            "umrah reisbureau",
        ],
    }
}

LOCATION_ALIAS_PRESETS: dict[str, dict[str, list[str]]] = {
    "ar": {
        "Houston": ["هيوستن"],
        "Chicago": ["شيكاغو"],
        "New York": ["نيويورك"],
        "Dallas": ["دالاس"],
        "Los Angeles": ["لوس أنجلوس"],
        "Toronto": ["تورونتو"],
        "Mississauga": ["ميسيساجا"],
        "Ottawa": ["أوتاوا"],
        "Montreal": ["مونتريال"],
        "Calgary": ["كالجاري"],
        "Vancouver": ["فانكوفر"],
        "London": ["لندن"],
        "Birmingham": ["برمنغهام"],
        "Manchester": ["مانشستر"],
        "Leicester": ["ليستر"],
        "Bradford": ["برادفورد"],
        "Luton": ["لوتون"],
        "Leeds": ["ليدز"],
        "Glasgow": ["غلاسكو"],
        "USA": ["الولايات المتحدة", "أمريكا"],
        "Canada": ["كندا"],
        "UK": ["المملكة المتحدة", "بريطانيا"],
        "Australia": ["أستراليا"],
        "South Africa": ["جنوب أفريقيا"],
        "Ireland": ["أيرلندا"],
        "New Zealand": ["نيوزيلندا"],
        "Netherlands": ["هولندا"],
        "Germany": ["ألمانيا"],
        "France": ["فرنسا"],
    },
    "ur": {
        "Houston": ["ہیوسٹن"],
        "Chicago": ["شکاگو"],
        "New York": ["نیویارک"],
        "Dallas": ["ڈیلس"],
        "Los Angeles": ["لاس اینجلس"],
        "Toronto": ["ٹورنٹو"],
        "Mississauga": ["مسیساگا"],
        "Ottawa": ["اوٹاوا"],
        "Montreal": ["مونٹریال"],
        "Calgary": ["کیلگری"],
        "Vancouver": ["وینکوور"],
        "London": ["لندن"],
        "Birmingham": ["برمنگھم"],
        "Manchester": ["مانچسٹر"],
        "Leicester": ["لیسٹر"],
        "Bradford": ["بریڈفورڈ"],
        "Luton": ["لوٹن"],
        "Leeds": ["لیڈز"],
        "Glasgow": ["گلاسگو"],
        "USA": ["امریکہ"],
        "Canada": ["کینیڈا"],
        "UK": ["برطانیہ", "یوکے"],
        "Australia": ["آسٹریلیا"],
        "South Africa": ["جنوبی افریقہ"],
        "Ireland": ["آئرلینڈ"],
        "New Zealand": ["نیوزی لینڈ"],
        "Netherlands": ["نیدرلینڈز"],
        "Germany": ["جرمنی"],
        "France": ["فرانس"],
    },
    "bn": {
        "Houston": ["হিউস্টন"],
        "Chicago": ["শিকাগো"],
        "New York": ["নিউ ইয়র্ক"],
        "Dallas": ["ডালাস"],
        "Los Angeles": ["লস অ্যাঞ্জেলেস"],
        "Toronto": ["টরন্টো"],
        "Mississauga": ["মিসিসাগা"],
        "Ottawa": ["অটোয়া"],
        "Montreal": ["মন্ট্রিয়াল"],
        "Calgary": ["ক্যালগারি"],
        "Vancouver": ["ভ্যাঙ্কুভার"],
        "London": ["লন্ডন"],
        "Birmingham": ["বার্মিংহাম"],
        "Manchester": ["ম্যানচেস্টার"],
        "Leicester": ["লেস্টার"],
        "Bradford": ["ব্র্যাডফোর্ড"],
        "Luton": ["লুটন"],
        "Leeds": ["লিডস"],
        "Glasgow": ["গ্লাসগো"],
        "USA": ["যুক্তরাষ্ট্র", "আমেরিকা"],
        "Canada": ["কানাডা"],
        "UK": ["যুক্তরাজ্য", "ব্রিটেন"],
        "Australia": ["অস্ট্রেলিয়া"],
        "South Africa": ["দক্ষিণ আফ্রিকা"],
        "Ireland": ["আয়ারল্যান্ড"],
        "New Zealand": ["নিউজিল্যান্ড"],
        "Netherlands": ["নেদারল্যান্ডস"],
        "Germany": ["জার্মানি"],
        "France": ["ফ্রান্স"],
    },
    "fr": {
        "London": ["Londres"],
        "USA": ["États-Unis"],
        "UK": ["Royaume-Uni"],
        "Australia": ["Australie"],
        "South Africa": ["Afrique du Sud"],
        "Ireland": ["Irlande"],
        "Netherlands": ["Pays-Bas"],
        "Germany": ["Allemagne"],
    },
    "tr": {
        "London": ["Londra"],
        "USA": ["Amerika"],
        "UK": ["Birleşik Krallık"],
        "Australia": ["Avustralya"],
        "South Africa": ["Güney Afrika"],
        "Ireland": ["İrlanda"],
        "Netherlands": ["Hollanda"],
        "Germany": ["Almanya"],
        "France": ["Fransa"],
    },
    "id": {
        "USA": ["Amerika Serikat"],
        "UK": ["Inggris"],
        "South Africa": ["Afrika Selatan"],
        "Ireland": ["Irlandia"],
        "Netherlands": ["Belanda"],
        "Germany": ["Jerman"],
        "France": ["Prancis"],
    },
    "ms": {
        "USA": ["Amerika Syarikat"],
        "UK": ["United Kingdom", "Britain"],
        "South Africa": ["Afrika Selatan"],
        "Ireland": ["Ireland"],
        "Netherlands": ["Belanda"],
        "Germany": ["Jerman"],
        "France": ["Perancis"],
    },
    "de": {
        "USA": ["Vereinigte Staaten"],
        "UK": ["Vereinigtes Königreich"],
        "Australia": ["Australien"],
        "South Africa": ["Südafrika"],
        "Ireland": ["Irland"],
        "Netherlands": ["Niederlande"],
        "France": ["Frankreich"],
    },
    "nl": {
        "USA": ["Verenigde Staten"],
        "UK": ["Verenigd Koninkrijk"],
        "South Africa": ["Zuid-Afrika"],
        "Ireland": ["Ierland"],
        "Germany": ["Duitsland"],
        "France": ["Frankrijk"],
    },
}


def expand_public_web_queries(
    queries: Sequence[str] | None = None,
    query_preset: str = "",
    languages: Sequence[str] | None = None,
    locations: Sequence[str] | None = None,
    query_terms: Sequence[str] | None = None,
    translated_terms: Mapping[str, Sequence[str]] | None = None,
    include_global_queries: bool = True,
    max_queries: int = 1500,
    use_location_aliases: bool = True,
    location_aliases: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    selected_languages = normalize_languages(languages, query_preset)
    normalized_locations = dedupe_strings(locations or [])
    expanded: list[str] = []

    expanded.extend(dedupe_strings(queries or []))

    for term in dedupe_strings(query_terms or []):
        expanded.extend(_queries_for_terms([term], normalized_locations, include_global_queries))

    preset_terms = QUERY_PRESETS.get((query_preset or "").strip().lower(), {})
    for language in selected_languages:
        language_locations = expand_locations_for_language(
            normalized_locations,
            language,
            use_location_aliases=use_location_aliases,
            location_aliases=location_aliases,
        )
        expanded.extend(
            _queries_for_terms(
                preset_terms.get(language, []),
                language_locations,
                include_global_queries,
            )
        )

    for language, terms in (translated_terms or {}).items():
        language_locations = expand_locations_for_language(
            normalized_locations,
            str(language or "").strip().lower(),
            use_location_aliases=use_location_aliases,
            location_aliases=location_aliases,
        )
        expanded.extend(_queries_for_terms(terms, language_locations, include_global_queries))

    return dedupe_strings(expanded)[: max(1, max_queries)]


def normalize_languages(languages: Sequence[str] | None, query_preset: str = "") -> list[str]:
    if languages:
        requested = dedupe_strings(languages)
    else:
        requested = list(DEFAULT_DISCOVERY_LANGUAGES)

    preset_terms = QUERY_PRESETS.get((query_preset or "").strip().lower(), {})
    if preset_terms:
        return [language for language in requested if language in preset_terms]
    return requested


def supported_query_presets() -> list[str]:
    return sorted(QUERY_PRESETS.keys())


def expand_locations_for_language(
    locations: Sequence[str],
    language: str,
    use_location_aliases: bool = True,
    location_aliases: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    if not use_location_aliases:
        return dedupe_strings(locations)

    preset_aliases = LOCATION_ALIAS_PRESETS.get((language or "").strip().lower(), {})
    expanded: list[str] = []
    for location in dedupe_strings(locations):
        aliases = [*preset_aliases.get(location, []), *((location_aliases or {}).get(location, []) or [])]
        expanded.extend(dedupe_strings([*aliases, location]))
    return dedupe_strings(expanded)


def _queries_for_terms(terms: Sequence[str], locations: Sequence[str], include_global_queries: bool) -> list[str]:
    output: list[str] = []
    normalized_terms = dedupe_strings(terms)
    for term in normalized_terms:
        if include_global_queries:
            output.append(term)
        for location in locations:
            output.append(f"{term} {location}".strip())
    return output


def dedupe_strings(values: Sequence[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = " ".join(str(value or "").strip().split())
        lowered = normalized.lower()
        if not normalized or lowered in seen:
            continue
        seen.add(lowered)
        output.append(normalized)
    return output
