# LeadAgent Social Media Compliant Architecture

Date checked: 2026-04-06

## Goal

Add social-media-based lead capture and activation to LeadAgent **without** turning the product into a high-risk profile-scraping tool.

The target outcome is:

- first-party and customer-authorized lead ingestion from social platforms
- audience sync back into ad platforms for retargeting and expansion
- clear consent, provenance, and asset ownership records
- a product shape that can survive platform review, partner vetting, and customer due diligence

## Bottom-line product decision

LeadAgent should **not** build its own social scraping database for LinkedIn, Facebook, or Instagram.

Instead, LeadAgent should use a compliant three-lane model:

1. **Official lead capture**
   - LinkedIn Lead Gen Forms / Lead Sync
   - Meta lead ads with forms
   - Meta lead ads that click to message
2. **Customer-owned asset sync**
   - customer ad accounts
   - customer pages
   - customer forms
   - customer CRM lists and exports
3. **Audience activation**
   - LinkedIn Matched Audiences
   - Meta custom audiences / Advantage+ seed audiences

This gives us a social offering that is commercially useful **without** promising universal social prospect scraping.

## Why this is the right boundary

### LinkedIn

As checked on 2026-04-06:

- LinkedIn's User Agreement says members may not use software, scripts, robots, crawlers, browser plugins, or similar means to scrape or copy LinkedIn services, including profiles and other data.
- LinkedIn's Lead Sync documentation and partner guides show the supported route is OAuth-based, organization-approved lead syncing into CRMs and automation tools.

### Meta / Facebook / Instagram

As checked on 2026-04-06:

- Meta's Automated Data Collection Terms say automated collection requires **Meta's express written permission**, and acceptance of the terms alone is not enough.
- Facebook's `robots.txt` says collection through automated means is prohibited unless express written permission has been granted.
- Instagram's terms say you cannot access or collect information in an automated way without express permission.
- Meta's official lead-generation product path is lead ads with forms, lead ads with messaging, and related CRM / audience workflows.

## What this means in practice

LeadAgent **can** sell:

- social lead capture
- social lead sync
- campaign-to-CRM workflows
- customer-list activation and suppression
- cross-channel scoring and routing

LeadAgent should **not** sell:

- scraped LinkedIn profile databases
- scraped Facebook Page databases
- scraped Instagram business-account databases
- browser-extension automation that copies profile data into LeadAgent
- unofficial API or session-cookie-based collection

## Reference competitor framing

This matters because some competitors mix together:

- proprietary or licensed contact databases
- social automation add-ons
- browser extensions
- outreach sequences

For example, as checked on 2026-04-06, Snov.io publicly markets:

- a B2B lead database with `1.5 billion` leads
- LinkedIn automation sold as an add-on at `$69/mo per slot`

That is a very different product shape from LeadAgent's current compliant public-web + owned-data positioning.

## Recommended product architecture

### 1. Source lanes

LeadAgent should expose social sources as **authorized connectors**, not scraping engines.

#### Lane A: LinkedIn Lead Sync

Use for:

- sponsored Lead Gen Forms
- organic Lead Gen Forms where supported by LinkedIn's newer APIs
- company-page, event, product-page, and landing-page-associated lead forms where available through the Lead Sync model

Expected data:

- form metadata
- predefined and custom field answers
- consent text and privacy-policy links
- campaign / account / organization metadata
- webhook notifications for new or deleted leads

#### Lane B: Meta Lead Ads

Use for:

- Facebook lead ads with instant forms
- Instagram placements that feed into Meta lead forms
- click-to-message lead flows through Messenger or Instagram

Expected data:

- form submission payloads
- campaign / ad-set / ad metadata
- page / business asset metadata
- message-flow lead answers where available in the official product path

#### Lane C: Customer-owned exports

Use for:

- CSV exports from customer social campaigns
- CRM exports that originated from social platforms
- agency-managed account exports

Expected data:

- lead identity data
- campaign source metadata
- timestamps
- consent or form provenance fields when available

#### Lane D: Activation audiences

Use for:

- suppression of existing customers
- retargeting of qualified social leads
- seed audiences for expansion
- account or contact list syncing from LeadAgent back to ad platforms

Targets:

- LinkedIn Matched Audiences
- Meta customer lists / audience seeds

### 2. Internal system shape

LeadAgent should add a `social-connectors` layer with four modules:

1. `auth`
   - OAuth tokens
   - refresh handling
   - token expiry detection
   - asset / organization authorization checks
2. `ingest`
   - webhook receiver
   - periodic pull backfill
   - idempotent lead upserts
   - deletion / revocation handling
3. `normalize`
   - map platform-specific fields into LeadAgent canonical lead schema
   - preserve raw payload snapshot
   - store consent text, form id, campaign id, account id, page id, organization id
4. `activate`
   - push qualified segments back as customer lists / matched audiences
   - maintain audience version history
   - support inclusion and suppression lists

## Canonical data model additions

LeadAgent's existing provenance model is a strong base, but social connectors need more explicit asset-level fields.

Add fields like:

- `source_type`: `first_party_social`, `customer_import`, `licensed_database`, `public_web`
- `source_platform`: `linkedin`, `facebook`, `instagram`, `messenger`
- `source_asset_owner_type`: `organization`, `page`, `ad_account`, `event`, `product_page`
- `source_asset_owner_id`
- `source_form_id`
- `source_campaign_id`
- `source_ad_account_id`
- `source_page_id`
- `source_consent_text`
- `source_privacy_policy_url`
- `source_submission_timestamp`
- `source_payload_version`
- `source_raw_payload_hash`
- `deletion_requested_at`
- `retention_expires_at`

This keeps LeadAgent consistent with its current provenance-first product thesis.

## Connector behavior requirements

### LinkedIn connector requirements

LeadAgent's LinkedIn connector should follow the shape implied by LinkedIn's current partner requirements:

- OAuth 2.0 flow
- token-heartbeat checks
- refresh token renewal
- permission checks for organization and sponsored-account access
- dynamic form-field storage instead of hard-coded static schemas
- full-form metadata ingestion
- automatic backfill of recent lead history
- push notifications with pull backup
- safe teardown that removes webhook registrations

### Meta connector requirements

LeadAgent's Meta connector should implement:

- business-asset authorization
- customer-owned page / ad-account selection
- instant-form and messaging-lead ingestion
- periodic reconciliation pull
- deduplication by lead id + asset id + submission timestamp
- customer-list push for activation and suppression
- clear asset-level audit logging

## Recommended UX

LeadAgent should present social integrations as an **authorized growth workspace**, not a scraping console.

Suggested flow:

1. Connect platform
2. Select owned assets
3. Select lead sources
4. Backfill last 30 / 90 / 365 days where supported
5. Review field mapping
6. Enable webhook / scheduled sync
7. Score and route leads
8. Create activation audiences
9. Export or sync to CRM

Each sync should show:

- source asset
- last successful sync
- new leads
- failed leads
- deleted leads
- token status
- retention / consent warnings

## What LeadAgent should say publicly

Recommended claim:

> LeadAgent connects your owned social lead sources, syncs them into one compliant pipeline, scores and routes them, and sends qualified audiences back to your paid channels.

Avoid claims like:

- "scrape social media for any lead"
- "build a LinkedIn database automatically"
- "extract Facebook and Instagram contacts at scale"
- "collect unlimited public social profiles"

## MVP scope

### MVP 1: Social inbound sync

Ship first:

- LinkedIn Lead Sync connector
- Meta lead ads with forms connector
- manual CSV import fallback for social exports
- provenance-preserving normalization
- HubSpot / Salesforce export

Success metric:

- a customer can connect owned assets and sync social leads into LeadAgent within one hour

### MVP 2: Activation loop

Then add:

- LinkedIn Matched Audiences sync
- Meta customer-list / audience sync
- inclusion and suppression segments
- quality-lead segment publishing

Success metric:

- a customer can push `MQL`, `SQL`, and `do-not-target` audiences back into ad platforms

### MVP 3: Cross-channel orchestration

Then add:

- channel-level attribution rollups
- paid-social to CRM conversion reporting
- route-by-intent scoring
- alerting for high-quality form submissions

Success metric:

- LeadAgent becomes the control plane for capture -> score -> route -> activate

## Non-goals

At least for the current product direction, do **not** build:

- scraped social profile search
- follower / liker / commenter harvesting
- "visit profile and auto-copy data" browser automations
- cookie-based session replay connectors
- unofficial reverse-engineered APIs
- outbound sending that depends on violating platform rules

## Main risks

1. **Platform access risk**
   - LinkedIn Lead Sync access requires vetting and commercial organization status.
2. **Scope mismatch risk**
   - customers may expect social prospect discovery, but official surfaces mainly cover owned lead capture and audience activation.
3. **Data-model complexity**
   - form schemas vary per asset and per locale.
4. **Consent and retention complexity**
   - social form payloads may have different legal bases across regions and customers.
5. **Go-to-market confusion**
   - if we talk like a database company while shipping an owned-asset connector product, positioning will drift.

## Recommended GTM framing

Position LeadAgent against risky scraping tools by saying:

- owned-data-first
- platform-compliant
- CRM-ready
- source-visible
- activation-ready

The wedge is:

- "connect what you already own"
- "make paid-social leads operational"
- "close the loop from form to CRM to audience"

Not:

- "we have the biggest social database"

## Suggested implementation order

1. Build canonical `social_source` schema and audit fields
2. Build LinkedIn Lead Sync connector
3. Build Meta lead ads connector
4. Add webhook ingestion + periodic pull backfill
5. Add CRM sync and dashboard surfaces
6. Add activation audiences for LinkedIn and Meta
7. Add policy guardrails, retention rules, and deletion workflows

## Final verdict

Yes, LeadAgent can expand into social media.

But the winning version is **not**:

- "use heuristics to scrape social pages the same way we crawl company websites"

The winning version is:

- "connect official social lead surfaces and customer-owned assets into a compliant lead-ops and activation system"

That product is narrower than a scraping database, but much safer, easier to defend, and better aligned with LeadAgent's current provenance-first positioning.

## Official source links checked on 2026-04-06

- LinkedIn User Agreement: https://www.linkedin.com/legal/user-agreement
- LinkedIn Lead Sync API access guide: https://business.linkedin.com/content/dam/me/business/en-us/marketing-solutions/cx/2022/pdf/linkedin-lead-sync-api-access-guide.pdf
- LinkedIn Lead Sync integration requirements: https://learn.microsoft.com/en-us/linkedin/marketing/lead-sync/marketing-leads-integration-requirements
- LinkedIn Lead Sync migration guide: https://learn.microsoft.com/en-us/linkedin/marketing/lead-sync/lead-sync-api-migration-guide
- LinkedIn Lead Gen Forms: https://business.linkedin.com/marketing-solutions/success/ads-guide/lead-gen-forms
- LinkedIn Matched Audiences: https://business.linkedin.com/de/de/advertise/ads/targeting/matched-audiences
- Meta Automated Data Collection Terms: https://www.facebook.com/legal/automated_data_collection_terms
- Facebook robots.txt: https://www.facebook.com/robots.txt
- Instagram Terms of Use: https://www.facebook.com/help/instagram/581066165581870
- Meta lead ads with forms: https://www.facebook.com/business/ads/ad-objectives/lead-generation/lead-ads-with-forms
- Meta lead ads with messaging: https://www.facebook.com/business/ads/ad-objectives/lead-generation/lead-ads-with-messaging
- Meta customer-list custom audiences: https://www.facebook.com/legal/terms/customaudience
- Meta Advantage+ audience: https://www.facebook.com/business/ads/meta-advantage-plus/audience
- Snov.io B2B lead finder: https://snov.io/b2b-lead-finder
- Snov.io pricing: https://snov.io/pricing
