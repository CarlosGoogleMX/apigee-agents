# Apigee Error Diagnostic Agent (ADK & uv ready)

An intelligent diagnostic AI agent built with **Google Agent Development Kit (ADK)** to inspect, analyze, and diagnose Apigee error logs from Google Cloud Logging and notify API proxy owners via API Hub and HTML email alerts.

---

## 🚀 Quickstart with `uv` & Google ADK

This project is natively configured for [`uv`](https://docs.astral.sh/uv/) and the **Google ADK CLI / Web UI**.

### 1. Sync Dependencies
```bash
uv sync
```
This automatically sets up a clean `.venv` using Python 3.10+ and installs all required dependencies (`google-adk`, `google-cloud-logging`, `google-auth`, etc.).

### 2. Configure Environment
Copy `.env.example` to `.env` and set your target GCP project:
```bash
cp .env.example .env
```
Ensure you have Application Default Credentials (ADC) configured:
```bash
gcloud auth application-default login
```

### 3. Run with ADK Web UI or CLI

#### 🌐 Launch ADK Web UI:
```bash
uv run adk web .
```
Open `http://127.0.0.1:8000` in your browser and select **`apigee_agent`** from the agent drop-down.

#### 💻 Run Interactively in Terminal (ADK CLI):
```bash
uv run adk run apigee_agent
```

#### 🐍 Run Standalone Script:
* **Inspection Mode** (prints agent initialization info and available tools):
  ```bash
  uv run main.py
  ```
* **Web Server Mode** (starts an ASGI server and serves static HTML diagnostic reports at `http://localhost:8000/reports/<filename>`):
  ```bash
  uv run main.py --server
  ```

#### 📡 Run REST API Server (ADK API Server):
```bash
uv run adk api_server .
```
Starts an HTTP REST API server on port 8000 for programmatic session management and agent invocations.

---

## 🤖 Agent Tools & Capabilities

The agent (`apigee_diagnostic_agent`) is equipped with 5 specialized ADK tools defined in [`apigee_agent/tools.py`](apigee_agent/tools.py), optimized for **single-turn execution and low-latency token ingestion**:

* **`get_cloud_logs`**: Queries Google Cloud Logging for HTTP 4xx and 5xx error logs. Supports **relative natural-language time ranges** (e.g., `'last 15 minutes'`, `'last 2 hours'`) as well as explicit ISO 8601 UTC timestamps. It automatically resolves business terms in proxy names (e.g., `'onboarding'` ➔ `'onboarding-v1-proxy'`) and returns concise diagnostic summaries with a default `n_results=20`.
* **`get_api_owner_email`**: Queries Google Cloud API Hub REST APIs (direct lookup or list search) with connection pooling, **LRU caching**, and organization/project alias resolution to locate the responsible proxy owner email.
* **`send_diagnostic_email`**: Dispatches a beautifully styled HTML email alert to the proxy owner via SMTP (with TLS) or saves a fallback HTML report in `sent_emails/` with a clickable HTTP URL (`/reports/<filename>`). It **automatically attaches cached logs from memory** (`_last_logs_cache`) without requiring the LLM to regenerate raw JSON payloads.
* **`get_current_time`**: Obtains the current UTC timestamp in ISO 8601 format when explicit reference timestamps are needed outside of a log query.
* **`lookup_business_reference`**: Manually resolves human-readable business terms (`'onboarding'`, `'billing'`, `'payments'`, `'authentication'`) to technical Apigee names using `catalogue.json` when inspecting catalogue metadata outside of log queries.

### ⚡ Performance & Token Optimizations
* **Single-Turn Log Queries**: Log queries execute immediately on the first LLM turn without requiring sequential roundtrips for timestamp or catalogue lookups.
* **Zero-Overhead Email Alerts**: Because `send_diagnostic_email` retrieves cached log records directly from memory (`_last_logs_cache`), alert generation requires only ~50 output tokens (a **98% reduction in output tokens** and **~4x speedup** in end-to-end execution).
* **Concise Log Sanitization**: Verbose Google Cloud Logging metadata is pruned down to essential diagnostic fields (`timestamp`, `responseCode`, `clientIp`, `message`, `apiProxy`, `environment`), cutting input token consumption by **~70%**.

---

## ⚙️ Environment Configuration

The application reads configuration from environment variables or a local `.env` file (copied from `.env.example`).

### Required Variables

| Variable | Description | Example Value |
| :--- | :--- | :--- |
| `GCP_PROJECT` | Target Google Cloud Project ID hosting Apigee error logs and API Hub. | `worstation-379213` |
| `DEFAULT_OWNER_EMAIL` | Default recipient email address for diagnostic alerts when an API proxy owner is not registered in API Hub. | `andresperezm@google.com` |

### Optional Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `GOOGLE_CLOUD_LOCATION` | `us-central1` | Google Cloud region for Vertex AI generative models. |
| `GOOGLE_GENAI_USE_VERTEXAI` | `true` | Connect to Vertex AI using least-privilege Application Default Credentials (ADC) or Service Account. |
| `MODEL_NAME` | `gemini-2.5-flash` | Gemini model name used for diagnostic analysis. |
| `APIHUB_LOCATION` | `global` | Location region for Google Cloud API Hub REST endpoint queries. |
| `ORG_MAPPINGS_JSON` | `{}` | JSON map of human-readable organization/project aliases to canonical GCP Project IDs (e.g., `'{"my-prod-project": ["prod", "producción"]}'`). |
| `COMPANY_NAME` | `API Operations Team` | Organization name displayed in email header branding. |
| `LOGO_URL` | Google Cloud Logo | Public URL to company logo displayed in HTML reports. |
| `APP_BASE_URL` | `http://localhost:8000` | Public base URL of the deployed Cloud Run service for generating clickable report links. |
| `SMTP_HOST` / `SMTP_PORT` | `None` / `587` | SMTP server host and port. If unset, alerts are saved in `sent_emails/` and served over HTTP via `/reports/<filename>`. |
| `SMTP_USER` / `SMTP_FROM` | `None` | Sender email address for SMTP authentication and message header. |
| `SMTP_PASSWORD` | `None` | SMTP App Password. **In production, store this in Google Cloud Secret Manager.** |

---

## 🔌 Programmatic REST API Usage

You can interact with the agent programmatically over HTTP when running via `adk api_server .` or when deployed to Google Cloud Run. The repository includes [`sample_request.py`](sample_request.py) as a working example.

### 1. Create a Session
```bash
curl -X POST "http://localhost:8000/apps/apigee_agent/users/eng-team-user/sessions" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 2. Invoke the Agent
```bash
curl -X POST "http://localhost:8000/run" \
  -H "Content-Type: application/json" \
  -d '{
    "appName": "apigee_agent",
    "userId": "eng-team-user",
    "sessionId": "<SESSION_ID_FROM_STEP_1>",
    "newMessage": {
      "role": "user",
      "parts": [{"text": "agent-test, dev, the last 24 hours"}]
    }
  }'
```

---

## ☁️ Google Cloud Run Deployment & Secret Manager Setup

### 1. Create SMTP Secrets in Google Cloud Secret Manager

Store sensitive SMTP credentials in Google Cloud Secret Manager instead of plaintext environment variables:

```bash
# Create SMTP secrets in project worstation-379213
printf "vqez mbwm abxb bqql"           | gcloud secrets create smtp-password --replication-policy=automatic --data-file=-
printf "carlospersonal93mex@gmail.com" | gcloud secrets create smtp-user     --replication-policy=automatic --data-file=-
printf "carlospersonal93mex@gmail.com" | gcloud secrets create smtp-from     --replication-policy=automatic --data-file=-
printf "smtp.gmail.com"                | gcloud secrets create smtp-host     --replication-policy=automatic --data-file=-
printf "587"                           | gcloud secrets create smtp-port     --replication-policy=automatic --data-file=-
```

### 2. Grant Secret Accessor Role to Runtime Service Account

Ensure the Cloud Run runtime service account (`288615556444-compute@developer.gserviceaccount.com`) has the **Secret Manager Secret Accessor** role:

```bash
gcloud projects add-iam-policy-binding worstation-379213 \
  --member="serviceAccount:288615556444-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### 3. Sample Deploy Script (`deploy.sh`)

Deploy the application from source to Google Cloud Run, binding `DEFAULT_OWNER_EMAIL` as an updatable environment variable and injecting all SMTP configuration via Secret Manager:

```bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="worstation-379213"
REGION="us-central1"
SERVICE_NAME="apigee-diagnostic-agent"

gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --port=8080 \
  --set-env-vars="GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_LOCATION=us-central1,GCP_PROJECT=${PROJECT_ID},APP_BASE_URL=https://${SERVICE_NAME}-288615556444.${REGION}.run.app,DEFAULT_OWNER_EMAIL=andresperezm@google.com" \
  --set-secrets="SMTP_PASSWORD=smtp-password:latest,SMTP_USER=smtp-user:latest,SMTP_FROM=smtp-from:latest,SMTP_HOST=smtp-host:latest,SMTP_PORT=smtp-port:latest" \
  --quiet
```

---

## 🏗️ Project Architecture

```text
apigee_agent/
├── __init__.py               # Exports root_agent for ADK discovery
├── agent.py                  # ADK Root Agent definition
├── config.py                 # Immutable Settings dataclass & dynamic organization mappings
├── tools.py                  # ADK Tool adapters for domain services & logging/email dispatch
├── catalogue/
│   ├── catalogue.json        # Built-in business reference catalogue
│   └── service.py            # CatalogueService with multi-path resolution
├── gcp/
│   ├── auth.py               # Shared CredentialManager (OAuth & ADC / Cloud Run metadata)
│   ├── logging_service.py    # Cloud Logging error query & payload sanitization
│   └── apihub_service.py     # GCP API Hub proxy owner lookups with connection pooling
└── notifications/
    ├── email_service.py      # EmailService with HTML template rendering
    └── templates/
        └── alert_email.html  # Dedicated HTML alert template
```

### Standalone & Example Files
- `main.py`: Standalone execution wrapper (`uv run main.py` or `uv run main.py --server`).
- `sample_request.py`: Python script demonstrating programmatic REST API invocation (`POST /sessions` and `POST /run`).
- `sent_emails/`: Directory where fallback HTML diagnostic alert reports are saved and served over HTTP via `/reports/<filename>`.
