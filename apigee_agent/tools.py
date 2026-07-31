"""
Lightweight Google ADK Tool adapters wrapping core domain services.
"""

from datetime import datetime, timezone
from typing import Any
from .catalogue.service import CatalogueService
from .gcp.logging_service import LoggingService
from .gcp.apihub_service import APIHubService
from .notifications.email_service import EmailService

# Singleton service instances for tool execution
_catalogue_service = CatalogueService()
_logging_service = LoggingService()
_apihub_service = APIHubService()
_email_service = EmailService()

_last_logs_cache: list[dict[str, Any]] = []


def lookup_business_reference(reference: str) -> dict[str, Any]:
    """
    Looks up a human-readable business reference in the catalogue to find
    associated technical names like API proxies, API product, and environment.
    """
    return _catalogue_service.lookup(reference)


def get_current_time() -> str:
    """
    Returns the current time in ISO 8601 format (UTC).
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def get_cloud_logs(
    environment: str,
    start_time: str | None = None,
    end_time: str | None = None,
    time_range: str | None = None,
    api_proxies: list[str] | None = None,
    api_product: str | None = None,
    client_id: str | None = None,
    target_server: str | None = None,
    n_results: int = 20,
    error_codes: list[int] | None = None,
    organization: str | None = None,
) -> dict[str, Any]:
    """
    Retrieves logs with common error status codes from Cloud Logging.
    Supports relative natural-language time_range (e.g., 'last 15 minutes', 'last 2 hours') or explicit ISO 8601 start_time and end_time.
    Automatically resolves business terms in api_proxies (e.g. 'onboarding' -> 'onboarding-v1-proxy').
    """
    res = _logging_service.fetch_error_logs(
        environment=environment,
        start_time=start_time,
        end_time=end_time,
        time_range=time_range,
        api_proxies=api_proxies,
        api_product=api_product,
        client_id=client_id,
        target_server=target_server,
        n_results=n_results,
        error_codes=error_codes,
        organization=organization,
    )
    if isinstance(res, dict) and isinstance(res.get("logs"), list):
        global _last_logs_cache
        _last_logs_cache = res["logs"]
    return res


def get_api_owner_email(
    proxy_name: str, organization: str | None = None
) -> dict[str, Any]:
    """
    Queries GCP API Hub to retrieve the owner email address of a given API proxy.
    
    Args:
        proxy_name: The name of the API proxy.
        organization: Optional Apigee Organization name/alias.
    """
    return _apihub_service.get_owner_email(
        proxy_name=proxy_name, organization=organization
    )


def send_diagnostic_email(
    recipient_email: str,
    proxy_name: str,
    error_summary: str,
    logs_details: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Sends a beautifully styled HTML diagnostic alert to the API proxy owner email.
    If logs_details is omitted or None, automatically attaches the last retrieved error logs from get_cloud_logs.
    
    Args:
        recipient_email: Email address of the proxy owner.
        proxy_name: The name of the API proxy.
        error_summary: Summarized diagnosis of the failure.
        logs_details: Optional list of failure log records (omit to auto-attach last retrieved logs).
    """
    if not logs_details:
        logs_details = _last_logs_cache
    return _email_service.send_diagnostic_email(
        recipient_email=recipient_email,
        proxy_name=proxy_name,
        error_summary=error_summary,
        logs_details=logs_details,
    )
