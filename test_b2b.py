import requests

# 测试 Google + B2B 搜索
queries = [
    {'platform': 'google', 'query': 'Islamic prayer mats distributor Saudi Arabia', 'type': 'company'},
    {'platform': 'google', 'query': 'Hajj products importer UAE', 'type': 'company'},
    {'platform': 'customs', 'query': 'prayer mats Saudi Arabia import', 'type': 'importer'},
    {'platform': 'alibaba', 'query': 'Islamic products buyer UAE', 'type': 'buyer'},
    {'platform': 'tradekey', 'query': 'wholesale Hajj supplies', 'type': 'company'},
]

search_data = {
    'queries': queries,
    'product_desc': 'HAJJ用品中东',
    'auto_import': True
}

print("Testing Google + B2B + Customs search...")
print("=" * 50)

resp = requests.post('http://127.0.0.1:5000/api/v1/search/run', json=search_data, timeout=120)
result = resp.json()

print(f"Status: {result.get('status')}")
print(f"Results: {len(result.get('results', []))}")
print(f"Imported: {result.get('imported', 0)}")
print()

for r in result.get('results', [])[:15]:
    print(f"【{r['platform'].upper()}】 {r['name']}")
    print(f"   URL: {r['url'][:70]}...")
    print(f"   Type: {r['type']}")
    print()
