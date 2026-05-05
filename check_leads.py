import requests

resp = requests.get('http://127.0.0.1:5000/api/v1/leads?per_page=20')
data = resp.json()

print(f"Total leads: {data.get('total', 0)}")
print()

for lead in data.get('items', [])[:15]:
    print(f"- Platform: {lead.get('platform')}")
    print(f"  Name: {lead.get('name', 'N/A')}")
    print(f"  URL: {lead.get('url', 'N/A')[:60]}")
    print(f"  Notes: {lead.get('notes', 'N/A')[:50]}")
    print()
