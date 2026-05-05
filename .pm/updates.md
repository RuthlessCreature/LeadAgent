## 2026-02-28
- 1

## 2026-04-03
- Reframed LeadAgent as a commercial lead operations workspace instead of a scraping-first prototype.
- Added owned lead import, source provenance fields, consent and verification states, and a data policy endpoint that rejects leaked or breached data.
- Rebuilt the frontend against the FastAPI app, added commercialization documentation, and restored a primary `python run.py` startup path for the product flow.
- Added a public-web crawl path for company sites, contact pages, and directory pages while keeping social-platform page scraping out of scope.
- Added heuristic public URL discovery plus a reusable Hajj/Umrah target capture script that exports real company-level accounts and public business contact details.
- Tightened public-web contact cleanup for mailto artifacts and placeholder phones, and added a repeatable enrichment script that turns discovered Hajj/Umrah company domains into contact-level and company-level deliverables.
- Added a batch-oriented Hajj/Umrah discovery expansion script so wider geographic coverage can be discovered and enriched without ad hoc one-liners.
- Scaled the Hajj/Umrah public-web dataset to 322 discovered company domains and 268 company-level records with public contact coverage after enrichment.
- Added multilingual query expansion for public-web discovery so a vertical can search with preset terms across Arabic, Urdu, French, Turkish, Indonesian, Malay, Bengali, German, Dutch, or user-supplied translations instead of relying only on English queries.
- Validated multilingual discovery on the Hajj/Umrah dataset: 402 discovered domains and 302 company-level records after enrichment, with 230 net-new domains versus the prior English-first wide run.
- Added language-specific location aliases for multilingual discovery and validated the uplift on Hajj/Umrah: 439 discovered domains and 322 company-level records after enrichment, including 84 net-new domains and 56 net-new company domains versus the prior polyglot run without location aliases.
- Added CRM-ready export cleanup heuristics for country inference, company-name cleanup, and phone normalization, then rebuilt the Hajj/Umrah exports.
- Verified the cleanup with targeted regression coverage plus API tests: 20 tests passing.
- Measured the current CRM export at 322 companies, 296 normalized phones, 223 records with both email and phone, and 24 inferred countries.
- Reduced unresolved geography in the CRM export from a prior 119 `Unknown` or `North America` rows to 20 after text, URL, dial-code, and local-number heuristics were added.
- Upgraded the public-web crawler to prefer named contacts from official team, staff, about, and contact pages before falling back to company-level inboxes.
- Added person-level deduplication and a dedicated `*_people.csv/json` export in the enrichment script so named contacts can be reviewed separately from company-level contacts.
- Removed the fake default role assignment on public-web records so unnamed contacts no longer appear as `Procurement Manager`.
- Re-ran the Hajj/Umrah enrichment on the multilingual alias dataset and produced a high-confidence named-contact export with 5 named people, 5 phones, and 1 public email from official public pages.
- Added a reusable multi-scenario benchmark runner for public-web discovery and crawling so different dealer/manufacturer ICPs can be compared under the same heuristic workflow.
- Ran five benchmark scenarios on 2026-04-03: Hajj accessories wholesaler, modest apparel manufacturer, Islamic books distributor, Islamic school supplier, and mosque technology dealer.
- The benchmark outputs were written to `deliverables/scenario_benchmarks_2026-04-03_v2/` and showed company-contact coverage in every scenario, but near-zero high-confidence named contacts from public websites under the quick-run budget.
- Final clean benchmark counts were: Hajj `66` discovered domains / `29` contacts / `0` named people; modest apparel `71` / `16` / `0`; Islamic books `45` / `21` / `0`; Islamic schools `65` / `23` / `0`; mosque tech `59` / `34` / `0`.
- The scenario benchmark confirms that public-web person-level extraction needs deeper official directory and accreditation sources for most verticals, while company-level contact extraction is already working across multiple product ICPs.

## 2026-04-06
- Added a scenario-file driven benchmark flow so public-web discovery can be tested on arbitrary benchmark definitions instead of only the hardcoded scenario list in `scripts/benchmark_public_web_scenarios.py`.
- Added a generic benchmark input template in `docs/benchmarks/general_b2b_smoke.json` covering restaurant POS, dental equipment, warehouse barcode software, and commercial HVAC supply.
- Generalized benchmark title ranking and public-web title scoring so company-like segments are not biased toward travel-only wording.
- Verified the new benchmark flow with live public-web runs across four unrelated B2B verticals in `deliverables/scenario_benchmarks_2026-04-06_general_smoke/`.
- Live summary counts were: restaurant POS `16` discovered domains / `8` contacts / `1` named person; dental equipment `43` / `7` / `0`; warehouse barcode `31` / `11` / `0`; commercial HVAC `38` / `14` / `3`.
- Wrote `docs/generalization-verdict.md` to make the product claim explicit: LeadAgent generalizes beyond the original specialized use cases for company-level public-web sourcing, but it is not yet a universal arbitrary-product customer-finding engine because buyer-hypothesis and query-plan generation still need operator input.
- Wrote `docs/social-media-compliant-architecture.md` to define the social expansion path: use owned-asset LinkedIn Lead Sync and Meta lead-ad connectors plus audience activation, and explicitly avoid high-risk LinkedIn / Facebook / Instagram profile scraping.
- Added a first implementation layer for that social direction: social connection models, sync-run models, first-party-social provenance fields on leads, connection/sync/overview APIs, and API tests for the owned-social workflow.
- Added `docs/social-mvp-delivery-plan.md` so the new social connector foundation has a concrete commercial MVP path instead of only an architecture note.

## 2026-04-07
- Added a persisted local runtime store in `backend/app/store.py` so FastAPI state no longer disappears on every process restart during development, including social connections, sync runs, leads, tasks, notifications, and product profiles.
- Added a social connector catalog in `backend/app/services/social_connectors.py` plus `GET /api/v1/social/connectors` and `GET /api/v1/social/connectors/{connector_key}` so the product now has explicit connector definitions for LinkedIn Lead Sync and Meta Lead Ads.
- Added connector-key support and external lead ids to the social provenance model so official connector runs can be made more reliably idempotent.
- Added API coverage for connector catalog responses and store persistence / reload behavior; the targeted suite now passes with `12` tests.
- Added `.gitignore` for `.runtime/` so local persisted product state can exist during development without polluting the repo.

## 2026-04-30
- Reviewed the current FastAPI, frontend, service, legacy Flask, public-web, social connector, and LLM surfaces before implementation.
- Wrote `docs/leadagent-optimization-rfc-2026-04-30.md` to define the next major optimization direction: compliant real-person customer discovery, a new Find Goods supplier sourcing workflow, and a DeepSeek V4 model gateway.
- Added `docs/leadagent-optimization-rfc-2026-04-30.zh-CN.md` as the Chinese primary planning artifact for the same optimization scope.
- Confirmed from DeepSeek official API documentation that V4 preview models were announced on 2026-04-24 and that old `deepseek-chat` / `deepseek-reasoner` aliases are scheduled for retirement on 2026-07-24.
- Updated project metadata to track planned DeepSeek V4, Find Goods, and customer-discovery V2 work.
- Implemented the first DeepSeek V4 gateway pass in `backend/app/services/llm.py`, including V4 defaults, model routing, JSON parsing helpers, metadata API support, and legacy alias warnings.
- Added customer discovery planning models and `POST /api/v1/customer-discovery/plan` for product-to-buyer hypothesis generation.
- Added supplier sourcing models, mock/permitted marketplace connector scaffolding, sourcing plan/search/report APIs, saved report persistence, and a Find Goods frontend panel.
- Updated README route documentation and added regression coverage for LLM defaults, customer discovery planning, and sourcing plan/search/report.
- Localized the active frontend interface to Chinese, including static labels, default examples, status messages, sourcing summaries, compliance policy text, lead-detail labels, and Chinese outreach template generation.
- Simplified the frontend per operator feedback by removing the technical-stack through per-platform-result inputs, the public-web crawl panel, and the owned-lead import panel from the active UI.
