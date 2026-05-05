# LeadAgent Social MVP Delivery Plan

Date: 2026-04-06

## Objective

Ship the first commercially usable social-media module for LeadAgent without relying on profile scraping.

## MVP scope

### Included

- owned social connection records
- owned asset selection
- authorized lead sync ingestion
- provenance-preserving lead storage
- dashboard-level social overview
- export-ready normalized leads

### Excluded

- profile scraping
- browser-extension capture
- audience pushback
- campaign creation
- message sending

## What is already in place

- canonical social connection models
- sync run models
- social provenance fields on leads
- persisted local social connection APIs and sync-run state
- connector catalog endpoints for LinkedIn Lead Sync and Meta Lead Ads
- test coverage for connection creation and lead sync

## Commercial acceptance criteria

The MVP is commercially credible when a pilot customer can:

1. connect a LinkedIn or Meta owned asset set
2. sync lead submissions into LeadAgent
3. see source provenance on each lead
4. export or sync those leads to CRM safely
5. prove that no scraping-based data source was used

## Delivery phases

### Phase 1: API and schema hardening

- move social connectors from in-memory state to persistent storage
- add encrypted token storage placeholders
- add connection health fields and error taxonomy
- add retention and deletion timestamps to sync runs

### Phase 2: LinkedIn Lead Sync connector

- OAuth handshake
- organization / sponsored account selection
- webhook registration tracking
- backfill job
- lead-field normalization

### Phase 3: Meta lead-ads connector

- business asset selection
- page / ad account / form binding
- periodic reconciliation pull
- form payload normalization

### Phase 4: CRM and ops polish

- HubSpot export / sync path
- Salesforce export / sync path
- operator review queue for social leads
- alerting for sync failures and stale tokens

## Engineering checklist

- add persistent tables or store adapters for social connections and sync runs
- introduce token-secret abstraction
- implement idempotent external lead identifiers
- add webhook verification helpers
- add retryable sync job interfaces
- add audit events for connect, sync, failure, disconnect

## Product checklist

- connection wizard copy
- asset authorization UX
- source provenance badges
- legal-basis copy for imported social leads
- documentation for pilot onboarding

## GTM checklist

- outbound message: "connect the lead sources you already own"
- anti-positioning: "not a scraping database"
- pilot ICP: agencies and SMB teams already running LinkedIn or Meta lead ads
- success story template: capture -> route -> CRM -> follow-up

## Recommended next implementation step

Build the persistent social connector layer first, then wire the first real connector in this order:

1. LinkedIn Lead Sync
2. Meta lead ads
3. HubSpot sync
