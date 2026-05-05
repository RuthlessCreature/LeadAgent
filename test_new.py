import requests
import json

# 测试解析
data = {'description': '我是白酒批发商，寻找亚美尼亚的经销商'}
resp = requests.post('http://127.0.0.1:5000/api/v1/search/parse', json=data, timeout=30)
result = resp.json()
print('=== Parse ===')
print('Product:', result['result']['product_name'])
print('Queries:')
for q in result['result']['search_queries'][:6]:
    print(f"  {q['platform']}: {q['query']}")

print()
print('=== Testing Search ===')

# 测试搜索
queries = result['result']['search_queries'][:4]
search_data = {
    'queries': queries,
    'product_desc': '白酒批发',
    'auto_import': True
}
resp2 = requests.post('http://127.0.0.1:5000/api/v1/search/run', json=search_data, timeout=120)
result2 = resp2.json()
print('Status:', result2.get('status'))
print('Results:', len(result2.get('results', [])))
print('Imported:', result2.get('imported', 0))

for r in result2.get('results', [])[:5]:
    print(f"  - {r['platform']}: {r['name']}")
