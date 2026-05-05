# LeadAgent

LeadAgent is now positioned as a commercial lead operations workspace for small sales teams, agencies, and export operators.

The product focus is:

- find target accounts from compliant sources
- find supplier and goods sources from marketplaces and supplier websites
- score and review leads in one place
- keep source provenance visible
- activate outreach only when data is owned, public, or licensed

## What changed

This repository previously mixed experimental scraping flows with partial product code.

The primary product path is now:

1. define a product and ICP
2. run a demo sourcing pipeline
3. crawl public business websites and directory pages
4. import customer-owned lead data
5. review source, consent, verification, and score
6. export or sync the approved lead set

The FastAPI app in `backend/app/main.py` is the primary runtime.

## Capability boundary

LeadAgent does **not** currently support a fully automatic `arbitrary product description -> customer list` flow.

What it can do today:

- score and review leads once a product profile, ICP, or owned list exists
- discover public company URLs when the operator provides explicit discovery queries or scenario terms
- crawl public business pages and extract company-level or occasional named-contact data

What it still needs from the operator:

- target-buyer hypotheses
- discovery query terms or a benchmark scenario definition
- validation that the product has a publicly discoverable buyer footprint

## Data policy

Allowed source classes:

- first-party inbound leads
- customer-owned CRM or CSV imports
- public web evidence with business context
- licensed B2B databases with provenance and opt-out support

Prohibited source classes:

- leaked or breached databases
- stolen cookies, passwords, or unauthorized account access
- records that were explicitly suppressed or opted out

Demo data shipped with the app is synthetic and should be replaced before any real outreach.

## Product surfaces

- commercial dashboard in `frontend/`
- ICP parsing and normalization
- multi-source demo search
- lead scoring, deduplication, and compliance scan
- owned lead import API
- public web crawl API for business websites and contact pages
- public URL discovery API for heuristic search-based account finding
- social connection APIs for owned LinkedIn and Meta lead sources
- social connector catalog APIs for compliant connector setup
- supplier sourcing plan, search, and report APIs
- DeepSeek V4 model routing metadata and test APIs
- CSV and PDF export
- strategy and outreach template generation

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Open `http://127.0.0.1:8000`.

## Core API routes

- `POST /api/v1/input/parse-product`
- `POST /api/v1/input/icp/normalize`
- `GET /api/v1/llm/models`
- `POST /api/v1/llm/test`
- `POST /api/v1/customer-discovery/plan`
- `POST /api/v1/search/run`
- `POST /api/v1/public-web/discover`
- `POST /api/v1/public-web/crawl`
- `POST /api/v1/sourcing/plan`
- `POST /api/v1/sourcing/search`
- `POST /api/v1/sourcing/report`
- `GET /api/v1/sourcing/reports`
- `GET /api/v1/sourcing/reports/{report_id}`
- `GET /api/v1/social/connections`
- `POST /api/v1/social/connections`
- `POST /api/v1/social/connections/{connection_id}/sync`
- `GET /api/v1/social/connectors`
- `GET /api/v1/social/connectors/{connector_key}`
- `GET /api/v1/social/overview`
- `POST /api/v1/scoring/score`
- `POST /api/v1/leads/import`
- `POST /api/v1/compliance/scan`
- `GET /api/v1/compliance/data-policy`
- `GET /api/v1/dashboard`
- `GET /api/v1/leads/export`

## Commercial direction

The product direction now tracks three market expectations:

- Apollo-style lead scoring and enrichment workflow
- Snov-style activation and outbound enablement
- Clay-style source transparency and operator control

See `docs/commercialization-plan.md` for competitor notes, positioning, and launch direction.

## Notes

- Legacy Flask modules remain in the repo, but they are no longer the primary app path.
- Experimental live scraping scripts are not the recommended commercial route.
- If you need real production data, use `POST /api/v1/leads/import` with customer-owned or licensed records.
- Public website crawling is supported for company sites, directory pages, and contact pages.
- The public-web path works best for B2B or institution-facing products whose buyers have official public websites; it is not yet a universal customer-finding engine for any product category.
- Social-media expansion should use owned-asset connectors and official platform workflows, not profile scraping. See `docs/social-media-compliant-architecture.md`.
- FastAPI runtime state now persists locally to `.runtime/leadagent_store.json` for development flows, including social connections and sync runs.
- Social platform page scraping is intentionally out of scope; use official APIs or authorized exports instead.
- DeepSeek defaults now target the V4 API model family through env-driven model routing.
- The first Find Goods workflow is available through sourcing plan/search/report APIs and the frontend supplier-search panel. The 1688 connector is scaffolded with mock/permitted data until official or partner API credentials are configured.
- A reusable Hajj/Umrah target collection workflow is available in `scripts/collect_hajj_targets.py`.
- A cross-vertical benchmark input template is available in `docs/benchmarks/general_b2b_smoke.json`.
