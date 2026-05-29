import os
import re
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List, Dict, Any

import google.auth
from google.cloud import logging_v2
from google.oauth2.credentials import Credentials
from google.auth.exceptions import GoogleAuthError

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def _clean_log_entry(payload: Any) -> Any:
    """
    Cleans a log entry payload by truncating large fields in the 'logs' array.
    Specifically targets base64 encoded data or large XML/JSON strings.
    """
    if not isinstance(payload, dict):
        return payload
        
    logs_array = None
    if "logs" in payload:
        logs_array = payload["logs"]
    elif "jsonPayload" in payload and isinstance(payload["jsonPayload"], dict):
        logs_array = payload["jsonPayload"].get("logs")
        
    if logs_array and isinstance(logs_array, list):
        for log in logs_array:
                    if isinstance(log, dict) and "payload" in log:
                        content = log["payload"]
                        if isinstance(content, str):
                            # First remove massive base64 strings if type property indicates it
                            if '"type":"base64"' in content or '"type": "base64"' in content:
                                content = re.sub(r'("content"\s*:\s*")[^"]{500,}(")', r'\1[BASE64 CONTENT REMOVED]\2', content)
                                log["payload"] = content
                            
                            # Fallback to general truncation if remaining text is still heavy
                            if len(content) > 1000:
                                log["payload"] = content[:1000] + "... [TRUNCATED to prevent token overflow]"
    return payload

def _parse_time_frame(time_frame: str) -> Optional[Tuple[str, str]]:
    return start_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ'), end_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def get_current_time() -> str:
    """
    Returns the current time in ISO 8601 format (UTC).
    """
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')



def get_cloud_logs(
    environment: str, 
    start_time: str, 
    end_time: str, 
    api_proxies: Optional[List[str]] = None, 
    api_product: Optional[str] = None, 
    client_id: Optional[str] = None, 
    target_server: Optional[str] = None, 
    n_results: int = 100, 
    error_codes: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Retrieves logs with common error status codes from Cloud Logging.
    Allows filtering by environment, time_frame, and optionally api_proxies, api_product, client_id, and target_server.
    """
    try:
        project_id = os.environ.get("GCP_PROJECT")
        
        # Determine credentials
        token = os.environ.get("OAUTH_TOKEN")
        credentials = None
        
        try:
            if token:
                logger.info("Using provided OAUTH_TOKEN for authentication.")
                credentials = Credentials(token)
            else:
                logger.info("OAUTH_TOKEN not found. Falling back to Application Default Credentials.")
                credentials, auth_project = google.auth.default()
                project_id = project_id or auth_project
        except GoogleAuthError as e:
            return {"status": "error", "logs": f"Failed to acquire credentials. Please authenticate via `gcloud auth application-default login` or set the OAUTH_TOKEN environment variable. Details: {str(e)}"}
            
        if not project_id:
            return {"status": "error", "logs": "GCP_PROJECT environment variable not set and could not be inferred from credentials."}

        client = logging_v2.Client(project=project_id, credentials=credentials)

        # Construct the base filter
        filter_parts = [f'jsonPayload.environment="{environment}"']

        if api_proxies:
            proxies_filter = " OR ".join([f'jsonPayload.apiProxy="{proxy}"' for proxy in api_proxies])
            filter_parts.append(f"({proxies_filter})")
        if api_product:
            filter_parts.append(f'jsonPayload.apiProduct="{api_product}"')
        if client_id:
            filter_parts.append(f'jsonPayload.clientId="{client_id}"')
        if target_server:
            filter_parts.append(f'jsonPayload.targetServer="{target_server}"')

        filter_str = " AND ".join(filter_parts)

        # Add time range to filter
        filter_str += f' AND timestamp >= "{start_time}" AND timestamp <= "{end_time}"'

        # Add filter for common error status codes
        if not error_codes:
            error_codes = [500, 502, 503, 504, 403, 401, 400, 404]
            
        error_filter = " OR ".join([f'jsonPayload.responseCode = {code}' for code in error_codes])
        filter_str += f" AND ({error_filter})"

        logger.info(f"Constructed filter query: {filter_str}")

        # Ensure we strictly limit the returned logs with max_results instead of just controlling the page chunking logic
        entries = client.list_entries(
            filter_=filter_str,
            max_results=n_results,
        )

        logs = [_clean_log_entry(entry.payload) for entry in entries]

        if not logs:
            return {"status": "success", "logs": "No logs found for the given criteria."}

        return {"status": "success", "logs": logs}

    except Exception as e:
        logger.error(f"Error fetching logs: {e}", exc_info=False)
        return {"status": "error", "logs": f"An unexpected error occurred: {e}"}
