"""
Shared authentication and credential management for Google Cloud services.
"""

import logging
from typing import Any
import google.auth
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from ..config import Settings, get_settings

logger = logging.getLogger(__name__)


class CredentialManager:
    """Manages acquisition and refreshing of Google Cloud Application Default Credentials (ADC)."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._cached_credentials: Any = None
        self._auth_project: str | None = None

    def get_credentials(self, scopes: list[str] | None = None) -> tuple[Any, str | None]:
        """Returns valid Google Cloud credentials and inferred project ID."""
        try:
            if self._cached_credentials is None:
                if scopes:
                    credentials, project = google.auth.default(scopes=scopes)
                else:
                    credentials, project = google.auth.default()
                self._cached_credentials = credentials
                self._auth_project = project

            if hasattr(self._cached_credentials, "valid") and not self._cached_credentials.valid:
                self._cached_credentials.refresh(Request())

            return self._cached_credentials, (self.settings.gcp_project or self._auth_project)
        except GoogleAuthError as e:
            logger.error(f"Failed to acquire Google credentials: {e}")
            raise

    def get_access_token(self, scopes: list[str] | None = None) -> str:
        """Returns a valid Bearer access token string."""
        creds, _ = self.get_credentials(
            scopes=scopes or ["https://www.googleapis.com/auth/cloud-platform"]
        )
        if not getattr(creds, "token", None) and hasattr(creds, "refresh"):
            creds.refresh(Request())
        if hasattr(creds, "token") and creds.token:
            return creds.token
        raise GoogleAuthError("Unable to extract token string from credentials.")
