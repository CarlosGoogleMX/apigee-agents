import os
from dotenv import load_dotenv
from google.adk.agents.llm_agent import Agent

from tools import get_cloud_logs

# Load environment variables from .env file
load_dotenv()

root_agent = Agent(
    model='gemini-3-flash-preview',
    tools=[get_cloud_logs],
    name='root_agent',
    description="An agent that retrieves and analyzes Apigee error logs to diagnose issues.",
    instruction=(
        "You are an expert in analyzing Apigee logs to diagnose issues. "
        "When a user reports an issue, ask for the API proxy, environment, time frame, and the number of log entries to retrieve. "
        "Then, use the 'get_cloud_logs' tool to retrieve logs containing common errors (4xx and 5xx status codes). "
        "Once you receive the logs, analyze them to identify patterns, such as a spike in a specific error code, "
        "issues from a single client IP, or recurring error messages. "
        "Finally, provide a concise conclusion about the likely cause of the problem based on your analysis."
    ),
)

if __name__ == "__main__":
    print(f"Agent '{root_agent.name}' initialized and ready.")
    print(f"Model configured: {root_agent.model}")
    print(f"Tools available: {[tool.__name__ for tool in root_agent.tools]}")