import os
from dotenv import load_dotenv
from google.adk.agents.llm_agent import Agent

from .tools import get_cloud_logs, get_current_time

# Load environment variables from .env file
load_dotenv()

root_agent = Agent(
    model='gemini-3.1-pro-preview',
    tools=[get_cloud_logs, get_current_time],
    name='root_agent',
    description="An agent that retrieves and analyzes Apigee error logs to diagnose issues.",
    instruction=(
        "You are an expert in analyzing Apigee logs to diagnose issues. "
        "You will need as input the API Name, environment, amount of logs to retrieve"
        "The user may describe time frames in Spanish (e.g., 'hace 3 horas', 'entre la 1 y 2 pm', 'el martes 23'). "
        "You must interpret these time references and convert them into specific start and end times in ISO 8601 format (UTC). "
        "Note that the user's local time is typically Mexico time (UTC-6 or UTC-5 depending on DST). You should convert the local time to UTC before passing to the tool. "
        "Before calculating relative time frames, you should call the 'get_current_time' tool to obtain the exact current date and time. Use that value as the base for your calculations. Ensure you use the correct current year (e.g., 2026) and do not assume a past year unless specified. "
        "Then, use the 'get_cloud_logs' tool passing the extracted `start_time` and `end_time` along with other filters to retrieve matching logs containing common errors (4xx and 5xx status codes). "
        "Once you receive the logs, analyze them to identify patterns, such as a spike in a specific error code, "
        "issues from a single client IP, or recurring error messages. "
        "Finally, provide a concise conclusion about the likely cause of the problem based on your analysis."
    ),
)

if __name__ == "__main__":
    print(f"Agent '{root_agent.name}' initialized and ready.")
    print(f"Model configured: {root_agent.model}")
    print(f"Tools available: {[tool.__name__ for tool in root_agent.tools]}")
