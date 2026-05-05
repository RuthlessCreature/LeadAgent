"""
LinkedIn search service (Selenium).
It opens LinkedIn people search, clicks each contact avatar, enters profile pages,
and extracts public profile information.
"""

from __future__ import annotations

import os
import random
import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Set
from urllib.parse import quote, urlparse
from uuid import NAMESPACE_URL, uuid5

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.models import (
    ConsentStatus,
    ICPDefinition,
    LeadCandidate,
    LeadScores,
    LeadSourceType,
    Platform,
    VerificationStatus,
)


@dataclass
class SearchSettings:
    browser: str = os.getenv("LINKEDIN_BROWSER", "edge")
    headless: bool = os.getenv("LINKEDIN_HEADLESS", "false").lower() == "true"
    # 0 means unlimited; process all generated queries by default.
    max_queries: int = int(os.getenv("LINKEDIN_MAX_QUERIES", "0"))
    max_profiles_per_query: int = int(os.getenv("LINKEDIN_MAX_PROFILES_PER_QUERY", "30"))
    max_pages_per_query: int = int(os.getenv("LINKEDIN_MAX_PAGES_PER_QUERY", "10"))
    search_scroll_rounds: int = int(os.getenv("LINKEDIN_SCROLL_ROUNDS", "3"))
    delay_min: float = float(os.getenv("LINKEDIN_DELAY_MIN", "1.2"))
    delay_max: float = float(os.getenv("LINKEDIN_DELAY_MAX", "2.9"))
    page_load_timeout: int = int(os.getenv("LINKEDIN_PAGE_LOAD_TIMEOUT", "40"))
    wait_timeout: int = int(os.getenv("LINKEDIN_WAIT_TIMEOUT", "18"))
    manual_login_wait_seconds: int = int(os.getenv("LINKEDIN_MANUAL_LOGIN_WAIT_SECONDS", "90"))
    user_data_dir: str = os.getenv("LINKEDIN_USER_DATA_DIR", "").strip()


class LinkedInSearcher:
    def __init__(self):
        self.settings = SearchSettings()

    def search_multi(self, queries: List[Dict]) -> List[Dict]:
        all_results: List[Dict] = []
        seen_profile_urls: Set[str] = set()

        if not queries:
            return all_results

        driver = self._build_driver()
        try:
            if not self._ensure_logged_in(driver):
                print("[LinkedIn] Login not detected, skipping scraping.")
                return all_results

            # Always run every generated query from the parser.
            for query in queries:
                query_text = (query.get("query") or "").strip()
                if not query_text:
                    continue

                platform = (query.get("platform") or "linkedin").lower()
                if platform != "linkedin":
                    continue

                query_type = (query.get("type") or "people").strip()
                print(f"[LinkedIn] Searching: {query_text}")
                query_results = self._search_query(driver, query_text, query_type, seen_profile_urls)
                all_results.extend(query_results)
                print(f"[LinkedIn] Captured {len(query_results)} profiles for query.")
                self._pause(0.9, 1.6)
        finally:
            try:
                driver.quit()
            except Exception:
                pass

        return all_results

    def _build_driver(self) -> WebDriver:
        browser = self.settings.browser.lower()
        user_agent = random.choice(
            [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            ]
        )

        if browser == "chrome":
            options = webdriver.ChromeOptions()
            self._apply_common_options(options, user_agent)
            driver = webdriver.Chrome(options=options)
        else:
            options = webdriver.EdgeOptions()
            self._apply_common_options(options, user_agent)
            try:
                driver = webdriver.Edge(options=options)
            except WebDriverException:
                # Fallback to Chrome when Edge driver is unavailable.
                chrome_options = webdriver.ChromeOptions()
                self._apply_common_options(chrome_options, user_agent)
                driver = webdriver.Chrome(options=chrome_options)

        driver.set_page_load_timeout(self.settings.page_load_timeout)
        return driver

    def _apply_common_options(self, options, user_agent: str) -> None:
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--lang=en-US")
        options.add_argument(f"--user-agent={user_agent}")
        options.add_argument(f"--window-size={random.randint(1280, 1520)},{random.randint(820, 980)}")
        if self.settings.headless:
            options.add_argument("--headless=new")
        if self.settings.user_data_dir:
            options.add_argument(f"--user-data-dir={self.settings.user_data_dir}")
        try:
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
        except Exception:
            pass

    def _ensure_logged_in(self, driver: WebDriver) -> bool:
        driver.get("https://www.linkedin.com/feed/")
        self._pause(1.1, 2.1)
        if self._is_logged_in(driver):
            return True

        print("[LinkedIn] Please complete login in the opened browser window.")
        driver.get("https://www.linkedin.com/login")
        deadline = time.time() + self.settings.manual_login_wait_seconds
        while time.time() < deadline:
            self._pause(1.8, 2.8)
            if self._is_logged_in(driver):
                return True

        return False

    @staticmethod
    def _is_logged_in(driver: WebDriver) -> bool:
        url = driver.current_url.lower()
        if "feed" in url and "linkedin.com/feed" in url:
            return True
        if "login" in url or "checkpoint" in url or "challenge" in url:
            return False
        return "linkedin.com" in url and "/in/" in url

    def _search_query(
        self, driver: WebDriver, query_text: str, query_type: str, seen_profile_urls: Set[str]
    ) -> List[Dict]:
        results: List[Dict] = []
        search_url = f"https://www.linkedin.com/search/results/people/?keywords={quote(query_text)}"
        max_pages = max(1, self.settings.max_pages_per_query)
        max_profiles = max(1, self.settings.max_profiles_per_query)

        for page_no in range(1, max_pages + 1):
            if len(results) >= max_profiles:
                break

            page_url = self._results_page_url(search_url, page_no)
            driver.get(page_url)
            self._pause(1.2, 2.2)

            if self._is_challenge_page(driver):
                print("[LinkedIn] Challenge page detected, stop current query.")
                break

            self._wait_results_ready(driver)
            self._soft_scroll(driver, rounds=self.settings.search_scroll_rounds)
            profile_urls = self._collect_profile_urls(driver)

            if not profile_urls:
                print(f"[LinkedIn] No profile links found on page {page_no}.")
                break

            print(f"[LinkedIn] Page {page_no}: {len(profile_urls)} candidates.")

            for profile_url in profile_urls:
                if len(results) >= max_profiles:
                    break
                if not profile_url or profile_url in seen_profile_urls:
                    continue

                seen_profile_urls.add(profile_url)
                try:
                    driver.get(profile_url)
                    self._pause(1.0, 1.9)
                except Exception:
                    continue

                if self._is_challenge_page(driver):
                    print("[LinkedIn] Challenge page detected while opening profile.")
                    return results

                scraped = self._scrape_profile(driver, query_type, query_text, profile_url)
                if scraped:
                    results.append(scraped)
                    has_email = "yes" if scraped.get("email") else "no"
                    print(f"  -> {scraped.get('name', 'Unknown')} | email:{has_email}")

                # Return to results page after inspecting each profile.
                try:
                    driver.get(page_url)
                    self._wait_results_ready(driver)
                    self._pause(0.6, 1.2)
                except Exception:
                    break

        return results

    def _wait_results_ready(self, driver: WebDriver) -> None:
        selectors = [
            ".reusable-search__result-container",
            "div[data-view-name='search-entity-result-universal-template']",
            ".search-results-container li",
        ]
        for selector in selectors:
            try:
                WebDriverWait(driver, min(8, self.settings.wait_timeout)).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                return
            except TimeoutException:
                continue

    @staticmethod
    def _results_page_url(search_url: str, page_no: int) -> str:
        if page_no <= 1:
            return search_url
        separator = "&" if "?" in search_url else "?"
        return f"{search_url}{separator}page={page_no}"

    def _collect_profile_urls(self, driver: WebDriver) -> List[str]:
        selectors = [
            "a.app-aware-link[href*='/in/']",
            "a[data-test-app-aware-link][href*='/in/']",
            ".search-results-container a[href*='/in/']",
            ".reusable-search__result-container a[href*='/in/']",
        ]
        urls: List[str] = []
        seen: Set[str] = set()
        for selector in selectors:
            try:
                anchors = driver.find_elements(By.CSS_SELECTOR, selector)
            except Exception:
                anchors = []
            for anchor in anchors:
                href = self._normalize_profile_url(anchor.get_attribute("href") or "")
                if not href or href in seen:
                    continue
                seen.add(href)
                urls.append(href)
        return urls

    def _go_to_next_results_page(self, driver: WebDriver, target_page: int) -> bool:
        before = self._results_page_fingerprint(driver)
        next_selectors = [
            "button[aria-label='Next']",
            "button[aria-label*='Next']",
            "button.artdeco-pagination__button--next",
            "li.artdeco-pagination__indicator--number button",
        ]
        next_btn = None
        for selector in next_selectors:
            try:
                for candidate in driver.find_elements(By.CSS_SELECTOR, selector):
                    disabled = (
                        (candidate.get_attribute("disabled") is not None)
                        or ("disabled" in (candidate.get_attribute("class") or "").lower())
                        or (candidate.get_attribute("aria-disabled") == "true")
                    )
                    if disabled:
                        continue

                    # Prefer explicit "next" buttons. Numeric buttons are fallback.
                    label = (candidate.get_attribute("aria-label") or candidate.text or "").strip().lower()
                    if selector == "li.artdeco-pagination__indicator--number button":
                        if label and str(target_page) not in label and candidate.text.strip() != str(target_page):
                            continue
                    next_btn = candidate
                    break
                if next_btn is not None:
                    break
            except Exception:
                continue

        if next_btn is None:
            return False

        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
            self._pause(0.2, 0.6)
            try:
                next_btn.click()
            except Exception:
                driver.execute_script("arguments[0].click();", next_btn)

            WebDriverWait(driver, self.settings.wait_timeout).until(
                lambda d: self._results_page_fingerprint(d) != before
            )
            self._pause(1.0, 1.8)
            self._wait_results_ready(driver)
            return True
        except Exception:
            return False

    def _results_page_fingerprint(self, driver: WebDriver) -> str:
        try:
            hrefs = []
            for element in driver.find_elements(
                By.CSS_SELECTOR,
                ".search-results-container a[href*='/in/'], a[data-test-app-aware-link][href*='/in/']",
            )[:5]:
                hrefs.append(self._normalize_profile_url(element.get_attribute("href") or ""))
            return "|".join([h for h in hrefs if h]) + f"::{driver.current_url}"
        except Exception:
            return driver.current_url

    def _result_cards(self, driver: WebDriver):
        selectors = [
            ".reusable-search__result-container",
            "div[data-view-name='search-entity-result-universal-template']",
            ".search-results-container li",
        ]

        for selector in selectors:
            try:
                WebDriverWait(driver, min(8, self.settings.wait_timeout)).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
            except TimeoutException:
                continue

            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                return elements

        # Last fallback: derive card roots from profile links.
        anchors = driver.find_elements(
            By.CSS_SELECTOR,
            ".search-results-container a[href*='/in/'], a[data-test-app-aware-link][href*='/in/']",
        )
        cards = []
        seen_ids = set()
        for anchor in anchors:
            try:
                card = driver.execute_script(
                    "return arguments[0].closest(\"li, div[data-view-name='search-entity-result-universal-template']\");",
                    anchor,
                )
            except Exception:
                card = None
            if card is None:
                continue
            if card.id in seen_ids:
                continue
            seen_ids.add(card.id)
            cards.append(card)
        return cards

    @staticmethod
    def _find_avatar_link(card):
        anchors = []
        anchor_selectors = [
            "a.scale-down[href*='/in/']",
            "a[href*='/in/']",
            "a.app-aware-link[href*='/in/']",
            "a[data-test-app-aware-link][href*='/in/']",
        ]
        for selector in anchor_selectors:
            try:
                anchors.extend(card.find_elements(By.CSS_SELECTOR, selector))
            except (NoSuchElementException, StaleElementReferenceException):
                continue

        seen_anchor_ids = set()
        deduped = []
        for a in anchors:
            if a.id in seen_anchor_ids:
                continue
            seen_anchor_ids.add(a.id)
            deduped.append(a)

        # Prefer avatar links first (image within anchor).
        for link in deduped:
            href = (link.get_attribute("href") or "").strip()
            if "/in/" not in href:
                continue
            try:
                link.find_element(By.CSS_SELECTOR, "img.presence-entity__image, img.EntityPhoto-circle-3, img")
                return link
            except NoSuchElementException:
                continue

        # Fallback to any profile link in card.
        for link in deduped:
            href = (link.get_attribute("href") or "").strip()
            if "/in/" in href:
                return link
        return None

    def _click_avatar_and_wait_profile(self, driver: WebDriver, avatar_link, profile_url: str) -> bool:
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", avatar_link)
            self._pause(0.2, 0.6)
            try:
                avatar_link.click()
            except Exception:
                driver.execute_script("arguments[0].click();", avatar_link)

            WebDriverWait(driver, self.settings.wait_timeout).until(
                lambda d: "/in/" in d.current_url.lower() and "linkedin.com" in d.current_url.lower()
            )
            self._pause(1.0, 2.0)
            return True
        except Exception:
            try:
                driver.get(profile_url)
                WebDriverWait(driver, self.settings.wait_timeout).until(
                    lambda d: "/in/" in d.current_url.lower() and "linkedin.com" in d.current_url.lower()
                )
                self._pause(1.0, 1.9)
                return True
            except Exception:
                return False

    def _scrape_profile(self, driver: WebDriver, query_type: str, query_text: str, profile_url: str) -> Optional[Dict]:
        try:
            WebDriverWait(driver, self.settings.wait_timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "main"))
            )
        except TimeoutException:
            return None

        main_lines = self._main_lines(driver)
        title_name = self._title_name(driver)

        name = self._first_text(
            driver,
            [
                "h1",
                "main h1",
                "main section h2",
                "main section h3",
            ],
        )
        headline = self._first_text(
            driver,
            [
                "div.text-body-medium.break-words",
                "div.text-body-medium",
                "main section p",
            ],
        )
        location = self._first_text(
            driver,
            [
                "span.text-body-small.inline.t-black--light.break-words",
                "span.text-body-small.inline.t-black--light",
                "main section p",
            ],
        )
        company = self._first_text(
            driver,
            [
                "section[id*='experience'] li div.t-bold span[aria-hidden='true']",
                "section[id*='experience'] li .display-flex.align-items-center.mr1.t-bold span[aria-hidden='true']",
                "section[id*='experience'] li h3",
            ],
        )
        about = self._first_text(
            driver,
            [
                "section[id='about'] div.inline-show-more-text span[aria-hidden='true']",
                "section[id='about'] div.inline-show-more-text",
                "section[id='about'] .display-flex.ph5.pv3 span[aria-hidden='true']",
            ],
        )

        if not name:
            name = title_name
        if not name:
            name = self._extract_name_from_lines(main_lines)

        if not headline:
            headline = self._extract_headline_from_lines(main_lines, name)

        if not location:
            location = self._extract_location_from_lines(main_lines)

        if not company:
            company = self._extract_company_from_lines(main_lines, headline)

        if not about:
            about = self._extract_about_from_lines(main_lines)

        email = self._extract_email(driver, main_lines)

        name = name or "Unknown"
        bio_parts = [p for p in [headline, company, location] if p]
        if about:
            bio_parts.append(about[:280])
        bio = " | ".join(bio_parts)[:500]
        final_url = self._normalize_profile_url(driver.current_url or profile_url)

        return {
            "name": name[:100],
            "username": self._extract_username(final_url),
            "company": (company or "")[:160],
            "url": final_url[:500],
            "bio": bio,
            "email": email[:200] if email else "",
            "platform": "linkedin",
            "type": query_type or "people",
            "query": query_text,
        }

    @staticmethod
    def _first_text(driver: WebDriver, selectors: List[str]) -> str:
        for selector in selectors:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                text = (element.text or "").strip()
                if text:
                    return re.sub(r"\s+", " ", text)
            except NoSuchElementException:
                continue
            except Exception:
                continue
        return ""

    @staticmethod
    def _title_name(driver: WebDriver) -> str:
        title = (driver.title or "").strip()
        if not title:
            return ""
        if "|" in title:
            title = title.split("|", 1)[0].strip()
        if title.lower() == "linkedin":
            return ""
        return re.sub(r"\s+", " ", title)

    @staticmethod
    def _main_lines(driver: WebDriver) -> List[str]:
        try:
            text = driver.execute_script(
                "return (document.querySelector('main') && document.querySelector('main').innerText) || '';"
            )
        except Exception:
            text = ""
        if not text:
            return []
        lines = [re.sub(r"\s+", " ", ln.strip()) for ln in str(text).splitlines()]
        return [ln for ln in lines if ln]

    @staticmethod
    def _extract_name_from_lines(lines: List[str]) -> str:
        if not lines:
            return ""
        first = lines[0]
        # Avoid section headers being mistaken as names.
        blocked = {"about", "featured", "activity", "experience", "education", "skills"}
        if first.lower() in blocked:
            return ""
        return first[:100]

    @staticmethod
    def _extract_headline_from_lines(lines: List[str], name: str) -> str:
        if not lines:
            return ""
        start_idx = 0
        if name:
            for i, ln in enumerate(lines[:10]):
                if ln == name:
                    start_idx = i + 1
                    break
        for ln in lines[start_idx : start_idx + 8]:
            low = ln.lower()
            if any(k in low for k in ("contact info", "connect", "message", "about", "followers", "open to work")):
                continue
            if len(ln) < 2:
                continue
            return ln[:160]
        return ""

    @staticmethod
    def _extract_location_from_lines(lines: List[str]) -> str:
        for ln in lines[:20]:
            low = ln.lower()
            if "contact info" in low:
                continue
            # Common location shape, e.g. "Dubai, Dubai, United Arab Emirates"
            if "," in ln and 6 <= len(ln) <= 120 and len(ln.split()) >= 2:
                return ln[:160]
        return ""

    @staticmethod
    def _extract_company_from_lines(lines: List[str], headline: str) -> str:
        if headline:
            m = re.search(r"\b(?:at|en|@)\s+(.+)$", headline, flags=re.IGNORECASE)
            if m:
                return m.group(1).strip()[:160]
        for ln in lines[:30]:
            low = ln.lower()
            if any(k in low for k in ("contact info", "about", "open to work", "message", "connect")):
                continue
            if " • " in ln:
                return ln.split(" • ", 1)[0].strip()[:160]
        return ""

    @staticmethod
    def _extract_about_from_lines(lines: List[str]) -> str:
        if not lines:
            return ""
        headings = {
            "featured",
            "activity",
            "experience",
            "education",
            "skills",
            "licenses & certifications",
            "recommendations",
            "projects",
        }
        about_idx = -1
        for i, ln in enumerate(lines):
            if ln.lower() == "about":
                about_idx = i
                break
        if about_idx < 0:
            return ""
        about_chunks: List[str] = []
        for ln in lines[about_idx + 1 : about_idx + 10]:
            low = ln.lower()
            if low in headings:
                break
            if any(k in low for k in ("show details", "see all", "contact info")):
                continue
            about_chunks.append(ln)
            if len(" ".join(about_chunks)) >= 360:
                break
        return " ".join(about_chunks).strip()[:360]

    def _extract_email(self, driver: WebDriver, main_lines: List[str]) -> str:
        # 1) Try direct extraction from visible profile text.
        direct = self._extract_email_from_text(" ".join(main_lines))
        if direct:
            return direct

        # 2) Try opening "Contact info" popup and parse email.
        modal_email = self._extract_email_from_contact_info_modal(driver)
        if modal_email:
            return modal_email

        # 3) Fallback from raw page source.
        try:
            html = driver.page_source or ""
        except Exception:
            html = ""
        return self._extract_email_from_text(html)

    @staticmethod
    def _extract_email_from_text(text: str) -> str:
        if not text:
            return ""
        match = re.search(
            r"([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})",
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            return ""
        email = match.group(1).strip().lower()
        # Ignore obvious placeholder / tracking addresses.
        ignored = ("example.com", "linkedin.com", "sentry.io")
        if any(x in email for x in ignored):
            return ""
        return email

    def _extract_email_from_contact_info_modal(self, driver: WebDriver) -> str:
        contact_btn = None
        selectors = [
            "a[href*='/overlay/contact-info/']",
            "a#top-card-text-details-contact-info",
            "a[data-control-name='contact_see_more']",
            "a[href*='contact-info']",
        ]
        for selector in selectors:
            try:
                btns = driver.find_elements(By.CSS_SELECTOR, selector)
            except Exception:
                btns = []
            if btns:
                contact_btn = btns[0]
                break

        if contact_btn is None:
            return ""

        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", contact_btn)
            self._pause(0.2, 0.5)
            try:
                contact_btn.click()
            except Exception:
                driver.execute_script("arguments[0].click();", contact_btn)

            WebDriverWait(driver, min(8, self.settings.wait_timeout)).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href^='mailto:'], .ci-email a, .pv-contact-info"))
            )
            self._pause(0.4, 0.9)

            # Preferred: mailto link in modal.
            for selector in ["a[href^='mailto:']", ".ci-email a", ".pv-contact-info__contact-type.ci-email a"]:
                try:
                    for el in driver.find_elements(By.CSS_SELECTOR, selector):
                        href = (el.get_attribute("href") or "").strip()
                        if href.startswith("mailto:"):
                            email = href.replace("mailto:", "", 1).split("?")[0].strip()
                        else:
                            email = (el.text or "").strip()
                        email = self._extract_email_from_text(email)
                        if email:
                            self._dismiss_modal(driver)
                            return email
                except Exception:
                    continue

            # Fallback: regex over visible modal text.
            modal_text = ""
            for selector in [".pv-contact-info", ".artdeco-modal", "body"]:
                try:
                    modal_text = driver.find_element(By.CSS_SELECTOR, selector).text or ""
                    if modal_text:
                        break
                except Exception:
                    continue
            email = self._extract_email_from_text(modal_text)
            self._dismiss_modal(driver)
            return email
        except Exception:
            self._dismiss_modal(driver)
            return ""

    @staticmethod
    def _dismiss_modal(driver: WebDriver) -> None:
        selectors = [
            "button[aria-label='Dismiss']",
            "button[aria-label='Close']",
            "button.artdeco-modal__dismiss",
        ]
        for selector in selectors:
            try:
                buttons = driver.find_elements(By.CSS_SELECTOR, selector)
            except Exception:
                buttons = []
            if not buttons:
                continue
            try:
                buttons[0].click()
            except Exception:
                try:
                    driver.execute_script("arguments[0].click();", buttons[0])
                except Exception:
                    pass
            break

    @staticmethod
    def _normalize_profile_url(url: str) -> str:
        if not url:
            return ""
        parsed = urlparse(url)
        path = parsed.path or ""
        if "/in/" not in path:
            return ""
        clean = f"https://www.linkedin.com{path}"
        return clean.rstrip("/")

    @staticmethod
    def _extract_username(url: str) -> str:
        parsed = urlparse(url)
        pieces = [p for p in parsed.path.split("/") if p]
        if len(pieces) >= 2 and pieces[0] == "in":
            return pieces[1][:80]
        return "linkedin_user"

    @staticmethod
    def _is_challenge_page(driver: WebDriver) -> bool:
        url = (driver.current_url or "").lower()
        if any(flag in url for flag in ("checkpoint", "challenge", "captcha")):
            return True
        page = (driver.page_source or "").lower()
        return "security verification" in page or "quick verification" in page

    def _soft_scroll(self, driver: WebDriver, rounds: int) -> None:
        for _ in range(max(0, rounds)):
            delta = random.randint(350, 780)
            driver.execute_script(f"window.scrollBy(0, {delta});")
            self._pause(0.4, 1.0)

    def _pause(self, min_delay: float = None, max_delay: float = None) -> None:
        low = self.settings.delay_min if min_delay is None else min_delay
        high = self.settings.delay_max if max_delay is None else max_delay
        time.sleep(random.uniform(low, high))


class SyncSearcher:
    def __init__(self):
        self.searcher = LinkedInSearcher()

    def multi_search(self, queries: List[Dict]) -> List[Dict]:
        return self.searcher.search_multi(queries)


# ---------------------------------------------------------------------------
# FastAPI compatibility helpers used by backend/app/main.py
# ---------------------------------------------------------------------------


MOCK_LEADS: dict[Platform, list[dict]] = {
    Platform.linkedin: [
        {
            "company": "Atlas Manufacturing Group",
            "contact_name": "Mia Chen",
            "role": "Head of Procurement",
            "email": "mia.chen@atlas-manufacturing.example",
            "phone": "+1-555-0101",
            "linkedin": "https://demo.leadagent.example/linkedin/mia-chen",
            "domain": "atlas-manufacturing.example",
            "industry": ["manufacturing"],
            "snippet": "Looking for suppliers and comparing RFQ tools with CRM synchronization.",
            "platform": "linkedin",
            "source_type": "public_web",
            "source_label": "Public company profile",
            "source_url": "https://atlas-manufacturing.example/procurement",
            "consent_status": "legitimate_interest",
            "verification_status": "company_verified",
        },
        {
            "company": "NorthBridge Logistics",
            "contact_name": "Aaron James",
            "role": "Director of Strategic Sourcing",
            "email": "aaron.james@northbridge-logistics.example",
            "phone": "",
            "linkedin": "https://demo.leadagent.example/linkedin/aaron-james",
            "domain": "northbridge-logistics.example",
            "industry": ["logistics"],
            "snippet": "Evaluating vendors for cross-border freight automation and supplier discovery.",
            "platform": "linkedin",
            "source_type": "public_web",
            "source_label": "Public company profile",
            "source_url": "https://northbridge-logistics.example/strategic-sourcing",
            "consent_status": "legitimate_interest",
            "verification_status": "company_verified",
        },
        {
            "company": "GreenForge Components",
            "contact_name": "Nora Patel",
            "role": "Purchasing Manager",
            "email": "nora@greenforge-components.example",
            "phone": "+1-555-0109",
            "linkedin": "https://demo.leadagent.example/linkedin/nora-patel",
            "domain": "greenforge-components.example",
            "industry": ["manufacturing"],
            "snippet": "Request for quotation process is manual; team is looking for supplier automation.",
            "platform": "linkedin",
            "source_type": "public_web",
            "source_label": "Public company profile",
            "source_url": "https://greenforge-components.example/rfq",
            "consent_status": "legitimate_interest",
            "verification_status": "email_verified",
        },
    ],
    Platform.google: [
        {
            "company": "Velocity Sourcing Labs",
            "contact_name": "Ethan Cole",
            "role": "Sales Operations Manager",
            "email": "ethan.cole@velocity-sourcing.example",
            "phone": "",
            "linkedin": "",
            "domain": "velocity-sourcing.example",
            "industry": ["saas", "manufacturing"],
            "snippet": "B2B buyer intent platform with pricing pages focused on procurement teams.",
            "platform": "google",
            "source_type": "public_web",
            "source_label": "Company website and search result",
            "source_url": "https://velocity-sourcing.example/pricing",
            "consent_status": "legitimate_interest",
            "verification_status": "company_verified",
        },
        {
            "company": "EuroTrade OEM Network",
            "contact_name": "Lisa Muller",
            "role": "Procurement Lead",
            "email": "lisa@eurotrade-oem.example",
            "phone": "",
            "linkedin": "",
            "domain": "eurotrade-oem.example",
            "industry": ["manufacturing"],
            "snippet": "Comparing supplier outreach software for international RFQ pipelines.",
            "platform": "google",
            "source_type": "public_web",
            "source_label": "Company website and search result",
            "source_url": "https://eurotrade-oem.example/partners",
            "consent_status": "legitimate_interest",
            "verification_status": "company_verified",
        },
    ],
    Platform.b2b_db: [
        {
            "company": "PrimeSupplier Index",
            "contact_name": "Data Team",
            "role": "Sourcing Operations",
            "email": "ops@prime-supplier-index.example",
            "phone": "",
            "linkedin": "",
            "domain": "prime-supplier-index.example",
            "industry": ["manufacturing", "logistics"],
            "snippet": "Database segment shows buyers hiring procurement analysts and evaluating vendors.",
            "platform": "b2b_db",
            "source_type": "licensed_database",
            "source_label": "Licensed B2B data vendor",
            "source_url": "https://partner-data.example/primesupplier-index",
            "consent_status": "legitimate_interest",
            "verification_status": "company_verified",
        },
        {
            "company": "Harbor Procurement Partners",
            "contact_name": "Sofia Ramirez",
            "role": "VP Growth",
            "email": "sofia@harbor-procurement.example",
            "phone": "+1-555-0142",
            "linkedin": "",
            "domain": "harbor-procurement.example",
            "industry": ["logistics"],
            "snippet": "Outbound campaigns for supplier sourcing expansion across US and Germany.",
            "platform": "b2b_db",
            "source_type": "licensed_database",
            "source_label": "Licensed B2B data vendor",
            "source_url": "https://partner-data.example/harbor-procurement",
            "consent_status": "legitimate_interest",
            "verification_status": "email_verified",
        },
    ],
    Platform.facebook: [],
    Platform.youtube: [],
    Platform.tiktok: [],
    Platform.instagram: [],
}


def _as_platform(value: Platform | str | None) -> Platform:
    if isinstance(value, Platform):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        for platform in Platform:
            if platform.value == lowered:
                return platform
    return Platform.linkedin


def _as_source_type(value: LeadSourceType | str | None) -> LeadSourceType:
    if isinstance(value, LeadSourceType):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        for source_type in LeadSourceType:
            if source_type.value == lowered:
                return source_type
    return LeadSourceType.demo


def _as_consent_status(value: ConsentStatus | str | None) -> ConsentStatus:
    if isinstance(value, ConsentStatus):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        for status in ConsentStatus:
            if status.value == lowered:
                return status
    return ConsentStatus.unknown


def _as_verification_status(value: VerificationStatus | str | None) -> VerificationStatus:
    if isinstance(value, VerificationStatus):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        for status in VerificationStatus:
            if status.value == lowered:
                return status
    return VerificationStatus.unverified


def build_platform_query(query: str, icp: ICPDefinition, platform: Platform) -> str:
    parts: list[str] = [query.strip()]
    if icp.industry:
        parts.append(" ".join(icp.industry[:2]))
    if icp.role_titles:
        parts.append(" ".join(icp.role_titles[:2]))
    if platform == Platform.linkedin:
        parts.append("site:linkedin.com/in")
    if platform == Platform.google:
        parts.append("B2B buyer intent")
    if platform == Platform.b2b_db:
        parts.append("supplier database")
    return " ".join(part for part in parts if part).strip()


def _mock_platform_results(query: str, icp: ICPDefinition, platform: Platform, limit: int) -> list[dict]:
    del icp  # Mock mode does not need strict ICP filtering.
    templates = MOCK_LEADS.get(platform, [])
    records: list[dict] = []
    for index, item in enumerate(templates[: max(0, limit)]):
        row = dict(item)
        row["query"] = query
        row["source_rank"] = index + 1
        records.append(row)
    return records


def search_platform(query: str, icp: ICPDefinition, platform: Platform, limit: int = 5) -> list[dict]:
    mode = os.getenv("SEARCH_MODE", "mock").strip().lower()
    safe_limit = max(1, int(limit))

    if mode in {"live", "selenium"} and platform == Platform.linkedin:
        searcher = LinkedInSearcher()
        raw = searcher.search_multi(
            [
                {
                    "query": build_platform_query(query, icp, platform),
                    "platform": platform.value,
                    "type": "people",
                }
            ]
        )
        return raw[:safe_limit]

    return _mock_platform_results(query, icp, platform, safe_limit)


def _normalize_industry(raw: object) -> list[str]:
    if isinstance(raw, list):
        values = [str(item).strip().lower() for item in raw if str(item).strip()]
        return values
    if isinstance(raw, str):
        tokens = [part.strip().lower() for part in re.split(r"[,/|]", raw) if part.strip()]
        return tokens
    return []


def _domain_from_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    return (parsed.netloc or "").lower().replace("www.", "")


def extract_leads(raw_results: list[dict]) -> list[LeadCandidate]:
    leads: list[LeadCandidate] = []
    seen_ids: set[str] = set()

    for record in raw_results:
        platform = _as_platform(record.get("platform"))
        company = str(record.get("company") or record.get("username") or "Unknown Company").strip()
        contact_name = str(record.get("contact_name") or record.get("name") or "").strip()
        role = str(record.get("role") or "").strip()
        email = str(record.get("email") or "").strip().lower()
        phone = str(record.get("phone") or "").strip()
        linkedin = str(record.get("linkedin") or record.get("url") or "").strip()
        source_url = str(record.get("source_url") or "").strip()
        domain = str(record.get("domain") or _domain_from_url(linkedin) or _domain_from_url(source_url) or "").strip().lower()
        snippet = str(record.get("snippet") or record.get("bio") or record.get("raw_text_snippet") or "").strip()
        industry = _normalize_industry(record.get("industry"))
        source_type = _as_source_type(record.get("source_type"))
        source_label = str(record.get("source_label") or "").strip()
        source_external_lead_id = str(record.get("source_external_lead_id") or "").strip()
        source_asset_owner_type = str(record.get("source_asset_owner_type") or "").strip()
        source_asset_owner_id = str(record.get("source_asset_owner_id") or "").strip()
        source_form_id = str(record.get("source_form_id") or "").strip()
        source_campaign_id = str(record.get("source_campaign_id") or "").strip()
        source_ad_account_id = str(record.get("source_ad_account_id") or "").strip()
        source_page_id = str(record.get("source_page_id") or "").strip()
        source_privacy_policy_url = str(record.get("source_privacy_policy_url") or "").strip()
        source_consent_text = str(record.get("source_consent_text") or "").strip()
        source_payload_version = str(record.get("source_payload_version") or "").strip()
        source_raw_payload_hash = str(record.get("source_raw_payload_hash") or "").strip()
        source_submission_timestamp = record.get("source_submission_timestamp")
        deletion_requested_at = record.get("deletion_requested_at")
        retention_expires_at = record.get("retention_expires_at")
        consent_status = _as_consent_status(record.get("consent_status"))
        verification_status = _as_verification_status(record.get("verification_status"))

        lead_key = "|".join(
            [
                platform.value,
                source_type.value,
                company.lower(),
                contact_name.lower(),
                role.lower(),
                email,
                source_external_lead_id.lower(),
                linkedin.lower(),
                domain,
                source_url.lower(),
                source_asset_owner_type.lower(),
                source_asset_owner_id.lower(),
                source_form_id.lower(),
                source_campaign_id.lower(),
                source_ad_account_id.lower(),
                source_page_id.lower(),
                str(source_submission_timestamp or ""),
                snippet.lower()[:120],
            ]
        )
        lead_id = str(uuid5(NAMESPACE_URL, lead_key))
        if lead_id in seen_ids:
            continue
        seen_ids.add(lead_id)

        leads.append(
            LeadCandidate(
                lead_id=lead_id,
                platform=platform,
                company=company,
                contact_name=contact_name,
                role=role,
                email=email,
                phone=phone,
                linkedin=linkedin,
                domain=domain,
                industry=industry,
                raw_text_snippet=snippet,
                source_type=source_type,
                source_label=source_label,
                source_url=source_url,
                source_external_lead_id=source_external_lead_id,
                source_asset_owner_type=source_asset_owner_type,
                source_asset_owner_id=source_asset_owner_id,
                source_form_id=source_form_id,
                source_campaign_id=source_campaign_id,
                source_ad_account_id=source_ad_account_id,
                source_page_id=source_page_id,
                source_privacy_policy_url=source_privacy_policy_url,
                source_consent_text=source_consent_text,
                source_submission_timestamp=source_submission_timestamp,
                source_payload_version=source_payload_version,
                source_raw_payload_hash=source_raw_payload_hash,
                deletion_requested_at=deletion_requested_at,
                retention_expires_at=retention_expires_at,
                consent_status=consent_status,
                verification_status=verification_status,
                scores=LeadScores(),
            )
        )

    return leads
