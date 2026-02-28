# Lead Agent (Web + FastAPI)

This project implements a prompt-driven B2B lead generation system with:

- `FastAPI` backend for parsing, search orchestration, scoring, deduplication, outreach, dashboard, and integrations.
- `Web frontend` (plain HTML/CSS/JS) for operating the full workflow in a browser.

## Quick Start

1. Install dependencies:

```bash
pip install -r requirements.txt
```

If Playwright cannot find a local browser on your machine, run:

```bash
python -m playwright install chromium
```

2. Run API + frontend:

```bash
uvicorn main:app --reload --app-dir backend
```

3. Open:

```text
http://127.0.0.1:8000/
```

## Project Structure

```text
backend/
  main.py
  app/
    main.py
    models.py
    store.py
    services/
frontend/
  index.html
  app.js
  styles.css
```

## API Coverage (Prompt Modules)

- Input layer:
  - Product parsing: `POST /api/v1/input/parse-product`
  - ICP normalize: `POST /api/v1/input/icp/normalize`
- Search & execution:
  - Multi-platform search: `POST /api/v1/search/run`
  - Task queue/status: `GET /api/v1/tasks`
- Scoring & filtering:
  - Lead scoring: `POST /api/v1/scoring/score`
  - Deduplicate: `POST /api/v1/leads/deduplicate`
  - Strategy engine: `POST /api/v1/strategy/next`
  - Intent/industry/role classification: `POST /api/v1/classify`
- Lead operations:
  - Lead list: `GET /api/v1/leads`
  - Lead card: `GET /api/v1/leads/{lead_id}/card`
  - Export CSV/PDF: `GET /api/v1/leads/export?format=csv|pdf`
- Outreach:
  - Template generation (EN/ES/FR/DE/CN): `POST /api/v1/outreach/templates`
  - Event tracking: `POST /api/v1/outreach/events`
  - Event stats: `GET /api/v1/outreach/stats`
  - Notifications: `GET /api/v1/notifications`
- Integration/governance:
  - CRM export/sync: `POST /api/v1/crm/export`
  - Dashboard metrics: `GET /api/v1/dashboard`
  - Permission check: `POST /api/v1/permissions/check`
  - Compliance scan: `POST /api/v1/compliance/scan`
  - Ext endpoints: `/api/v1/ext/*`

## Notes

- Search now uses live web results (DuckDuckGo with Bing fallback) with platform-scoped queries
  like `site:linkedin.com`, `site:facebook.com`, `site:tiktok.com`, etc.
- Default mode is people discovery (`SEARCH_TARGET=people`), which prioritizes profile URLs
  such as LinkedIn `/in/`, YouTube `@handle`, and TikTok `@handle`.
- Set `SEARCH_MODE=mock` to use the deterministic local dataset for offline/dev testing.
- Optional env vars for search responsiveness:
  - `SEARCH_MODE=live|mock` (default `live`)
  - `SEARCH_TARGET=people|company` (default `people`)
  - `SEARCH_DRIVER=playwright|http` (default `playwright`)
  - `SEARCH_TIMEOUT=8` (seconds per upstream request)
  - `SEARCH_QUERY_VARIANTS=2` (how many query variants per platform)
- Connector endpoints for HubSpot/Zoho/Salesforce are scaffolded and can be replaced with real SDK calls.
- In `playwright` mode the backend first tries local Edge/Chrome browser channels; if neither is usable,
  install Playwright Chromium (`python -m playwright install chromium`).
