import requests

# 测试新数据源
queries = [
    {'platform': 'importyeti', 'query': 'prayer mats', 'type': 'importer'},
    {'platform': 'europages', 'query': 'Islamic products wholesale', 'type': 'company'},
    {'platform': 'tradeindia', 'query': 'Hajj supplies importer', 'type': 'importer'},
    {'platform': 'alibaba', 'query': 'LED lights buyer', 'type': 'buyer'},
]

search_data = {
    'queries': queries,
    'product_desc': 'HAJJ用品中东',
    'auto_import': True
}

print("Testing B2B data sources...")
print("=" * 50)

resp = requests.post('http://127.0.0.1:5000/api/v1/search/run', json=search_data, timeout=180)
result = resp.json()

print(f"Status: {result.get('status')}")
print(f"Results: {len(result.get('results', []))}")
print(f"Imported: {result.get('imported', 0)}")
print()

for r in result.get('results', [])[:20]:
    print(f"【{r['platform'].upper()}】 {r['name']}")
    print(f"   URL: {r['url'][:60]}...")
    print(f"   Type: {r['type']}")
    print()
