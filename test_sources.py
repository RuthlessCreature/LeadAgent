import requests

# 测试更多数据源
queries = [
    {'platform': 'google', 'query': 'wine importer Armenia', 'type': 'company'},
    {'platform': 'google', 'query': 'spirits distributor UAE', 'type': 'company'},
    {'platform': 'alibaba', 'query': 'wine buyer', 'type': 'buyer'},
    {'platform': 'customs', 'query': 'alcohol Armenia', 'type': 'importer'},
]

search_data = {
    'queries': queries,
    'product_desc': '白酒',
    'auto_import': True
}

resp = requests.post('http://127.0.0.1:5000/api/v1/search/run', json=search_data, timeout=120)
result = resp.json()
print('Status:', result.get('status'))
print('Results:', len(result.get('results', [])))
print('Imported:', result.get('imported', 0))
print()

for r in result.get('results', [])[:10]:
    print(f"- Platform: {r['platform']}")
    print(f"  Name: {r['name']}")
    print(f"  URL: {r['url'][:60]}...")
    print(f"  Type: {r['type']}")
    print()
