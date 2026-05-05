# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
import time

print('='*50)
print('LinkedIn Auto Search Test')
print('='*50)

# Use default profile (non-headless so user can see)
options = Options()
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')

driver = webdriver.Edge(options=options)
driver.set_page_load_timeout(30)

print('\n[1] Opening LinkedIn...')
driver.get('https://www.linkedin.com/')
time.sleep(5)

# Check if logged in
if 'login' in driver.current_url:
    print('\n[!] Not logged in!')
    print('Please login manually in the browser window.')
    print('Script will continue after login...\n')
    
    # Wait for login
    max_wait = 180
    start_time = time.time()
    while 'login' in driver.current_url:
        time.sleep(5)
        if time.time() - start_time > max_wait:
            print('\nTimeout - please run script again after logging in')
            driver.quit()
            exit()
        driver.get('https://www.linkedin.com/')
        time.sleep(3)
        print(f'  Waiting... ({int(time.time() - start_time)}s)')

print('\n[OK] Logged in!')

# Now search
print('\n[2] Searching...')
search_queries = [
    'LED lights distributor Dubai',
    'LED lighting wholesaler UAE'
]

all_results = []

for query in search_queries:
    print(f'\nQuery: {query}')
    
    search_url = f'https://www.linkedin.com/search/results/people/?keywords={query.replace(" ", "%20")}'
    driver.get(search_url)
    time.sleep(8)
    
    # Scroll
    for _ in range(3):
        driver.execute_script('window.scrollBy(0, 500);')
        time.sleep(1)
    
    time.sleep(3)
    
    # Find results
    people = driver.find_elements(By.CSS_SELECTOR, '.reusable-search__result-container, li.entity-result')
    print(f'  Found {len(people)} results')
    
    # Process first 2 results
    for i, person in enumerate(people[:2]):
        try:
            link = person.find_element(By.CSS_SELECTOR, 'a')
            profile_url = link.get_attribute('href')
            
            if not profile_url or '/in/' not in profile_url:
                continue
                
            print(f'\n  [{i+1}] Opening: {profile_url[:50]}...')
            
            driver.execute_script(f'window.open("{profile_url}");')
            driver.switch_to.window(driver.window_handles[-1])
            time.sleep(3)
            
            info = {'name': '', 'headline': '', 'location': '', 'email': ''}
            
            # Name
            try:
                info['name'] = driver.find_element(By.CSS_SELECTOR, 'h1').text.strip()
            except:
                pass
            
            # Headline
            try:
                info['headline'] = driver.find_element(By.CSS_SELECTOR, '.text-body-medium').text.strip()
            except:
                pass
            
            # Location
            try:
                info['location'] = driver.find_element(By.CSS_SELECTOR, '.pv-text-details__left-row-item').text.strip()
            except:
                pass
            
            # Contact info
            try:
                contact_btn = driver.find_element(By.XPATH, "//a[contains(@href, '/contact-info')]")
                contact_btn.click()
                time.sleep(2)
                
                try:
                    email = driver.find_element(By.CSS_SELECTOR, '.ci-email a')
                    info['email'] = email.text.strip()
                except:
                    pass
            except:
                pass
            
            print(f'    Name: {info["name"]}')
            print(f'    Title: {info["headline"][:50] if info["headline"] else "N/A"}')
            print(f'    Location: {info["location"]}')
            print(f'    Email: {info["email"] if info["email"] else "N/A (need premium)"}')
            
            all_results.append(info)
            
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
            time.sleep(2)
            
        except Exception as e:
            print(f'    Error: {e}')
            try:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
            except:
                pass
    
    time.sleep(3)

print('\n' + '='*50)
print(f'Done! Found {len(all_results)} contacts')
print('='*50)

for i, r in enumerate(all_results):
    print(f'\n{i+1}. {r["name"]}')
    print(f'   {r["headline"][:60] if r["headline"] else "No title"}')
    print(f'   {r["location"]}')
    print(f'   Email: {r["email"] if r["email"] else "N/A"}')

driver.quit()
print('\nBrowser closed.')
