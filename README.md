# Apigee Error Log Diagnostic Agent

This repository contains an AI-powered agent built using the Google Agent Development Kit (ADK) that integrates with Google Cloud Logging. The agent is designed to intelligently retrieve, analyze, and interpret Apigee logs to quickly diagnose API issues.

## Features

- **AI-Powered Analysis:** Leverages `gemini-3.5-flash` to identify complex issue patterns (e.g. error code spikes, recurring problematic IPs).
- **Dynamic Logging Filters:** Retrieve logs filtering by specific criteria:
  - Up to two API Proxies
  - API Product
  - Client ID
  - Target Server
  - Environment
  - Time Frame (e.g., "last 3 hours", "last 2 days")
- **Error Code Focused:** Automatically isolates 4xx and 5xx errors typically involved in critical outages. 
- **Context Controlled:** Restricts maximum log results gracefully to protect the LLM context window limits.

<br>

## Setup & Installation

### 1. Requirements

Ensure you have Python 3 installed. It is strongly recommended to use a virtual environment.

```bash
# Create and activate a Virtual Environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 2. Authentication

This agent relies on Application Default Credentials (ADC) to access Google Cloud Logging securely without heavily relying on static Tokens.

If you are running this locally, run:
```bash
gcloud auth application-default login
```
*(If you must use a traditional token, you can define `OAUTH_TOKEN` in the `.env` file).*

### 3. Environment Variables

Create a local `.env` file based on the provided template:
```bash
cp .env.example .env
```
Inside the `.env` file, configure your target Google Cloud logging project:
```
GCP_PROJECT=your-gcp-project-id
```

<br>

## Usage

You can load and execute the agent directly via the ADK CLI or by running the script locally to view initialization properties:

```bash
adk web --port 8000
```

When interacting with the agent (e.g., passing it input strings), you can ask naturally for what you need:
> *"Analyze the logs from the last 2 hours in the production environment for API product payments-v1."*

The agent will intuitively extract your requirements, query GCP logging automatically, summarize the log payloads, and provide an expert root-cause conclusion.
