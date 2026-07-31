"""
Apigee Error Diagnostic Agent - Core Modular Package
Follows modern Python 3.10+ best practices and Google ADK architecture.
"""

import os
import sys

_pkg_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_pkg_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from .agent import root_agent

# Hook into Google ADK's FastAPI app creator to automatically mount /reports
# whenever `adk web`, `adk api_server`, or Cloud Run containers run.
try:
    from google.adk.cli import fast_api
    from fastapi.staticfiles import StaticFiles

    _original_get_fast_api_app = fast_api.get_fast_api_app

    def _patched_get_fast_api_app(*args, **kwargs):
        app = _original_get_fast_api_app(*args, **kwargs)
        sent_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "sent_emails",
        )
        os.makedirs(sent_dir, exist_ok=True)
        # Mount /reports if not already mounted
        if not any(getattr(route, "path", None) == "/reports" for route in app.routes):
            app.mount("/reports", StaticFiles(directory=sent_dir), name="reports")
        return app

    fast_api.get_fast_api_app = _patched_get_fast_api_app
except ImportError:
    pass

__all__ = ["root_agent"]
