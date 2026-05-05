import requests

# 按优先级测试数据源
queries = [
    {'platform': 'importyeti', 'query': 'LED lights', 'type': 'importer'},
    {'platform': 'europages', 'query': 'LED lighting wholesale', 'type': 'company'},
    {'platform': 'buzzfile', 'query': 'lighting distributor', 'type': 'company'},
    {'platform': 'tradeindia', 'query': 'LED importer', 'type': 'importer'},
    {'platform': 'globalbuyers', 'query': 'LED lights buyer', 'type': 'buyer'},
]

search_data = {
    'queries': queries,
    'product_desc': 'LED lights',
    'auto_import': True
}

print("Testing B2B data sources (priority order)...")
print("=" * 60)

resp = requests.post('http://127.0.0.1:5000/api/v1/search/run', json=search_data, timeout=300)
result = resp.json()

print(f"\nStatus: {result.get('status')}")
print(f"Results: {len(result.get('results', []))}")
print(f"Imported: {result.get('imported', 0)}")
print()

for r in result.get('results', [])[:25]:
    print(f"【{r['platform'].upper():12}】 {r['name'][:40]}")
    print(f"   Type: {r['type']}")
    print(f"   URL: {r['url'][:50]}...")
    print()
