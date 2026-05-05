# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
import time

print('='*50)
print('LinkedIn Debug Test')
print('='*50)

options = Options()
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')

driver = webdriver.Edge(options=options)
driver.set_page_load_timeout(30)

print('\n[1] Opening LinkedIn...')
driver.get('https://www.linkedin.com/')
time.sleep(5)

if 'login' in driver.current_url:
    print('Not logged in! Please login first.')
    driver.quit()
    exit()

print('Logged in!')

# Go directly to search
query = 'LED lights distributor Dubai'
search_url = f'https://www.linkedin.com/search/results/people/?keywords={query.replace(" ", "%20")}'
print(f'\n[2] Going to: {search_url}')
driver.get(search_url)
time.sleep(10)

print(f'\nCurrent URL: {driver.current_url}')
print(f'Page title: {driver.title}')

# Check for any blocks
if 'challenge' in driver.current_url or 'captcha' in driver.current_url.lower():
    print('\n[!] LinkedIn is showing a challenge/captcha!')
    print('Please solve it manually in the browser.')
    input('Press Enter after solving...')

# Try scrolling
print('\n[3] Scrolling...')
for i in range(5):
    driver.execute_script('window.scrollBy(0, 300);')
    time.sleep(1)

time.sleep(3)

# Get page source length
print(f'\n[4] Page source length: {len(driver.page_source)}')

# Try to find results with different selectors
selectors = [
    '.reusable-search__result-container',
    '.entity-result',
    '.search-result',
    '.results-list',
    '#people',
    '.pb2',
    '.app-aware-link'
]

for sel in selectors:
    els = driver.find_elements(By.CSS_SELECTOR, sel)
    if els:
        print(f'  {sel}: {len(els)} elements')

# Try XPaths
xpaths = [
    '//li[contains(@class, "result")]',
    '//div[contains(@class, "entity-result")]',
    '//a[contains(@href, "/in/")]'
]

for xp in xpaths:
    els = driver.find_elements(By.XPATH, xp)
    if els:
        print(f'  XPath {xp}: {len(els)} elements')

# Try to find any links with /in/
print('\n[5] Looking for profile links...')
links = driver.find_elements(By.XPATH, '//a[contains(@href, "/in/")]')
print(f'  Found {len(links)} links with /in/')

if links:
    print(f'  First link: {links[0].get_attribute("href")}')
    
    # Click first link
    print('\n[6] Clicking first profile...')
    links[0].click()
    time.sleep(5)
    
    # Get profile info
    try:
        name = driver.find_element(By.CSS_SELECTOR, 'h1').text
        print(f'  Name: {name}')
    except:
        print('  No name found')
    
    try:
        headline = driver.find_element(By.CSS_SELECTOR, '.text-body-medium').text
        print(f'  Headline: {headline}')
    except:
        print('  No headline found')
    
    # Try contact info
    try:
        contact = driver.find_element(By.XPATH, "//a[contains(@href, '/contact-info')]")
        contact.click()
        time.sleep(2)
        
        try:
            email = driver.find_element(By.CSS_SELECTOR, '.ci-email a')
            print(f'  Email: {email.text}')
        except:
            print('  No email found')
    except:
        print('  No contact button')

else:
    # Save screenshot
    driver.save_screenshot('debug.png')
    print('\nNo profile links found!')
    print('Screenshot saved to debug.png')

driver.quit()
print('\nDone.')
