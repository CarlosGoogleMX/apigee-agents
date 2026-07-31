"""
Google Cloud Logging query service for Apigee API proxy error logs.
"""

import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Any
from google.cloud import logging_v2
from google.auth.exceptions import GoogleAuthError
from ..config import Settings, get_settings, resolve_organization_alias
from .auth import CredentialManager
from ..catalogue.service import CatalogueService

_catalogue = CatalogueService()


def _resolve_time_bounds(
    start_time: str | None, end_time: str | None, time_range: str | None
) -> tuple[str, str]:
    """Resolves relative natural-language time_range expressions to UTC ISO 8601 timestamps."""
    now = datetime.now(timezone.utc)
    end_dt = now
    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        except Exception:
            pass

    if start_time and end_time and not time_range:
        return start_time, end_time

    delta = timedelta(hours=2)
    query_str = (time_range or start_time or "").lower()
    m = re.search(
        r"(\d+)\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)",
        query_str,
    )
    if m:
        val = int(m.group(1))
        unit = m.group(2)
        if unit.startswith("m"):
            delta = timedelta(minutes=val)
        elif unit.startswith("h"):
            delta = timedelta(hours=val)
        elif unit.startswith("d"):
            delta = timedelta(days=val)

    start_dt = end_dt - delta
    return (
        start_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        end_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    )


def _resolve_api_proxies(api_proxies: list[str] | None) -> list[str] | None:
    """Resolves business references (e.g. 'onboarding') to technical API proxy names."""
    if not api_proxies:
        return None
    resolved = []
    for proxy in api_proxies:
        lookup_res = _catalogue.lookup(proxy)
        if lookup_res.get("status") == "success" and "apiProxy" in lookup_res:
            resolved.append(lookup_res["apiProxy"])
        else:
            resolved.append(proxy)
    return resolved

logger = logging.getLogger(__name__)

# Pre-compiled regex for stripping large base64 strings in log payloads
BASE64_CONTENT_REGEX = re.compile(r'("content"\s*:\s*")[^"]{500,}(")')


class LoggingService:
    """Service class for querying and sanitizing Google Cloud Logging entries."""

    def __init__(self, settings: Settings | None = None, cred_manager: CredentialManager | None = None):
        self.settings = settings or get_settings()
        self.cred_manager = cred_manager or CredentialManager(self.settings)
        self._client_cache: dict[str, logging_v2.Client] = {}

    def _get_client(self, project_id: str, credentials: Any) -> logging_v2.Client:
        cache_key = f"{project_id}_{id(credentials)}"
        if cache_key not in self._client_cache:
            self._client_cache[cache_key] = logging_v2.Client(
                project=project_id, credentials=credentials
            )
        return self._client_cache[cache_key]

    @staticmethod
    def clean_log_entry(payload: Any) -> Any:
        """Sanitizes log payloads by extracting concise diagnostic fields to avoid token overflow."""
        if not isinstance(payload, dict):
            return payload

        p_dict = (
            payload.get("jsonPayload")
            if isinstance(payload.get("jsonPayload"), dict)
            else payload
        )
        concise = {
            "timestamp": payload.get("timestamp")
            or p_dict.get("clientReceived")
            or "N/A",
            "responseCode": p_dict.get("responseCode")
            or p_dict.get("proxyResponseCode")
            or payload.get("responseCode")
            or "UNKNOWN",
            "clientIp": p_dict.get("clienteIP")
            or p_dict.get("clientIp")
            or payload.get("clientIp")
            or "N/A",
            "message": p_dict.get("fault", {}).get("reason")
            or p_dict.get("fault", {}).get("name")
            or p_dict.get("message")
            or payload.get("message")
            or payload.get("textPayload")
            or "N/A",
            "apiProxy": p_dict.get("apiProxy") or payload.get("apiProxy"),
            "environment": p_dict.get("environment") or payload.get("environment"),
        }
        return {k: v for k, v in concise.items() if v is not None}

    def fetch_error_logs(
        self,
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
        """Retrieves and sanitizes error logs from Cloud Logging matching criteria."""
        try:
            start_time_iso, end_time_iso = _resolve_time_bounds(
                start_time, end_time, time_range
            )
            api_proxies = _resolve_api_proxies(api_proxies)

            project_id = None
            if organization:
                project_id = resolve_organization_alias(organization)
            if not project_id:
                project_id = self.settings.gcp_project

            try:
                credentials, auth_project = self.cred_manager.get_credentials()
                project_id = project_id or auth_project
            except GoogleAuthError as e:
                return {
                    "status": "error",
                    "logs": f"Failed to acquire credentials. Please authenticate via `gcloud auth application-default login` or use a Service Account. Details: {str(e)}",
                }

            if not project_id:
                return {
                    "status": "error",
                    "logs": "GCP_PROJECT environment variable not set and could not be inferred from credentials.",
                }

            client = self._get_client(project_id, credentials)

            # Construct filter
            filter_parts = [f'jsonPayload.environment="{environment}"']
            if api_proxies:
                proxies_filter = " OR ".join(
                    [f'jsonPayload.apiProxy="{proxy}"' for proxy in api_proxies]
                )
                filter_parts.append(f"({proxies_filter})")
            if api_product:
                filter_parts.append(f'jsonPayload.apiProduct="{api_product}"')
            if client_id:
                filter_parts.append(f'jsonPayload.clientId="{client_id}"')
            if target_server:
                filter_parts.append(f'jsonPayload.targetServer="{target_server}"')

            filter_str = " AND ".join(filter_parts)
            filter_str += f' AND timestamp >= "{start_time_iso}" AND timestamp <= "{end_time_iso}"'

            if not error_codes:
                error_codes = [500, 503, 504, 403, 401, 400, 404]

            error_filter = " OR ".join(
                [
                    f'(jsonPayload.responseCode = "{code}" OR jsonPayload.responseCode = {code} OR '
                    f'jsonPayload.proxyResponseCode = "{code}" OR jsonPayload.proxyResponseCode = {code} OR '
                    f'jsonPayload.logs.statusCode = {code})'
                    for code in error_codes
                ]
            )
            filter_str += f" AND ({error_filter})"

            logger.info(f"Constructed filter query: {filter_str}")

            entries = client.list_entries(
                filter_=filter_str,
                max_results=n_results,
                page_size=min(n_results, 500),
            )

            logs = []
            for entry in entries:
                payload = self.clean_log_entry(entry.payload)
                if isinstance(payload, dict):
                    ts = getattr(entry, "timestamp", None)
                    if ts and "timestamp" not in payload:
                        payload["timestamp"] = (
                            ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
                        )
                logs.append(payload)
            if not logs:
                return {
                    "status": "success",
                    "summary": "No error logs found for the given time range and filter criteria.",
                    "logs": "No logs found for the given criteria.",
                }

            status_counts: dict[str, int] = {}
            for l in logs:
                code = str(
                    l.get("responseCode") or l.get("proxyResponseCode") or "UNKNOWN"
                )
                status_counts[code] = status_counts.get(code, 0) + 1

            summary = f"Total logs retrieved: {len(logs)}."
            if status_counts:
                summary += f" Status code breakdown: {status_counts}."

            return {"status": "success", "summary": summary, "logs": logs}
        except Exception as e:
            logger.error(f"Error fetching logs: {e}", exc_info=False)
            return {"status": "error", "logs": f"An unexpected error occurred: {e}"}
