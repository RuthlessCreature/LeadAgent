# LeadAgent Major Optimization RFC

Date checked: 2026-04-30
Status: Draft for implementation planning

## Executive Verdict

LeadAgent is already a useful lead-operations workspace, but it is not yet the product the next version needs to become.

Current state:

- The primary runtime is the FastAPI app in `backend/app/main.py`.
- The current frontend is a single commercial dashboard in `frontend/`.
- Public-web discovery and crawl are usable for company-level leads.
- Owned social lead ingestion is modeled, but real OAuth/webhook connectors are not implemented.
- Legacy Flask routes and Selenium LinkedIn scripts still exist and create product confusion.
- DeepSeek support is hardcoded around `deepseek-chat` in `backend/app/services/llm.py`.
- The system still lacks the missing middle layer: `product description -> buyer hypotheses -> source plan -> verified customer/supplier evidence`.

Target state:

1. A stronger **Find Customers** workflow: input product info, infer real buyer archetypes, search authorized/public sources, and return real-person leads only when provenance, consent posture, and verification evidence are attached.
2. A new **Find Goods** workflow: input product info, search supplier marketplaces such as 1688 and adjacent sources, normalize offers/suppliers, score source quality, and generate a sourcing report.
3. A DeepSeek V4-ready LLM gateway: model selection, JSON-mode reliability, report-generation model routing, version metadata, and deprecation handling for old DeepSeek aliases.

## Non-Negotiable Product Boundary

The user goal says "find real customer information from social media". The commercially usable version must satisfy that without building a high-risk profile-scraping tool.

LeadAgent should support:

- authorized social lead sources, such as LinkedIn Lead Sync and Meta Lead Ads;
- customer-owned social/CRM exports;
- public business websites, public team pages, public directories, and public profile evidence where access is allowed;
- licensed B2B/social data vendors with contract, provenance, deletion, and opt-out workflows;
- real-person records only when the person-level identity has source evidence and a lawful processing basis.

LeadAgent should not ship as:

- a LinkedIn/Facebook/Instagram/TikTok profile scraper;
- a browser automation that uses logged-in sessions to bypass platform controls;
- a "paste product -> steal all social profiles" engine;
- a system that hides source, consent, or retention state.

The practical promise should be:

> LeadAgent finds and verifies customer candidates from owned, licensed, and permitted public sources, with real-person records shown only when source evidence is strong enough for review and compliant outreach.

## Current Codebase Read

### Primary Runtime

- `run.py` starts `uvicorn` against `backend.main:app`.
- `backend/main.py` re-exports the FastAPI app.
- `backend/app/main.py` owns the active API routes.
- `frontend/index.html`, `frontend/app.js`, and `frontend/styles.css` implement the active UI.
- `backend/app/store.py` persists local runtime state to `.runtime/leadagent_store.json`.

### Important Service Modules

- `backend/app/services/parser.py`: rule-based product parser; does not infer buyer hypotheses or query plans.
- `backend/app/services/query_expansion.py`: expands public-web queries; still narrow and preset-heavy.
- `backend/app/services/discovery.py`: searches DuckDuckGo/Yahoo/Bing HTML results for public URLs.
- `backend/app/services/public_web.py`: crawls business/contact/team pages and extracts company or occasional named-person records.
- `backend/app/services/search.py`: includes both Selenium LinkedIn scraping code and FastAPI mock search compatibility helpers.
- `backend/app/services/social_connectors.py`: connector catalog for LinkedIn Lead Sync and Meta Lead Ads, but no real OAuth/webhook implementation yet.
- `backend/app/services/llm.py`: legacy LLM adapter with hardcoded DeepSeek model mapping.

### Existing Documentation Alignment

The existing docs are directionally correct:

- `docs/generalization-verdict.md` honestly says the product is not yet an arbitrary-product customer finder.
- `docs/social-media-compliant-architecture.md` correctly rejects profile scraping as the default social strategy.
- `docs/social-mvp-delivery-plan.md` scopes owned-social connector delivery.
- `docs/commercialization-plan.md` frames the product around lead operations and source transparency.

This RFC extends those docs into the next product architecture.

## Product Surface Redesign

### Navigation

Replace the single long dashboard with a work-focused app shell:

- `Dashboard`: metrics, recent runs, compliance warnings.
- `Find Customers`: product-to-buyer discovery and lead review.
- `Find Goods`: product-to-supplier sourcing and report generation.
- `Sources`: connected social, public web, licensed databases, marketplace connectors.
- `Reports`: customer lead reports, supplier sourcing reports, export history.
- `Settings`: model provider, API keys, source policies, retention defaults.

### Find Customers Workflow

Input:

- product description;
- target geography;
- optional price/MOQ/channel info;
- target sales motion, such as wholesale, retail, distributor, agency, institution, ecommerce;
- allowed source classes.

System stages:

1. Parse product and use case.
2. Generate buyer hypotheses.
3. Generate search/source plan.
4. Execute permitted sources.
5. Normalize companies and people.
6. Verify real-person evidence.
7. Score fit, contactability, and compliance.
8. Generate reviewable customer report.

Output:

- buyer-archetype summary;
- lead candidates grouped by company and person;
- source URLs and evidence snippets;
- consent/legal-basis state;
- verification level;
- recommended next action;
- CSV/PDF export.

### Find Goods Workflow

Input:

- product description;
- target supplier country/region;
- target platform mix, initially `1688`, `Alibaba`, `Made-in-China`, `GlobalSources`, and generic public web;
- target price band;
- MOQ and customization needs;
- certification needs;
- report language.

System stages:

1. Parse product into product taxonomy, Chinese/English keywords, materials, dimensions, use cases, and buyer constraints.
2. Build marketplace search plan.
3. Search source platforms through official APIs, partner APIs, permitted browser/manual flows, or search-engine discovery.
4. Normalize product offers and suppliers.
5. Score suppliers by price, MOQ, trust signals, transaction signals, response evidence, certifications, and source risk.
6. Build comparison table.
7. Generate sourcing report.

Output:

- recommended supplier shortlist;
- price/MOQ range;
- offer links and screenshots/evidence where available;
- supplier risk flags;
- negotiation questions;
- sample outreach/RFQ message;
- sourcing report in HTML/PDF/CSV.

## New Data Model

### Buyer Hypotheses

Add a canonical object:

```python
class BuyerHypothesis(BaseModel):
    hypothesis_id: str
    buyer_type: str
    buyer_roles: list[str]
    company_types: list[str]
    geographies: list[str]
    search_language: list[str]
    source_plan: list[str]
    confidence: float
    rationale: str
```

### Person Verification

Extend `LeadCandidate` or add an attached evidence model:

```python
class PersonEvidence(BaseModel):
    evidence_id: str
    lead_id: str
    source_url: str
    source_platform: str
    evidence_type: str  # profile, team_page, lead_form, licensed_record, crm_import
    observed_name: str
    observed_role: str
    observed_company: str
    observed_contact: str
    confidence: float
    collected_at: datetime
```

Person-level output should require at least one strong evidence record.

### Supplier Sourcing

Add:

```python
class SupplierCandidate(BaseModel):
    supplier_id: str
    platform: str
    supplier_name: str
    supplier_url: str
    location: str = ""
    years_active: int | None = None
    verification_badges: list[str] = []
    response_rate: str = ""
    transaction_signals: list[str] = []
    risk_flags: list[str] = []
```

```python
class ProductOffer(BaseModel):
    offer_id: str
    supplier_id: str
    platform: str
    title: str
    product_url: str
    image_url: str = ""
    price_min: float | None = None
    price_max: float | None = None
    currency: str = "CNY"
    moq: str = ""
    attributes: dict[str, str] = {}
    source_evidence: list[str] = []
```

```python
class SourcingReport(BaseModel):
    report_id: str
    product_name: str
    query_terms: list[str]
    offers: list[ProductOffer]
    suppliers: list[SupplierCandidate]
    summary: str
    recommendations: list[str]
    generated_at: datetime
```

## API Plan

### Customer Discovery

- `POST /api/v1/customer-discovery/plan`
  - Input: product description, geography, allowed sources.
  - Output: buyer hypotheses and source plan.

- `POST /api/v1/customer-discovery/run`
  - Input: selected plan, source limits.
  - Output: leads, evidence, tasks.

- `POST /api/v1/customer-discovery/report`
  - Input: lead IDs and report options.
  - Output: customer discovery report.

### Supplier Sourcing

- `POST /api/v1/sourcing/plan`
  - Input: product description, target source platforms, constraints.
  - Output: sourcing query plan.

- `POST /api/v1/sourcing/search`
  - Input: sourcing plan.
  - Output: product offers and supplier candidates.

- `POST /api/v1/sourcing/report`
  - Input: offer IDs, supplier IDs, report options.
  - Output: sourcing report.

- `GET /api/v1/sourcing/reports/{report_id}`
  - Output: saved report.

### LLM Gateway

- `GET /api/v1/llm/models`
- `POST /api/v1/llm/test`
- `POST /api/v1/llm/json`
- `POST /api/v1/llm/report`

The app should call the LLM through one gateway instead of calling `LLMClient` directly from multiple feature modules.

## DeepSeek V4 Migration Plan

### Official State as of 2026-04-30

DeepSeek's official API news page says DeepSeek-V4-0324-preview launched on 2026-04-24 and exposes:

- `deepseek-v4-flash`
- `deepseek-v4-flash-thinking`
- `deepseek-v4-pro`
- `deepseek-v4-pro-thinking`

The same official notice says the older `deepseek-chat` and `deepseek-reasoner` models are scheduled for retirement on 2026-07-24.

### Required Code Changes

In `backend/app/services/llm.py`:

- stop hardcoding `deepseek-chat`;
- read model names from environment variables;
- support separate fast, reasoning, and report models;
- preserve DeepSeek's OpenAI-compatible `/chat/completions` shape;
- add JSON-response helper with strict parsing and repair fallback;
- expose model/version metadata to the frontend;
- add timeout/retry controls.

Suggested env vars:

```env
DEFAULT_LLM=deepseek
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_REASONING_MODEL=deepseek-v4-flash-thinking
DEEPSEEK_REPORT_MODEL=deepseek-v4-pro
DEEPSEEK_REPORT_REASONING_MODEL=deepseek-v4-pro-thinking
DEEPSEEK_TIMEOUT_SECONDS=90
```

Routing:

- buyer hypothesis generation: `deepseek-v4-flash-thinking`
- ordinary parsing/classification: `deepseek-v4-flash`
- supplier report synthesis: `deepseek-v4-pro`
- complex report or multi-source contradiction analysis: `deepseek-v4-pro-thinking`

### Backward Compatibility

During migration:

- accept existing `DEEPSEEK_API_KEY` and `DEEPSEEK_BASE_URL`;
- if `DEEPSEEK_MODEL` is missing, default to `deepseek-v4-flash`;
- keep `deepseek-chat` only as an explicit override, not default;
- log a warning if old aliases are configured.

## Source Connector Strategy

### Social Sources

Priority order:

1. LinkedIn Lead Sync via official/customer-authorized flow.
2. Meta Lead Ads via official/customer-authorized flow.
3. Customer-owned exports from social campaign tools.
4. Licensed databases with person-level data contracts.
5. Public business/team pages crawled with source and robots policy handling.

The existing Selenium LinkedIn scraper should be moved behind an explicit experimental quarantine or removed from the default product path.

### Supplier Sources

Initial source plan:

1. 1688 through official/partner API or permitted operator-assisted workflow.
2. Alibaba.com public/product discovery where permitted.
3. Made-in-China and GlobalSources discovery where permitted.
4. Supplier public websites.
5. Manual CSV import for supplier lists.

For 1688, build the connector as an interface first:

```python
class SupplierSourceConnector(Protocol):
    source_key: str

    def search_offers(self, query: SourcingQuery) -> list[ProductOffer]:
        ...

    def get_supplier(self, supplier_url: str) -> SupplierCandidate:
        ...
```

Then implement `Mock1688Connector` first, followed by `Official1688Connector` once API credentials and exact endpoints are confirmed.

## Report Requirements

### Customer Report

Must include:

- product summary;
- buyer hypotheses;
- source plan used;
- lead table;
- person evidence;
- score rationale;
- compliance status;
- recommended outreach angle.

### Supplier Report

Must include:

- product interpretation;
- query terms in English and Chinese;
- offer comparison;
- supplier shortlist;
- price/MOQ summary;
- certification and risk flags;
- recommended negotiation questions;
- RFQ template;
- appendix of source URLs.

## Implementation Phases

### Phase 0: Documentation and Guardrails

- Publish this RFC.
- Update `.pm` metadata.
- Add a small architecture diagram later if needed.

### Phase 1: DeepSeek V4 Gateway

- Refactor `LLMClient`.
- Add env vars and tests.
- Add `/api/v1/llm/test`.
- Update `.env.example`.

Acceptance:

- `deepseek-v4-flash` is default.
- old DeepSeek aliases are not hardcoded.
- JSON parsing has regression tests.

### Phase 2: Product Intelligence Layer

- Add buyer hypothesis generation.
- Add sourcing query generation.
- Add source fit confidence.

Acceptance:

- product input alone can produce a reviewable customer-source plan and supplier-source plan.

### Phase 3: Find Customers V2

- Add customer discovery page.
- Add lead evidence model.
- Add official social connector implementation milestones.
- Quarantine direct social scraping from default UX.

Acceptance:

- real-person leads require evidence and source type.
- social lead records must show authorized/owned/licensed/public provenance.

### Phase 4: Find Goods V1

- Add supplier sourcing models.
- Add mock 1688 connector.
- Add public supplier web connector.
- Add frontend page.
- Add sourcing report generation.

Acceptance:

- a user can input a product and receive a supplier comparison report using mock/permitted sources.

### Phase 5: Real Marketplace Connectors

- Implement 1688 official/partner connector after credentials and API contract are confirmed.
- Add import fallback.
- Add caching, deduplication, rate limits, and source audit.

Acceptance:

- real supplier records include source URL, collected timestamp, and marketplace/source risk state.

## Engineering Risks

- Social platform access may require partner approval and API review.
- Scraping-based social workflows can create legal and account-suspension risk.
- Supplier marketplace access may require credentials, anti-bot controls, or partner API approval.
- Product-to-buyer inference can hallucinate if the LLM is not constrained by evidence.
- DeepSeek V4 preview behavior may change before stable release.
- Existing mojibake comments in legacy Python files make maintenance harder.
- Current file-backed store is not production-grade.

## Immediate Backlog

1. Refactor `backend/app/services/llm.py` for DeepSeek V4 env-driven model routing.
2. Add `ProductDiscoveryPlan` and `SourcingPlan` schemas.
3. Add `BuyerHypothesis`, `PersonEvidence`, `SupplierCandidate`, `ProductOffer`, and `SourcingReport` models.
4. Build `/api/v1/sourcing/plan`, `/api/v1/sourcing/search`, and `/api/v1/sourcing/report`.
5. Add a `Find Goods` page to the frontend.
6. Add tests for supplier normalization and report generation.
7. Quarantine `LinkedInSearcher` behind `SEARCH_MODE=experimental_selenium` and remove it from default docs.
8. Add official social connector implementation tickets for OAuth, webhook verification, token storage, and backfill.
9. Update README to describe the new two-sided product: find customers and find goods.
10. Add report export support for supplier reports.

## Official Source Links Checked

- DeepSeek V4 API news, checked 2026-04-30: https://api-docs.deepseek.com/news/news260424
- DeepSeek API pricing/model page, checked 2026-04-30: https://api-docs.deepseek.com/quick_start/pricing
- LinkedIn User Agreement, checked 2026-04-30: https://www.linkedin.com/legal/user-agreement
- Meta Automated Data Collection Terms, checked 2026-04-30: https://www.facebook.com/legal/automated_data_collection_terms
- Meta Lead Ads guide, checked 2026-04-30: https://developers.facebook.com/docs/marketing-api/guides/lead-ads/
- Alibaba Open Platform / 1688 API entry, checked 2026-04-30: https://aop.alibaba.com/

