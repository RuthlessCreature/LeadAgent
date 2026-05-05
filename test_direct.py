import sys
sys.path.insert(0, 'E:/github/leadagent/backend')

from app.services.search import LoggedInSearcher

print("Testing search...")
searcher = LoggedInSearcher(headless=False)

queries = [
    {"platform": "instagram", "query": "wine distributor Armenia"},
    {"platform": "facebook", "query": "wine wholesaler Armenia"}
]

try:
    results = searcher.search_multi(queries)
    print(f"Found {len(results)} results")
    for r in results[:5]:
        print(f"- {r.get('platform')}: {r.get('name')}")
        print(f"  URL: {r.get('url', '')[:60]}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    searcher.close()
