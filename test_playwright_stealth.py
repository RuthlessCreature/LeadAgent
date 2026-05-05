# -*- coding: utf-8 -*-
"""
Playwright-based LinkedIn scraper with stealth settings
Testing if it can bypass LinkedIn detection
"""
from playwright.sync_api import sync_playwright
import time

print('='*50)
print('LinkedIn Test with Playwright (Stealth Mode)')
print('='*50)

def run():
    with sync_playwright() as p:
        # Launch browser with more realistic settings
        browser = p.chromium.launch(
            headless=False,  # Show browser for visibility
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
            ]
        )
        
        # Create context with realistic settings
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/New_York',
            permissions=['geolocation'],
            # Extra headers to look more like real browser
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            }
        )
        
        # Add stealth script to hide automation
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            window.chrome = {};
        """)
        
        page = context.new_page()
        
        print('\n[1] Opening LinkedIn...')
        page.goto('https://www.linkedin.com/', timeout=30000)
        time.sleep(5)
        
        # Check if login required
        if 'login' in page.url:
            print('\n[!] Not logged in!')
            print('Please login manually in the browser window.')
            print('Script will detect login and continue...\n')
            
            # Wait for login
            max_wait = 180
            start_time = time.time()
            while 'login' in page.url:
                time.sleep(5)
                if time.time() - start_time > max_wait:
                    print('\nTimeout - please run script again after logging in')
                    browser.close()
                    return
                page.goto('https://www.linkedin.com/')
                time.sleep(3)
                print(f'  Waiting... ({int(time.time() - start_time)}s)')
        
        print('\n[OK] Logged in!')
        
        # Check for any challenges
        if 'challenge' in page.url or 'captcha' in page.url.lower():
            print('\n[!] LinkedIn showing challenge!')
            input('Please solve manually, then press Enter...')
        
        # Test search
        print('\n[2] Testing search...')
        query = 'LED lights distributor Dubai'
        search_url = f'https://www.linkedin.com/search/results/people/?keywords={query.replace(" ", "%20")}'
        page.goto(search_url)
        time.sleep(8)
        
        # Check current URL
        print(f'    URL after search: {page.url}')
        
        # Scroll to simulate human behavior
        print('\n[3] Scrolling...')
        for i in range(3):
            page.evaluate('window.scrollBy(0, 500)')
            time.sleep(1)
        
        time.sleep(3)
        
        # Check page content
        content = page.content()
        print(f'    Page content length: {len(content)}')
        
        # Try to find profile links
        print('\n[4] Looking for profile links...')
        try:
            # Try different selectors for LinkedIn search results
            profile_links = page.query_selector_all('a[href*="/in/"]')
            print(f'    Found {len(profile_links)} profile links')
            
            if profile_links:
                first_link = profile_links[0].get_attribute('href')
                print(f'    First link: {first_link[:80]}...')
                
                # Click first profile
                print('\n[5] Clicking first profile...')
                profile_links[0].click()
                time.sleep(5)
                
                # Get profile info
                try:
                    name = page.query_selector('h1')
                    if name:
                        print(f'    Name: {name.inner_text()}')
                except Exception as e:
                    print(f'    Error getting name: {e}')
                
                try:
                    headline = page.query_selector('.text-body-medium, .pv-text-details__headline')
                    if headline:
                        print(f'    Headline: {headline.inner_text()[:80]}')
                except Exception as e:
                    print(f'    Error getting headline: {e}')
                    
            else:
                print('    No profile links found - possible detection!')
                page.screenshot(path='debug_playwright.png')
                print('    Screenshot saved to debug_playwright.png')
                
        except Exception as e:
            print(f'    Error: {e}')
            page.screenshot(path='debug_playwright_error.png')
        
        print('\n' + '='*50)
        print('Test complete!')
        print('='*50)
        
        input('Press Enter to close browser...')
        browser.close()

if __name__ == '__main__':
    run()
