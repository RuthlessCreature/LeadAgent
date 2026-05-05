import requests

# 测试 Selenium 真实点击搜索
queries = [
    {'platform': 'google', 'query': 'Islamic products distributor Saudi Arabia', 'type': 'company'},
    {'platform': 'instagram', 'query': 'Islamic prayer mats seller Dubai', 'type': 'people'},
]

search_data = {
    'queries': queries,
    'product_desc': 'HAJJ用品中东',
    'auto_import': True
}

print("Starting Selenium browser search...")
print("This will open browser and click through to get real data")
print("=" * 50)

resp = requests.post('http://127.0.0.1:5000/api/v1/search/run', json=search_data, timeout=300)
result = resp.json()

print(f"Status: {result.get('status')}")
print(f"Results: {len(result.get('results', []))}")
print(f"Imported: {result.get('imported', 0)}")
print()

for r in result.get('results', [])[:10]:
    print(f"【{r['platform'].upper()}】 {r['name']}")
    print(f"   URL: {r['url'][:60]}...")
    print(f"   Info: {r['bio'][:80]}...")
    print()
