import requests
import json

# 先测试解析
data = {
    "description": "我是白酒批发商，寻找亚美尼亚的经销商和批发商"
}

try:
    resp = requests.post("http://127.0.0.1:5000/api/v1/search/parse", json=data, timeout=30)
    result = resp.json()
    print('=== Parse Result ===')
    print('Product:', result['result']['product_name'])
    print('Roles:', result['result']['target_role'])
    print('Queries:', len(result['result']['search_queries']))
    for q in result['result']['search_queries'][:4]:
        print(f"  - {q['platform']}: {q['query']}")
except Exception as e:
    print('Parse Error:', str(e))
