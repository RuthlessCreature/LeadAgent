# LeadAgent Generalization Verdict

Date: 2026-04-06

## Bottom line

LeadAgent is **not** currently a true `arbitrary product input -> customer list` engine.

It is currently better described as:

- a compliant lead-operations workspace
- with reusable public-web discovery and crawl tooling
- that can produce company-level prospects for multiple B2B verticals
- when an operator provides explicit buyer hypotheses, ICP constraints, and discovery queries

## Why the current product is not fully general

### 1. Product parsing does not create a buyer-market map

`backend/app/services/parser.py` extracts:

- product name
- industry tags
- feature tags
- use cases
- target roles
- price hints

It does **not** infer:

- who the actual buyer segment is
- what search terms represent that buyer segment
- which public sources should be searched first
- whether the buyer footprint is public, private, or mostly intent-data driven

### 2. Public-web discovery still needs explicit queries

`POST /api/v1/public-web/discover` in `backend/app/main.py` requires one of:

- `queries`
- `query_terms`
- `query_preset`

That means the system currently needs an operator-supplied discovery plan. Product input alone is insufficient.

### 3. The built-in preset library is still narrow

`backend/app/services/query_expansion.py` currently ships with one built-in preset: `hajj_umrah`.

That is a strong signal that the product has reusable public-web mechanics, but not a broad default market-intelligence layer yet.

### 4. The generic search pipeline is still mostly demo-mode

`backend/app/services/search.py` defaults `SEARCH_MODE` to `mock`, and only the experimental LinkedIn path attempts live search.

So the real validated live-data path today is primarily:

- owned / customer imports
- public-web discovery
- public-web crawl

not a universal autonomous search agent.

## Fresh cross-vertical check

To avoid overfitting to the existing Hajj / Islamic-adjacent scenarios, a new scenario-file driven benchmark runner was added and run on 2026-04-06 with four unrelated B2B categories:

1. restaurant POS software -> restaurants
2. dental equipment distributor -> dental clinics / labs
3. warehouse barcode software -> 3PL / fulfillment operators
4. commercial HVAC parts supplier -> HVAC contractors

Input file:

- `docs/benchmarks/general_b2b_smoke.json`

Output directory:

- `deliverables/scenario_benchmarks_2026-04-06_general_smoke/`

Summary results:

| Scenario | Discovered domains | Contacts | Named people | Companies |
| --- | ---: | ---: | ---: | ---: |
| Restaurant POS | 16 | 8 | 1 | 7 |
| Dental equipment | 43 | 7 | 0 | 6 |
| Warehouse barcode | 31 | 11 | 0 | 8 |
| Commercial HVAC | 38 | 14 | 3 | 7 |

## What this proves

The new run proves that LeadAgent is **not only working on the original specialized scenarios**.

The public-web workflow can generalize across several unrelated B2B categories and still return:

- relevant company domains
- company-level inboxes or phone numbers
- occasional named-contact signals

## What it does not prove

The new run does **not** prove that LeadAgent works for **any** product.

It still fails the stronger claim for several reasons:

1. it needs hand-authored buyer queries
2. it works best when buyers have official public websites
3. named-person extraction remains sparse
4. some results are directories, media lists, or aggregator pages rather than direct buyer accounts
5. products aimed at consumers, stealth buyers, or non-public procurement flows are still weak fits

## Practical capability boundary

LeadAgent currently works best when all of the following are true:

- the product is B2B or institution-facing
- the buyer category can be named in public search queries
- target accounts have official public websites or directory listings
- company-level contact data is acceptable as an initial lead set

LeadAgent is currently weak when:

- the product is B2C
- the category is new or hard to name in search language
- the real buyer is hidden behind marketplaces, channels, or procurement systems
- success depends on deep intent data rather than public business presence
- high-confidence named-person coverage is required immediately

## Recommended next step

If the goal is to make LeadAgent feel closer to a true arbitrary-product system, the missing layer is:

`product description -> buyer hypotheses -> query plan -> source plan -> confidence check`

The next milestone should be a new strategy stage that:

- infers likely buyer archetypes from product + use case
- proposes multiple discoverable search-language hypotheses
- predicts whether public-web sourcing is a good fit
- falls back to import / licensed-data / directory-first workflows when public-web fit is low

Until that exists, the honest claim is:

> LeadAgent can already find company-level prospects across multiple B2B verticals, but it is not yet a universal arbitrary-product customer-finder.
