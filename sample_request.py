import requests

BASE_URL = "https://apigee-diagnostic-agent-288615556444.us-central1.run.app"
USER_ID = "eng-team-user"

# 1. Create a session
res_session = requests.post(
    f"{BASE_URL}/apps/apigee_agent/users/{USER_ID}/sessions", json={}
)
session_id = res_session.json()["id"]

# 2. Invoke the agent
payload = {
    "appName": "apigee_agent",
    "userId": USER_ID,
    "sessionId": session_id,
    "newMessage": {
        "role": "user",
        "parts": [{"text": "agent-test, dev, the last 24 hours"}],
    },
}
res_run = requests.post(f"{BASE_URL}/run", json=payload)
print(res_run.json())
