from __future__ import annotations

from app.models import (
    LeadSourceType,
    Platform,
    SocialAssetType,
    SocialConnectorDefinition,
    SocialConnectorField,
    SocialConnectorKey,
    SocialSyncMode,
)


LINKEDIN_LEAD_SYNC = SocialConnectorDefinition(
    connector_key=SocialConnectorKey.linkedin_lead_sync,
    platform=Platform.linkedin,
    display_name="LinkedIn Lead Sync",
    required_scopes=["r_ads", "r_organization_social", "rw_events"],
    supported_sync_modes=[SocialSyncMode.webhook, SocialSyncMode.pull, SocialSyncMode.hybrid],
    supported_asset_types=[
        SocialAssetType.organization,
        SocialAssetType.ad_account,
        SocialAssetType.form,
        SocialAssetType.campaign,
        SocialAssetType.event,
        SocialAssetType.product_page,
    ],
    supported_source_type=LeadSourceType.first_party_social,
    webhook_supported=True,
    backfill_supported=True,
    audience_sync_supported=False,
    onboarding_steps=[
        "Confirm partner access and customer-owned LinkedIn assets.",
        "Complete OAuth and select organizations, sponsored accounts, and lead forms.",
        "Enable webhook delivery and run an initial lead backfill.",
        "Review mapped fields and route qualified leads into CRM workflows.",
    ],
    expected_lead_fields=[
        SocialConnectorField(key="company", label="Company", required=False, description="Submitted company or organization name."),
        SocialConnectorField(key="contact_name", label="Full name", required=False, description="Submitted lead contact name."),
        SocialConnectorField(key="email", label="Email", required=False, description="Lead form email response."),
        SocialConnectorField(key="phone", label="Phone", required=False, description="Lead form phone response when provided."),
        SocialConnectorField(key="source_external_lead_id", label="External lead id", required=True, description="LinkedIn lead or submission id."),
        SocialConnectorField(key="source_form_id", label="Form id", required=True, description="LinkedIn lead form urn."),
        SocialConnectorField(key="source_campaign_id", label="Campaign id", required=False, description="Sponsored campaign urn."),
        SocialConnectorField(key="source_submission_timestamp", label="Submission time", required=True, description="Lead submission timestamp."),
    ],
    notes=[
        "Use only official LinkedIn Lead Sync style workflows; do not scrape profile data.",
        "Store organization, sponsored account, and form provenance for every lead.",
    ],
)


META_LEAD_ADS = SocialConnectorDefinition(
    connector_key=SocialConnectorKey.meta_lead_ads,
    platform=Platform.facebook,
    display_name="Meta Lead Ads",
    required_scopes=["leads_retrieval", "ads_management", "pages_read_engagement"],
    supported_sync_modes=[SocialSyncMode.webhook, SocialSyncMode.pull, SocialSyncMode.hybrid],
    supported_asset_types=[
        SocialAssetType.page,
        SocialAssetType.ad_account,
        SocialAssetType.form,
        SocialAssetType.campaign,
        SocialAssetType.business_account,
    ],
    supported_source_type=LeadSourceType.first_party_social,
    webhook_supported=True,
    backfill_supported=True,
    audience_sync_supported=False,
    onboarding_steps=[
        "Connect a customer-owned Meta business asset set.",
        "Select pages, ad accounts, and instant forms to ingest.",
        "Enable lead webhooks and reconcile historical submissions.",
        "Review consent text and privacy-policy provenance before CRM export.",
    ],
    expected_lead_fields=[
        SocialConnectorField(key="company", label="Company", required=False, description="Submitted company name when available."),
        SocialConnectorField(key="contact_name", label="Full name", required=False, description="Submitted lead name."),
        SocialConnectorField(key="email", label="Email", required=False, description="Lead form email response."),
        SocialConnectorField(key="phone", label="Phone", required=False, description="Lead form phone response."),
        SocialConnectorField(key="source_external_lead_id", label="External lead id", required=True, description="Meta leadgen id."),
        SocialConnectorField(key="source_form_id", label="Form id", required=True, description="Instant form id."),
        SocialConnectorField(key="source_page_id", label="Page id", required=False, description="Facebook Page or Instagram asset id."),
        SocialConnectorField(key="source_submission_timestamp", label="Submission time", required=True, description="Lead submission timestamp."),
    ],
    notes=[
        "Use official Meta lead-ad workflows only; no Page or profile scraping.",
        "Preserve page, ad account, campaign, and form provenance on every synced lead.",
    ],
)


CONNECTOR_REGISTRY: dict[SocialConnectorKey, SocialConnectorDefinition] = {
    LINKEDIN_LEAD_SYNC.connector_key: LINKEDIN_LEAD_SYNC,
    META_LEAD_ADS.connector_key: META_LEAD_ADS,
}


def list_social_connectors() -> list[SocialConnectorDefinition]:
    return list(CONNECTOR_REGISTRY.values())


def get_social_connector(connector_key: SocialConnectorKey | str) -> SocialConnectorDefinition | None:
    try:
        normalized = connector_key if isinstance(connector_key, SocialConnectorKey) else SocialConnectorKey(str(connector_key))
    except ValueError:
        return None
    return CONNECTOR_REGISTRY.get(normalized)


def default_connector_key_for_platform(platform: Platform) -> SocialConnectorKey:
    if platform == Platform.linkedin:
        return SocialConnectorKey.linkedin_lead_sync
    if platform in {Platform.facebook, Platform.instagram}:
        return SocialConnectorKey.meta_lead_ads
    raise ValueError(f"No official social connector registered for platform '{platform.value}'.")


def validate_connector_platform(connector_key: SocialConnectorKey, platform: Platform) -> None:
    connector = CONNECTOR_REGISTRY.get(connector_key)
    if connector is None:
        raise ValueError(f"Unsupported connector '{connector_key.value}'.")
    if connector.platform != platform and not (
        connector.connector_key == SocialConnectorKey.meta_lead_ads and platform == Platform.instagram
    ):
        raise ValueError(f"Connector '{connector_key.value}' does not match platform '{platform.value}'.")
