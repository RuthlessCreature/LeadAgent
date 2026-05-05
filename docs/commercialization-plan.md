# LeadAgent Commercialization Plan

Date: 2026-04-03

## Objective

Turn LeadAgent from a scraping-heavy prototype into a saleable lead operations product for SMB outbound teams.

## Target customer

- founder-led B2B SaaS teams
- export and manufacturing operators doing outbound prospecting
- small agencies running outbound for clients

## Product thesis

LeadAgent should win on operator clarity, not raw data volume.

The product should make it obvious:

- where a lead came from
- whether it is safe to use
- why it scored high
- what the next action should be

## Differentiated product shape

LeadAgent should combine:

- a simple outbound workspace like Snov.io
- scoring and workflow discipline similar to Apollo
- source provenance and enrichment controls closer to Clay

The product should avoid competing head-on on database size.
Instead it should compete on:

- speed to first usable pipeline
- visible data governance
- easy import of owned data
- practical activation for small teams

## Compliant data strategy

Primary data lanes:

1. customer-owned imports
2. first-party inbound forms
3. public company pages and role pages
4. licensed B2B data providers
5. partner referrals

Supported crawler lane:

- public business websites
- contact pages
- company/about/team pages
- directory and exhibitor pages that are publicly accessible

Not supported as crawler targets:

- Facebook, Instagram, LinkedIn, TikTok, or similar platform pages through direct scraping
- any logged-in area
- pages protected by technical access restrictions

Explicitly out of scope:

1. leaked databases
2. breached credentials
3. unauthorized account access
4. stealth workflows that depend on bypassing platform controls

## Competitor notes

As checked on 2026-04-03 from official sources:

### Snov.io

- Snov.io packages prospecting, verification, outreach, CRM, and LinkedIn automation into one stack.
- The pricing page shows a Starter plan at `$29.25/mo` billed annually and a Pro tier starting at `$74.25/mo`, with LinkedIn automation sold as an add-on.
- The product highlights unlimited team seats, multichannel campaigns, CRM, and API/webhooks.
- Official source: https://snov.io/pricing
- Security and compliance messaging is also explicit in the Snov.io Security Center.
- Official source: https://snov.io/security-center

### Apollo

- Apollo positions around outbound, inbound, data enrichment, deal execution, AI assistant, workflow automation, and Chrome-based prospecting.
- The pricing page states a free tier exists, the trial includes `50 credits` and `5 mobile credits`, and Apollo presents itself as `GDPR Compliant`.
- Apollo also exposes a Privacy Center, opt-out flow, and public compliance claims such as ISO 27001 and SOC 2.
- Official sources:
  - https://www.apollo.io/pricing
  - https://www.apollo.io/company/privacy-center
  - https://knowledge.apollo.io/hc/en-us/articles/19207906524557-Enable-Do-Not-Call-DNC-Phone-Screening

### Clay

- Clay frames pricing around actions plus third-party data credits, which creates strong source-cost transparency.
- Clay Docs list Launch starting at `$185/month`, Growth starting at `$495/month`, and Enterprise as custom.
- Clay also makes data credit mechanics explicit and ties higher plans to CRM integrations, HTTP API, intent signals, and automation.
- Official source: https://university.clay.com/docs/plans-and-billing

## Product decisions derived from that research

LeadAgent should ship with:

- visible source type on every lead
- consent and verification state on every lead
- owned lead import as a first-class workflow
- strategy guidance after each search pass
- quick export for CRM or operator review

LeadAgent should not ship with:

- any promise of a giant private database
- hidden provenance
- ambiguous compliance posture
- claims that arbitrary product input alone can already produce a customer list without operator-supplied buyer hypotheses or discovery queries

## Capability boundary

As verified on 2026-04-06, LeadAgent's public-web workflow generalizes beyond the original Hajj/Islamic-adjacent scenarios into unrelated B2B categories, but it still behaves like an operator-assisted sourcing system rather than a universal autonomous customer finder.

The detailed verdict and benchmark evidence are documented in `docs/generalization-verdict.md`.
The recommended social-media expansion path is documented in `docs/social-media-compliant-architecture.md`.
The delivery sequence for that path is documented in `docs/social-mvp-delivery-plan.md`.
The current product now includes a local persisted social-connector foundation and connector catalog for owned-asset LinkedIn and Meta workflows.

## Pricing direction

Recommended initial pricing direction:

- Starter: low monthly fee for solo operators, demo pipeline, import, score, export
- Team: multi-user review, CRM sync, audit trail, compliance controls
- Custom: managed onboarding, governance, data partner integrations

This is an inferred pricing direction, not validated customer demand yet.

## Immediate next steps

1. Validate the new dashboard and import flow with a real customer-owned CSV.
2. Add CRM connectors for HubSpot and Salesforce sync.
3. Introduce audit logs and role-based governance before production rollout.
4. Remove or quarantine legacy scraping-first flows from the default UX.
5. Build a `product -> buyer hypotheses -> query plan` strategy layer before claiming broad arbitrary-product coverage.
6. Build owned-asset social connectors for LinkedIn Lead Sync and Meta lead ads instead of profile scraping.
7. Replace the local file-backed social connector persistence layer with database-backed storage and real OAuth token handling.
