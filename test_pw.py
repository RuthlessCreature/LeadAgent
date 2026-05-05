import requests

# 使用 Playwright 测试
queries = [
    {'platform': 'importyeti', 'query': 'LED lights', 'type': 'importer'},
    {'platform': 'europages', 'query': 'LED lighting', 'type': 'company'},
]

search_data = {
    'queries': queries,
    'product_desc': 'LED lights',
    'auto_import': True
}

print("Testing Playwright search...")
print("Browser will open - watch the process!")
print("=" * 60)

resp = requests.post('http://127.0.0.1:5000/api/v1/search/run', json=search_data, timeout=300)
result = resp.json()

print(f"\nStatus: {result.get('status')}")
print(f"Results: {len(result.get('results', []))}")
print(f"Imported: {result.get('imported', 0)}")
print()

for r in result.get('results', [])[:20]:
    print(f"【{r['platform'].upper():12}】 {r['name'][:40]}")
    print(f"   Type: {r['type']}")
