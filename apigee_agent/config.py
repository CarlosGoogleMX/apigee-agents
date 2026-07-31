"""
Centralized configuration, dynamic mappings, and environment settings.
Agnostic to any specific customer or GCP organization.
"""

import os
import json
import functools
from dataclasses import dataclass


def _load_org_mappings() -> dict[str, list[str]]:
    """Loads optional organization alias mappings from environment JSON."""
    raw = os.environ.get("ORG_MAPPINGS_JSON", "{}")
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _clean_text(str_val: str) -> str:
    """Helper to normalize text for organization alias comparisons."""
    str_val = str_val.lower().strip()
    replacements = [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")]
    for src, dest in replacements:
        str_val = str_val.replace(src, dest)
    return str_val.replace("-", " ")


def _build_precleaned_mappings() -> dict[str, tuple[list[str], list[set[str]]]]:
    mappings = _load_org_mappings()
    return {
        org_id: (
            [_clean_text(org_id)] + [_clean_text(alias) for alias in aliases],
            [set(_clean_text(alias).split()) for alias in aliases],
        )
        for org_id, aliases in mappings.items()
    }


PRECLEANED_ORG_MAPPINGS = _build_precleaned_mappings()


@functools.lru_cache(maxsize=128)
def resolve_organization_alias(alias_or_id: str) -> str:
    """
    Resolves human-readable aliases to canonical Apigee Organization or Project IDs.
    If no alias matches, returns alias_or_id directly as the target project/org.
    """
    val_clean = _clean_text(alias_or_id)

    # 1. Check direct match or exact alias match against pre-cleaned map
    for org_id, (cleaned_aliases, _) in PRECLEANED_ORG_MAPPINGS.items():
        if val_clean in cleaned_aliases:
            return org_id

    # 2. Check subset word matches
    val_words = set(val_clean.split())
    for org_id, (_, alias_words_list) in PRECLEANED_ORG_MAPPINGS.items():
        for alias_words in alias_words_list:
            if alias_words.issubset(val_words) or val_words.issubset(alias_words):
                return org_id

    return alias_or_id


@dataclass(frozen=True)
class Settings:
    """Immutable application configuration loaded from environment variables."""

    gcp_project: str | None
    apihub_location: str
    default_owner_email: str
    company_name: str
    logo_url: str
    smtp_host: str | None
    smtp_port: int
    smtp_user: str | None
    smtp_password: str | None
    smtp_from: str

    @classmethod
    def from_env(cls) -> "Settings":
        smtp_port_raw = os.environ.get("SMTP_PORT", "587")
        try:
            smtp_port = int(smtp_port_raw)
        except ValueError:
            smtp_port = 587

        return cls(
            gcp_project=(
                os.environ.get("GCP_PROJECT")
                or os.environ.get("GOOGLE_CLOUD_PROJECT")
                or os.environ.get("GCLOUD_PROJECT")
            ),
            apihub_location=os.environ.get("APIHUB_LOCATION", "global"),
            default_owner_email=os.environ.get(
                "DEFAULT_OWNER_EMAIL", "api-ops@example.com"
            ),
            company_name=os.environ.get("COMPANY_NAME", "API Operations Team"),
            logo_url=os.environ.get(
                "LOGO_URL",
                "https://cloud.google.com/_static/cloud/images/social-icon-google-cloud-1200-630.png",
            ),
            smtp_host=os.environ.get("SMTP_HOST"),
            smtp_port=smtp_port,
            smtp_user=os.environ.get("SMTP_USER"),
            smtp_password=os.environ.get("SMTP_PASSWORD"),
            smtp_from=os.environ.get("SMTP_FROM", "apigee-alerts@example.com"),
        )


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Returns the singleton Settings instance."""
    return Settings.from_env()
