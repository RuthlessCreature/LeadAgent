import requests
import json

queries = [
    {'platform': 'linkedin', 'query': 'LED lights distributor', 'type': 'people'},
]

search_data = {
    'queries': queries,
    'product_desc': 'LED lights',
    'auto_import': True
}

print("Testing LinkedIn search...")
print("=" * 50)

try:
    resp = requests.post('http://127.0.0.1:5000/api/v1/search/run', json=search_data, timeout=300)
    result = resp.json()
    print('Status:', result.get('status'))
    print('Results:', len(result.get('results', [])))
    print('Imported:', result.get('imported', 0))
    
    for r in result.get('results', [])[:10]:
        print(f"- {r['platform']}: {r['name'][:40]}")
        print(f"  URL: {r['url'][:50]}...")
        print(f"  Bio: {r['bio'][:60]}...")
        print()
except Exception as e:
    print('Error:', str(e)[:200])
