from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
import time
import os

print('Testing LinkedIn search...')

# Create a temp profile
temp_profile = r"C:\Users\Georgij Xe\AppData\Local\Temp\ selenium_profile"
os.makedirs(temp_profile, exist_ok=True)

options = Options()
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument(f'--user-data-dir={temp_profile}')

try:
    driver = webdriver.Edge(options=options)
    driver.set_page_load_timeout(30)
    
    print('Opening LinkedIn...')
    driver.get('https://www.linkedin.com/')
    time.sleep(5)
    
    if 'login' in driver.current_url:
        print('NOT LOGGED IN!')
        print('Please login manually in the browser window.')
        print('I will check again in 60 seconds...')
        
        # Wait for login
        for i in range(6):
            time.sleep(10)
            driver.get('https://www.linkedin.com/feed/')
            time.sleep(2)
            if 'login' not in driver.current_url:
                print('Logged in!')
                break
            print(f'Waiting... ({i+1}/6)')
        else:
            print('Still not logged in.')
            driver.quit()
            exit()
    
    print('Logged in!')
    
    # Search
    query = 'LED lights distributor Dubai'
    print(f'Searching: {query}')
    driver.get(f'https://www.linkedin.com/search/results/people/?keywords={query.replace(" ", "%20")}')
    time.sleep(5)
    
    # Get results
    people = driver.find_elements(By.CSS_SELECTOR, '.reusable-search__result-container')
    print(f'Found {len(people)} results')
    
    if people:
        # Click first result
        print('Clicking first result...')
        link = people[0].find_element(By.CSS_SELECTOR, 'a')
        href = link.get_attribute('href')
        driver.get(href)
        time.sleep(3)
        
        # Get name
        try:
            name = driver.find_element(By.CSS_SELECTOR, 'h1').text
            print(f'Name: {name}')
        except:
            print('No name found')
        
        # Get headline
        try:
            headline = driver.find_element(By.CSS_SELECTOR, '.text-body-medium').text
            print(f'Headline: {headline}')
        except:
            print('No headline')
        
        # Get contact info
        try:
            contact = driver.find_element(By.XPATH, "//a[contains(@href, '/contact-info')]")
            contact.click()
            time.sleep(2)
            
            # Email
            try:
                email = driver.find_element(By.CSS_SELECTOR, '.ci-email a')
                print(f'Email: {email.text}')
            except:
                print('No email found')
        except:
            print('No contact button')
    
    driver.quit()
    print('Done!')
    
except Exception as e:
    print(f'Error: {e}')
