import requests
import json

# 测试搜索
data = {
    "queries": [
        {"platform": "instagram", "query": "wine spirits distributor Armenia"},
        {"platform": "instagram", "query": "alcohol importer Armenia"},
        {"platform": "facebook", "query": "wine wholesaler Armenia"}
    ],
    "product_desc": "白酒批发商寻找亚美尼亚客户",
    "auto_import": True
}

try:
    resp = requests.post("http://127.0.0.1:5000/api/v1/search/run", json=data, timeout=180)
    result = resp.json()
    print('Status:', result.get('status'))
    print('Results:', len(result.get('results', [])))
    print('Imported:', result.get('imported', 0))
    print()
    for r in result.get('results', [])[:5]:
        print('-', r.get('platform'), ':', r.get('name'))
        print('  URL:', r.get('url', '')[:60])
        print('  Bio:', r.get('bio', '')[:80])
        print()
except Exception as e:
    print('Error:', str(e)[:300])
