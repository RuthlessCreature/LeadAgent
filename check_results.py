import requests
resp = requests.get('http://127.0.0.1:5000/api/v1/leads?per_page=20')
data = resp.json()
print(f'Total: {data["total"]}')
print()
for lead in data['items'][:15]:
    print(f"- {lead['platform']}: {lead['name']}")
    print(f"  URL: {lead['url'][:60]}...")
