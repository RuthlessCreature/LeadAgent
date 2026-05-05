"""
测试直接调用 Searcher
"""
import sys
sys.path.insert(0, 'E:/github/leadagent/backend')

from app.services.search import SyncSearcher

print("Testing SyncSearcher...")

searcher = SyncSearcher()

queries = [
    {'platform': 'europages', 'query': 'LED lights', 'type': 'company'},
]

print("Calling search_multi...")
results = searcher.multi_search(queries)

print(f"Results: {len(results)}")
for r in results[:5]:
    print(f"  - {r['platform']}: {r['name']}")
