# -*- coding: utf-8 -*-
"""
LinkedIn Scraper - Anti-Detection Version
Uses Playwright with stealth settings + Selenium alternatives
"""
from playwright.sync_api import sync_playwright
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random

# ============================================
# OPTION 1: Playwright (RECOMMENDED)
# ============================================
def run_with_playwright():
    """Use Playwright - better stealth by default"""
    print('='*50)
    print('Using Playwright (Best Detection Avoidance)')
    print('='*50)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-sandbox',
            ]
        )
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/Los_Angeles',
        )
        
        # Stealth scripts
        context.add_init_script("""
            // Hide webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en', 'zh-CN'];
            });
            // Add chrome runtime
            window.chrome = { runtime: {} };
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
        
        page = context.new_page()
        
        # Anti-detection: random delays
        def human_delay(min_sec=1, max_sec=3):
            time.sleep(random.uniform(min_sec, max_sec))
        
        # Step 1: Go to LinkedIn
        print('\n[1] Opening LinkedIn...')
        page.goto('https://www.linkedin.com/', timeout=60000)
        human_delay(2, 4)
        
        # Check if login required
        if 'login' in page.url:
            print('\n[!] Please login manually in browser')
            print('After login, script will continue...')
            input('Press Enter after logging in...')
        
        # Step 2: Search
        print('\n[2] Searching for "LED lights distributor Dubai"...')
        query = 'LED lights distributor Dubai'
        search_url = f'https://www.linkedin.com/search/results/people/?keywords={query.replace(" ", "%20")}&origin=SWITCH_SEARCH_V2'
        page.goto(search_url)
        human_delay(5, 8)
        
        # Step 3: Scroll like human
        print('\n[3] Scrolling...')
        for i in range(4):
            page.evaluate(f'window.scrollBy(0, {random.randint(300, 600)})')
            human_delay(1, 2)
        
        # Step 4: Find profiles
        print('\n[4] Looking for profiles...')
        
        # Try multiple selectors (LinkedIn changes these frequently)
        selectors = [
            'a[href*="/in/"]',
            '.reusable-search__result-container a',
            '.entity-result a',
            '.search-result__info a',
        ]
        
        profile_links = []
        for sel in selectors:
            links = page.query_selector_all(sel)
            # Filter for valid profile URLs
            for link in links:
                href = link.get_attribute('href')
                if href and '/in/' in href and 'linkedin.com' in href:
                    profile_links.append(href)
        
        # Remove duplicates
        profile_links = list(dict.fromkeys(profile_links))
        print(f'    Found {len(profile_links)} profile links')
        
        results = []
        
        # Process first 5 profiles
        for i, profile_url in enumerate(profile_links[:5]):
            print(f'\n[5.{i+1}] Processing: {profile_url[:60]}...')
            
            try:
                page.goto(profile_url)
                human_delay(3, 5)
                
                info = {
                    'name': '',
                    'headline': '',
                    'location': '',
                    'email': ''
                }
                
                # Get name
                try:
                    name_el = page.query_selector('h1')
                    if name_el:
                        info['name'] = name_el.inner_text().strip()
                except:
                    pass
                
                # Get headline
                try:
                    headline_el = page.query_selector('.text-body-medium, .pv-text-details__headline')
                    if headline_el:
                        info['headline'] = headline_el.inner_text().strip()
                except:
                    pass
                
                # Get location
                try:
                    location_el = page.query_selector('.pv-text-details__left-row-item, .text-body-small')
                    if location_el:
                        info['location'] = location_el.inner_text().strip()
                except:
                    pass
                
                # Try to get email (requires premium usually)
                try:
                    contact_link = page.query_selector('a[href*="/contact-info"]')
                    if contact_link:
                        contact_link.click()
                        human_delay(2, 3)
                        
                        email_el = page.query_selector('.ci-email a, .pv-contact-info__email-link')
                        if email_el:
                            info['email'] = email_el.inner_text().strip()
                except:
                    pass
                
                print(f'    Name: {info["name"]}')
                print(f'    Title: {info["headline"][:50] if info["headline"] else "N/A"}')
                print(f'    Email: {info["email"] if info["email"] else "N/A (need premium)"}')
                
                results.append(info)
                
            except Exception as e:
                print(f'    Error: {e}')
        
        print('\n' + '='*50)
        print(f'Total profiles processed: {len(results)}')
        print('='*50)
        
        for i, r in enumerate(results):
            print(f'\n{i+1}. {r["name"]}')
            print(f'   {r["headline"][:60] if r["headline"] else "No title"}')
            print(f'   {r["location"]}')
            print(f'   Email: {r["email"] if r["email"] else "N/A"}')
        
        input('\nPress Enter to close browser...')
        browser.close()


# ============================================
# OPTION 2: Selenium with Edge (STEALTH)
# ============================================
def run_with_selenium_stealth():
    """Use Selenium with advanced stealth settings"""
    print('='*50)
    print('Using Selenium with Stealth Settings')
    print('='*50)
    
    options = Options()
    
    # Critical stealth options
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-web-security')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--lang=en-US')
    
    # Use a real user profile if available
    # options.add_argument('--user-data-dir=C:/Users/YOUR_USER/AppData/Local/Microsoft/Edge/User Data/Default')
    
    # Exclude automation flags
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Edge(options=options)
    driver.set_page_load_timeout(60)
    
    # Execute stealth scripts
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'];
            });
            window.chrome = { runtime: {} };
        '''
    })
    
    # Human-like delays
    def human_delay():
        time.sleep(random.uniform(1, 3))
    
    print('\n[1] Opening LinkedIn...')
    driver.get('https://www.linkedin.com/')
    human_delay()
    
    if 'login' in driver.current_url:
        print('\n[!] Please login manually')
        input('Press Enter after logging in...')
    
    print('\n[2] Searching...')
    query = 'LED lights distributor Dubai'
    search_url = f'https://www.linkedin.com/search/results/people/?keywords={query.replace(" ", "%20")}'
    driver.get(search_url)
    human_delay()
    
    # Scroll
    for _ in range(4):
        driver.execute_script('window.scrollBy(0, random.randint(300, 600))')
        time.sleep(1)
    
    # Find profiles
    print('\n[3] Looking for profiles...')
    try:
        people = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/in/"]')
        print(f'    Found {len(people)} links')
    except Exception as e:
        print(f'    Error: {e}')
    
    driver.quit()
    print('\nDone!')


# ============================================
# MAIN
# ============================================
if __name__ == '__main__':
    print('Choose method:')
    print('1. Playwright (recommended - better stealth)')
    print('2. Selenium with Edge (stealth mode)')
    
    choice = input('Enter 1 or 2: ').strip()
    
    if choice == '1':
        run_with_playwright()
    else:
        run_with_selenium_stealth()
