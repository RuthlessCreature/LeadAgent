from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_hajj_crm_exports import (  # noqa: E402
    clean_company_name,
    classify_email_type,
    infer_country,
    normalize_phone,
)


def test_clean_company_name_prefers_domain_when_name_is_truncated() -> None:
    assert clean_company_name("Accurate Travel S", "accuratetravels.com") == "Accurate Travels"


def test_clean_company_name_prefers_domain_when_name_is_marketing_title() -> None:
    assert clean_company_name("Travel Packages In Chicago, IL", "hajjmakkahtours.com") == "Hajj Makkah Tours"


def test_clean_company_name_keeps_best_title_segment() -> None:
    assert clean_company_name("Hajj 2026 - ISRA Foundation", "israfoundation.com") == "ISRA Foundation"


def test_clean_company_name_rejects_generic_agency_title() -> None:
    assert clean_company_name("Approved Islamic Travel Agents", "qiblatain.com") == "Qiblatain"


def test_infer_country_prefers_domain_tld() -> None:
    country, source = infer_country({"source_url": ""}, "alhijratravel.nl", "", "")
    assert country == "Netherlands"
    assert source == "domain_tld"


def test_infer_country_falls_back_to_phone() -> None:
    country, source = infer_country({"source_url": ""}, "example.com", "", "+44 208 145 7860")
    assert country == "United Kingdom"
    assert source == "phone"


def test_infer_country_prefers_text_hint_when_phone_is_ambiguous() -> None:
    country, source = infer_country(
        {
            "source_url": "https://www.worldhajj.com/hajj-packages-from-australia",
            "raw_text_snippet": "We are an experienced Australian travel agency offering the best Hajj Packages 2026.",
            "company": "World Hajj",
        },
        "worldhajj.com",
        "info@worldhajj.com",
        "+1 307-392-4596",
    )
    assert country == "Australia"
    assert source == "text_hint"


def test_infer_country_detects_indonesia_from_text_hint() -> None:
    country, source = infer_country(
        {
            "source_url": "https://dreamtour.co/hajj",
            "raw_text_snippet": "PT Dream Tours and Travel adalah Travel Umroh Terbaik di Jakarta.",
            "company": "Travel Umroh Terbaik di Jakarta",
        },
        "dreamtour.co",
        "info@dreamtour.co",
        "021 2138 1090",
    )
    assert country == "Indonesia"
    assert source == "text_hint"


def test_normalize_phone_uses_country_hint() -> None:
    assert normalize_phone("020 8145 7860", "United Kingdom") == "+442081457860"


def test_normalize_phone_trims_trailing_nanp_noise() -> None:
    assert normalize_phone("+1 201-726-7525 12", "United States") == "+12017267525"


def test_normalize_phone_extracts_embedded_nanp_number() -> None:
    assert normalize_phone("5464) 905-624-8555", "Canada") == "+19056248555"


def test_normalize_phone_formats_french_local_number() -> None:
    assert normalize_phone("01 42 36 23 29", "France") == "+33142362329"


def test_classify_email_type_detects_free_provider() -> None:
    assert classify_email_type("info@gmail.com", "agency.com") == "free_provider"
