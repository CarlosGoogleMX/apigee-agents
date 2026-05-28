# Apigee Log Analysis Agent

This agent helps diagnose issues in Apigee by retrieving and analyzing error logs from Cloud Logging.

## Agent

### `root_agent`

This is the main agent that orchestrates the log analysis process.

**Description:** An agent that retrieves and analyzes Apigee error logs to diagnose issues.

**Instructions:** You are an expert in analyzing Apigee logs to diagnose issues. When a user reports an issue, ask for the API proxy, environment, time frame, and the number of log entries to retrieve. Then, use the 'get_cloud_logs' tool to retrieve logs containing common errors (4xx and 5xx status codes). Once you receive the logs, analyze them to identify patterns, such as a spike in a specific error code, issues from a single client IP, or recurring error messages. Finally, provide a concise conclusion about the likely cause of the problem based on your analysis.

## Tools

### `get_cloud_logs(api_proxy: str, environment: str, time_frame: str, n_results: int = 100) -> dict`

Retrieves logs with common error status codes from Cloud Logging for a given API proxy, environment, and time frame.

**Time Frame Format:**
The `time_frame` parameter can be a human-readable string like "last 3 hours" or a specific timestamp. The agent can parse the following units:
-   `hour(s)`
-   `minute(s)`
-   `day(s)`

If a human-readable string is provided, it will be converted to a time range with `startTime` and `endTime` in the format `YYYY-MM-DDTHH:MM:SS.sssZ`.

## How to Run

1.  **Set up environment variables:**
    Create a `.env` file in the root of the project and add the following variables:
    ```
    GOOGLE_API_KEY=<your_api_key>
    OAUTH_TOKEN=<your_oauth_token>
    GCP_PROJECT=<your_gcp_project_id>
    ```

2.  **Run the agent:**
    You can interact with the agent through the command line or by integrating it into your application.
