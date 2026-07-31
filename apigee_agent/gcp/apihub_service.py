"""
Google Cloud API Hub service for querying API proxy owner emails.
"""

import logging
import functools
from dataclasses import dataclass
from typing import Any
import requests
from ..config import Settings, get_settings, resolve_organization_alias
from .auth import CredentialManager

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProxyOwnerResult:
    status: str
    proxy_name: str | None = None
    owner_email: str | None = None
    owner_name: str | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        if self.status == "success":
            return {
                "status": "success",
                "proxy_name": self.proxy_name,
                "owner_email": self.owner_email,
                "owner_name": self.owner_name,
            }
        return {"status": "error", "message": self.message}


class APIHubService:
    """Service class for querying API Hub REST endpoints with connection pooling."""

    def __init__(self, settings: Settings | None = None, cred_manager: CredentialManager | None = None):
        self.settings = settings or get_settings()
        self.cred_manager = cred_manager or CredentialManager(self.settings)
        self.session = requests.Session()

    def _get_project(self, organization: str | None) -> str | None:
        project = None
        if organization:
            project = resolve_organization_alias(organization)
        if not project:
            project = self.settings.gcp_project
        if not project:
            try:
                _, inferred = self.cred_manager.get_credentials()
                project = inferred
            except Exception:
                pass
        return project

    def _make_request(self, url: str, token: str) -> dict[str, Any]:
        response = self.session.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            timeout=3.0,
            verify=False,
        )
        response.raise_for_status()
        return response.json()

    @functools.lru_cache(maxsize=32)
    def _list_apis_cached(self, list_url: str, token: str) -> dict[str, Any]:
        return self._make_request(list_url, token)

    @functools.lru_cache(maxsize=256)
    def get_owner_email(
        self, proxy_name: str, organization: str | None = None
    ) -> dict[str, Any]:
        """Queries GCP API Hub to retrieve the owner email address of an API proxy."""
        project = self._get_project(organization)
        if not project:
            return ProxyOwnerResult(
                status="error",
                message="GCP_PROJECT environment variable is not defined.",
            ).to_dict()

        try:
            token = self.cred_manager.get_access_token()
        except Exception as e:
            return ProxyOwnerResult(
                status="error", message=f"Authentication failed: {str(e)}"
            ).to_dict()

        location = self.settings.apihub_location

        # 1. Try direct fetch for this proxy name
        direct_url = f"https://apihub.googleapis.com/v1/projects/{project}/locations/{location}/apis/{proxy_name}"
        try:
            data = self._make_request(direct_url, token)
            owner = data.get("owner", {})
            email = owner.get("email")
            if email:
                return ProxyOwnerResult(
                    status="success",
                    proxy_name=proxy_name,
                    owner_email=email,
                    owner_name=owner.get("displayName", "Owner Team"),
                ).to_dict()
        except Exception:
            pass

        # 2. Try querying APIs list and searching for match
        list_url = f"https://apihub.googleapis.com/v1/projects/{project}/locations/{location}/apis"
        try:
            data = self._list_apis_cached(list_url, token)
            apis = data.get("apis", [])
            for api in apis:
                api_name = api.get("name", "")
                display_name = api.get("displayName", "")
                api_id = api_name.split("/")[-1] if "/" in api_name else api_name
                if proxy_name.lower() in [api_id.lower(), display_name.lower()]:
                    owner = api.get("owner", {})
                    email = owner.get("email")
                    if email:
                        return ProxyOwnerResult(
                            status="success",
                            proxy_name=proxy_name,
                            owner_email=email,
                            owner_name=owner.get("displayName", "Owner Team"),
                        ).to_dict()
        except Exception as e:
            logger.warning(f"Failed listing APIs from API Hub: {e}")

        default_email = self.settings.default_owner_email
        if default_email:
            return ProxyOwnerResult(
                status="success",
                proxy_name=proxy_name,
                owner_email=default_email,
                owner_name="Equipo de Soporte/Operaciones API (Default)",
            ).to_dict()

        return ProxyOwnerResult(
            status="error",
            message=f"No owner email registered for proxy '{proxy_name}' in API Hub and no DEFAULT_OWNER_EMAIL was set.",
        ).to_dict()
