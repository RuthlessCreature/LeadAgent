# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time

print('='*50)
print('LinkedIn Search Test - Using Search Box')
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

# Go to homepage first, then use search box
print('\n[2] Using search box to search...')
time.sleep(3)

# Find search box - LinkedIn has a global search box
try:
    search_box = driver.find_element(By.CSS_SELECTOR, '.search-global-typeahead__input, #global-nav-search')
    search_box.clear()
    search_box.send_keys('LED lights distributor Dubai')
    search_box.send_keys(Keys.RETURN)
    print('  Search submitted!')
except Exception as e:
    print(f'  Error with search box: {e}')
    # Try alternative
    try:
        search_box = driver.find_element(By.XPATH, '//input[contains(@placeholder, "Search")]')
        search_box.clear()
        search_box.send_keys('LED lights distributor Dubai')
        search_box.send_keys(Keys.RETURN)
        print('  Search submitted (alt)!')
    except Exception as e2:
        print(f'  Alt error: {e2}')

time.sleep(10)

print(f'\n[3] Current URL: {driver.current_url}')
print(f'    Page title: {driver.title}')

# Check for login redirect
if 'login' in driver.current_url:
    print('\n[!] Redirected to login!')
    print('Please login in browser, then script will continue...')
    
    max_wait = 180
    start = time.time()
    while 'login' in driver.current_url:
        time.sleep(5)
        if time.time() - start > max_wait:
            driver.quit()
            exit()
        print(f'  Waiting... ({int(time.time()-start)}s)')
    
    # Now try search again
    print('\n[4] Retrying search...')
    driver.get('https://www.linkedin.com/feed/')
    time.sleep(5)
    
    try:
        search_box = driver.find_element(By.CSS_SELECTOR, '.search-global-typeahead__input')
        search_box.send_keys('LED lights distributor Dubai')
        search_box.send_keys(Keys.RETURN)
    except:
        pass
    
    time.sleep(10)

print(f'\n[5] Current URL: {driver.current_url}')

# Scroll
for i in range(3):
    driver.execute_script('window.scrollBy(0, 300);')
    time.sleep(1)

time.sleep(3)

# Find profile links
links = driver.find_elements(By.XPATH, '//a[contains(@href, "/in/")]')
print(f'\n[6] Found {len(links)} profile links')

if links:
    print('\n[7] Clicking first profile...')
    links[0].click()
    time.sleep(5)
    
    try:
        name = driver.find_element(By.CSS_SELECTOR, 'h1').text
        print(f'  Name: {name}')
    except:
        print('  No name')
    
    try:
        headline = driver.find_element(By.CSS_SELECTOR, '.text-body-medium').text
        print(f'  Title: {headline[:80]}')
    except:
        print('  No title')
    
    # Contact
    try:
        contact = driver.find_element(By.XPATH, "//a[contains(@href, '/contact-info')]")
        contact.click()
        time.sleep(2)
        
        try:
            email = driver.find_element(By.CSS_SELECTOR, '.ci-email a')
            print(f'  Email: {email.text}')
        except:
            print('  No email')
    except:
        print('  No contact')
else:
    print('No profile links found!')
    driver.save_screenshot('search_result.png')
    print('Screenshot saved')

driver.quit()
print('\nDone.')
