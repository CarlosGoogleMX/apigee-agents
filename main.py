"""
Top-level entrypoint and compatibility module for Apigee Error Diagnostic Agent.
Re-exports root_agent from `apigee_agent` package.
Supports running as an HTTP web server with static report serving for local and Cloud Run deployments.
"""

import os
import sys
from apigee_agent.agent import root_agent

__all__ = ["root_agent", "app"]


def create_app():
    from fastapi.staticfiles import StaticFiles
    from google.adk.cli import fast_api

    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0" if "K_SERVICE" in os.environ else "127.0.0.1"

    fastapi_app = fast_api.get_fast_api_app(
        agents_dir=".",
        web=True,
        host=host,
        port=port,
    )

    sent_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "sent_emails"
    )
    os.makedirs(sent_dir, exist_ok=True)
    fastapi_app.mount("/reports", StaticFiles(directory=sent_dir), name="reports")
    return fastapi_app


# Expose `app` at module level for ASGI servers (e.g. gunicorn/uvicorn main:app)
try:
    app = create_app()
except Exception as e:
    app = None


def run_server():
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0" if "K_SERVICE" in os.environ else "127.0.0.1"

    print(f"Starting Apigee Agent Web Server on http://{host}:{port}")
    print(
        f"HTML diagnostic reports are viewable at http://{host}:{port}/reports/<filename>"
    )
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    if "--server" in sys.argv or "K_SERVICE" in os.environ:
        run_server()
    else:
        print(f"Agent '{root_agent.name}' initialized and ready.")
        print(f"Model configured: {root_agent.model}")
        print(f"Tools available: {[tool.__name__ for tool in root_agent.tools]}")
        print(
            "\nTip: To run as an HTTP web server (for Cloud Run or local report viewing), execute:"
        )
        print("     uv run main.py --server")