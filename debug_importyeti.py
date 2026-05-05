import httpx
from bs4 import BeautifulSoup

# 测试 ImportYeti 网页结构
url = "https://www.importyeti.com/company-search?q=LED"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

resp = httpx.get(url, headers=headers, timeout=15)
print(f"Status: {resp.status_code}")
print(f"Length: {len(resp.text)}")

soup = BeautifulSoup(resp.text, 'html.parser')

# 查找公司元素
print("\n=== Looking for company items ===")
items = soup.select('.company-item, .company-card, .result-item, [class*="company"]')
print(f"Found items: {len(items)}")

# 打印页面结构
print("\n=== Page structure (first 2000 chars) ===")
print(soup.prettify()[:2000])
