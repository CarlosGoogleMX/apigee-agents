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

def _parse_time_frame(time_frame: str) -> Optional[Tuple[str, str]]:
    """
    Parses a human-readable time frame string (e.g., "last 3 hours") and returns a tuple
    of (startTime, endTime) in ISO 8601 format (UTC).
    """
    match = re.search(r"last\s+(\d+)\s+(hour|hours|minute|minutes|day|days)", time_frame, re.IGNORECASE)
    if not match:
        return None

    value = int(match.group(1))
    unit = match.group(2).lower()
    now = datetime.now(timezone.utc)

    if unit.startswith("hour"):
        delta = timedelta(hours=value)
    elif unit.startswith("minute"):
        delta = timedelta(minutes=value)
    elif unit.startswith("day"):
        delta = timedelta(days=value)
    else:
        return None

    start_time = now - delta
    end_time = now

    # Format timestamp for Google Cloud Logging (RFC3339 / ISO 8601 subset)
    return start_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ'), end_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def get_cloud_logs(api_proxy: str, environment: str, time_frame: str, n_results: int = 100, error_codes: Optional[List[int]] = None) -> Dict[str, Any]:
    """
    Retrieves logs with common error status codes from Cloud Logging for a given
    API proxy, environment, and time frame.
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
        filter_str = f'jsonPayload.apiProxy="{api_proxy}" AND jsonPayload.environment="{environment}"'

        # Add time frame to filter - Guard against invalid LLM arguments
        parsed_time = _parse_time_frame(time_frame)
        if parsed_time:
            start_time, end_time = parsed_time
            filter_str += f' AND timestamp >= "{start_time}" AND timestamp <= "{end_time}"'
        else:
            return {"status": "error", "logs": f"Invalid time_frame format: '{time_frame}'. Please use string formats like 'last 3 hours', 'last 30 minutes', 'last 2 days'."}

        # Add filter for common error status codes
        if not error_codes:
            error_codes = [500, 503, 504, 403, 401, 400, 404]
            
        error_filter = " OR ".join([f'jsonPayload.logs.statusCode = {code}' for code in error_codes])
        filter_str += f" AND ({error_filter})"

        logger.info(f"Constructed filter query: {filter_str}")

        # Ensure we strictly limit the returned logs with max_results instead of just controlling the page chunking logic
        entries = client.list_entries(
            filter_=filter_str,
            max_results=n_results,
        )

        logs = [entry.payload for entry in entries]

        if not logs:
            return {"status": "success", "logs": "No logs found for the given criteria."}

        return {"status": "success", "logs": logs}

    except Exception as e:
        logger.error(f"Error fetching logs: {e}", exc_info=False)
        return {"status": "error", "logs": f"An unexpected error occurred: {e}"}