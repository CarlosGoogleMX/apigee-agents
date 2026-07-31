"""
Email notification sender service for diagnostic alerts.
"""

import os
import smtplib
import logging
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any
from ..config import Settings, get_settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for rendering and dispatching HTML diagnostic alert emails."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.template_path = os.path.join(
            os.path.dirname(__file__), "templates", "alert_email.html"
        )

    def _render_table_rows(self, logs_details: list[dict[str, Any]]) -> str:
        rows: list[str] = []
        for log in logs_details:
            payload_dict = (
                log.get("jsonPayload")
                if isinstance(log.get("jsonPayload"), dict)
                else log
            )
            timestamp = (
                log.get("timestamp")
                or log.get("clientReceived")
                or payload_dict.get("clientReceived")
                or "N/A"
            )
            message = (
                log.get("textPayload")
                or payload_dict.get("fault", {}).get("reason")
                or payload_dict.get("fault", {}).get("name")
                or payload_dict.get("message")
                or log.get("message")
                or "N/A"
            )

            status_code = (
                payload_dict.get("responseCode")
                or payload_dict.get("proxyResponseCode")
                or log.get("responseCode")
                or log.get("proxyResponseCode")
                or "N/A"
            )
            client_ip = (
                payload_dict.get("clienteIP")
                or payload_dict.get("clientIp")
                or log.get("clienteIP")
                or log.get("clientIp")
                or "N/A"
            )

            nested_logs = payload_dict.get("logs", [])
            if (
                nested_logs
                and isinstance(nested_logs, list)
                and isinstance(nested_logs[0], dict)
            ):
                status_code = nested_logs[0].get("statusCode", status_code)
                client_ip = nested_logs[0].get("clientIp", client_ip)

            rows.append(
                f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #ddd; font-size: 13px;">{timestamp}</td>
            <td style="padding: 10px; border-bottom: 1px solid #ddd; font-size: 13px; font-weight: bold; color: #d9534f;">{status_code}</td>
            <td style="padding: 10px; border-bottom: 1px solid #ddd; font-size: 13px;">{client_ip}</td>
            <td style="padding: 10px; border-bottom: 1px solid #ddd; font-size: 13px; font-family: monospace; word-break: break-all;">{message}</td>
        </tr>
                """
            )
        return "".join(rows)

    def _render_html(
        self,
        recipient_email: str,
        proxy_name: str,
        error_summary: str,
        logs_details: list[dict[str, Any]],
    ) -> str:
        table_rows = self._render_table_rows(logs_details)
        logo_url = self.settings.logo_url
        company_name = self.settings.company_name

        if os.path.exists(self.template_path):
            with open(self.template_path, "r", encoding="utf-8") as f:
                raw_tpl = f.read()
            return raw_tpl.format(
                proxy_name=proxy_name,
                recipient_email=recipient_email,
                error_summary=error_summary,
                table_rows=table_rows,
                logo_url=logo_url,
                company_name=company_name,
            )
        # Fallback minimal HTML if template is missing
        return f"<h1>Alerta Apigee - {company_name}: {proxy_name}</h1><p>{error_summary}</p>"

    def _detect_base_url(self) -> str:
        """Determines the HTTP base URL for serving report links, automatically detecting Cloud Run."""
        for env_key in ["APP_BASE_URL", "SERVICE_URL", "CLOUD_RUN_URL"]:
            url = os.environ.get(env_key)
            if url:
                return url.rstrip("/")

        k_service = os.environ.get("K_SERVICE")
        if k_service:
            project_number = os.environ.get("GCP_PROJECT_NUMBER", "288615556444")
            region = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
            return f"https://{k_service}-{project_number}.{region}.run.app"

        return "http://localhost:8000"

    def _ensure_reports_mounted(self, sent_dir: str) -> None:
        """Dynamically mounts /reports onto any active FastAPI application in memory."""
        try:
            import gc
            from fastapi import FastAPI
            from fastapi.staticfiles import StaticFiles

            for obj in gc.get_objects():
                if isinstance(obj, FastAPI):
                    if not any(
                        getattr(route, "path", None) == "/reports"
                        for route in getattr(obj, "routes", [])
                    ):
                        obj.mount(
                            "/reports",
                            StaticFiles(directory=sent_dir),
                            name="reports",
                        )
                        logger.info(
                            "Dynamically mounted /reports onto live FastAPI application!"
                        )
        except Exception as e:
            logger.debug(f"Could not dynamically mount /reports: {e}")

    def send_diagnostic_email(
        self,
        recipient_email: str,
        proxy_name: str,
        error_summary: str,
        logs_details: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Sends a styled HTML diagnostic alert to the API proxy owner email."""
        html_content = self._render_html(
            recipient_email, proxy_name, error_summary, logs_details
        )

        smtp_host = self.settings.smtp_host
        smtp_port = self.settings.smtp_port
        smtp_user = self.settings.smtp_user
        smtp_pass = self.settings.smtp_password
        smtp_from = self.settings.smtp_from

        if smtp_host and smtp_port:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = (
                    f"[ALERTA APIGEE] Errores recurrentes en el proxy {proxy_name}"
                )
                msg["From"] = smtp_from
                msg["To"] = recipient_email

                part = MIMEText(html_content, "html", "utf-8")
                msg.attach(part)

                server = smtplib.SMTP(smtp_host, smtp_port)
                if smtp_user and smtp_pass:
                    server.starttls()
                    server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, [recipient_email], msg.as_string())
                server.quit()

                return {
                    "status": "success",
                    "message": f"Email successfully sent via SMTP to {recipient_email}.",
                }
            except Exception as e:
                logger.error(f"Failed sending email via SMTP: {e}")

        try:
            root_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            sent_dir = os.path.join(root_dir, "sent_emails")
            os.makedirs(sent_dir, exist_ok=True)
            timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"email_{proxy_name}_{timestamp_str}.html"
            filepath = os.path.join(sent_dir, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html_content)

            self._ensure_reports_mounted(sent_dir)

            logger.info(
                f"Fallback storage: HTML notification written to local file at {filepath}"
            )
            base_url = self._detect_base_url()
            http_url = f"{base_url}/reports/{filename}"
            file_url = f"file://{filepath}"
            return {
                "status": "success",
                "message": (
                    f"SMTP not configured. Notification HTML report saved locally. "
                    f"View the HTML report in your browser via HTTP at: {http_url} "
                    f"(or local file: {file_url})"
                ),
                "local_file": filepath,
                "html_report_url": http_url,
                "http_report_url": http_url,
                "local_file_url": file_url,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed creating fallback HTML file: {e}",
            }
