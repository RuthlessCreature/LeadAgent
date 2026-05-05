"""
直接测试 LinkedIn 搜索
"""
import time
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# 初始化浏览器 - 非 headless
options = Options()
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_experimental_option('excludeSwitches', ['enable-automation'])
options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

driver = webdriver.Edge(options=options)
driver.set_page_load_timeout(30)

print("Opening LinkedIn...")

# 检查是否已登录
driver.get('https://www.linkedin.com/feed/')
time.sleep(3)

print("Current URL:", driver.current_url)

if 'login' in driver.current_url:
    print("Not logged in! Please login manually...")
    print("After login, I'll search automatically")
else:
    print("Logged in! Searching...")
    
    # 搜索
    query = "LED lights distributor"
    url = f"https://www.linkedin.com/search/results/people/?keywords={query.replace(' ', '%20')}"
    driver.get(url)
    time.sleep(5)
    
    # 滚动
    for _ in range(3):
        driver.execute_script("window.scrollBy(0, 500);")
        time.sleep(1)
    
    # 获取结果
    try:
        results = driver.find_elements(By.CSS_SELECTOR, '.reusable-search__result-container')
        print(f"Found {len(results)} results")
        
        for i, r in enumerate(results[:10]):
            try:
                name = r.find_element(By.CSS_SELECTOR, '.actor-name').text
                print(f"  {i+1}. {name}")
            except:
                pass
    except Exception as e:
        print("Error:", e)

print("\nDone. Close browser manually or press Enter...")
input()
driver.quit()
