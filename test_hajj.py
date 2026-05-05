import requests

# 测试 HAjj用品 中东
queries = [
    {'platform': 'google', 'query': 'Hajj supplies distributor Saudi Arabia', 'type': 'company'},
    {'platform': 'google', 'query': 'Islamic products importer UAE', 'type': 'company'},
    {'platform': 'google', 'query': 'prayer mats wholesaler Middle East', 'type': 'company'},
    {'platform': 'facebook', 'query': 'Hajj products wholesaler Dubai', 'type': 'page'},
    {'platform': 'instagram', 'query': 'Islamic prayer mats seller Saudi', 'type': 'people'},
    {'platform': 'alibaba', 'query': 'Hajj products buyer UAE', 'type': 'buyer'},
    {'platform': 'customs', 'query': 'prayer mats Saudi Arabia import', 'type': 'importer'},
]

search_data = {
    'queries': queries,
    'product_desc': 'HAJJ用品中东批发',
    'auto_import': True
}

print("Searching for Hajj products customers in Middle East...")
print("=" * 50)

resp = requests.post('http://127.0.0.1:5000/api/v1/search/run', json=search_data, timeout=120)
result = resp.json()
print(f"Status: {result.get('status')}")
print(f"Results found: {len(result.get('results', []))}")
print(f"Imported: {result.get('imported', 0)}")
print()

for r in result.get('results', []):
    print(f"【{r['platform'].upper()}】 {r['name']}")
    print(f"   URL: {r['url'][:70]}...")
    print(f"   Type: {r['type']}")
    print()
