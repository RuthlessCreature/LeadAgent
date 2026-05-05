import requests

# 测试 Stealth 搜索
queries = [
    {'platform': 'facebook', 'query': 'Islamic products distributor Saudi Arabia', 'type': 'page'},
    {'platform': 'instagram', 'query': 'prayer mats seller Dubai', 'type': 'people'},
]

search_data = {
    'queries': queries,
    'product_desc': 'HAJJ用品中东',
    'auto_import': True
}

print("Starting Stealth browser search...")
print("Browser will open - you can watch the process!")
print("=" * 50)

resp = requests.post('http://127.0.0.1:5000/api/v1/search/run', json=search_data, timeout=300)
result = resp.json()

print(f"\nStatus: {result.get('status')}")
print(f"Results: {len(result.get('results', []))}")
print(f"Imported: {result.get('imported', 0)}")
print()

for r in result.get('results', [])[:10]:
    print(f"【{r['platform'].upper()}】 {r['name']}")
    print(f"   URL: {r['url'][:60]}...")
    print(f"   Bio: {r['bio'][:80]}")
    print()
