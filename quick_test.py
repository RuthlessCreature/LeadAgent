"""
直接测试 LinkedIn 搜索
"""
import time
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By

options = Options()
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')

driver = webdriver.Edge(options=options)
driver.set_page_load_timeout(30)

print("Opening LinkedIn...")

# 检查登录
driver.get('https://www.linkedin.com/feed/')
time.sleep(3)

if 'login' in driver.current_url:
    print("NOT LOGGED IN! Please login first in the browser.")
    input("After logging in, press Enter...")
else:
    print("Logged in! Searching...")
    
    # 搜索
    query = "LED lights distributor"
    driver.get(f"https://www.linkedin.com/search/results/people/?keywords={query.replace(' ', '%20')}")
    time.sleep(5)
    
    # 滚动
    for _ in range(3):
        driver.execute_script("window.scrollBy(0, 500);")
        time.sleep(1)
    
    # 获取结果
    try:
        people = driver.find_elements(By.CSS_SELECTOR, '.reusable-search__result-container')
        print(f"Found {len(people)} results")
        
        # 点击第一个
        if people:
            print("Clicking first result...")
            link = people[0].find_element(By.CSS_SELECTOR, 'a')
            href = link.get_attribute('href')
            print(f"Profile URL: {href}")
            
            driver.get(href)
            time.sleep(3)
            
            # 获取姓名
            try:
                name = driver.find_element(By.CSS_SELECTOR, 'h1').text
                print(f"Name: {name}")
            except:
                print("No name found")
            
            # 获取职位
            try:
                headline = driver.find_element(By.CSS_SELECTOR, '.text-body-medium').text
                print(f"Headline: {headline}")
            except:
                print("No headline")
            
            # 获取邮箱 - 点击联系信息
            try:
                contact = driver.find_element(By.XPATH, "//a[contains(@href, '/contact-info')]")
                contact.click()
                time.sleep(2)
                
                # 找邮箱
                try:
                    email = driver.find_element(By.CSS_SELECTOR, '.ci-email a, .pv-contact-info__email-link')
                    print(f"Email: {email.text}")
                except:
                    print("No email found")
            except:
                print("No contact info button")
                
    except Exception as e:
        print(f"Error: {e}")

print("\nDone. Close browser or press Enter...")
input()
driver.quit()
