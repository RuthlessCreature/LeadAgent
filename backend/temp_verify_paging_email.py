import os
import json
from app.services.search import LinkedInSearcher

os.environ['LINKEDIN_USER_DATA_DIR'] = r'E:\GitHub\LeadAgent\data\linkedin_edge_profile_v3'
os.environ['LINKEDIN_MAX_QUERIES'] = '1'
os.environ['LINKEDIN_MAX_PROFILES_PER_QUERY'] = '12'
os.environ['LINKEDIN_MAX_PAGES_PER_QUERY'] = '2'
os.environ['LINKEDIN_SCROLL_ROUNDS'] = '1'
os.environ['LINKEDIN_DELAY_MIN'] = '0.8'
os.environ['LINKEDIN_DELAY_MAX'] = '1.4'
os.environ['LINKEDIN_MANUAL_LOGIN_WAIT_SECONDS'] = '6'

q = [{'platform':'linkedin','query':'Hajj supplies wholesaler Dubai UAE','type':'people'}]
rows = LinkedInSearcher().search_multi(q)
print('COUNT', len(rows))
print('EMAIL_COUNT', sum(1 for r in rows if r.get('email')))
print(json.dumps(rows[:12], ensure_ascii=False))
