from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
import time
import os

print('Testing LinkedIn search...')

# Create a temp profile
temp_profile = r"C:\Users\Georgij Xe\AppData\Local\Temp\ selenium_profile2"
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
        exit()
    
    print('Logged in!')
    
    # Search
    query = 'LED lights distributor Dubai'
    print(f'Searching: {query}')
    driver.get(f'https://www.linkedin.com/search/results/people/?keywords={query.replace(" ", "%20")}')
    time.sleep(8)
    
    # Scroll to load more results
    print('Scrolling...')
    for i in range(5):
        driver.execute_script('window.scrollBy(0, 500);')
        time.sleep(1)
    
    time.sleep(3)
    
    # Try different selectors
    selectors = [
        '.reusable-search__result-container',
        '.entity-result',
        '.search-result__info',
        'li.reusable-search__result-item'
    ]
    
    people = []
    for sel in selectors:
        people = driver.find_elements(By.CSS_SELECTOR, sel)
        if people:
            print(f'Found {len(people)} results with: {sel}')
            break
    
    if not people:
        print('No results found!')
        # Take a screenshot
        driver.save_screenshot('linkedin_search.png')
        print('Screenshot saved to linkedin_search.png')
        
        # Print page source for debugging
        print('Page title:', driver.title)
        print('Current URL:', driver.current_url)
    else:
        # Click first result
        print('Clicking first result...')
        link = people[0].find_element(By.CSS_SELECTOR, 'a')
        href = link.get_attribute('href')
        print(f'Profile URL: {href}')
        driver.get(href)
        time.sleep(5)
        
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
            time.sleep(3)
            
            # Email
            try:
                email = driver.find_element(By.CSS_SELECTOR, '.ci-email a')
                print(f'Email: {email.text}')
            except:
                print('No email found')
                
            # Phone
            try:
                phone = driver.find_element(By.CSS_SELECTOR, '.ci-phone')
                print(f'Phone: {phone.text}')
            except:
                print('No phone found')
                
        except Exception as e:
            print(f'Contact error: {e}')
    
    driver.quit()
    print('Done!')
    
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
