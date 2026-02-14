import requests
import os
import sys

TOKEN = os.getenv("GITHUB_TOKEN", "your_token_here")
REPO = "jimjcranshaw/azure-production-v2"
FILENAME = "monthly_charity_processor.py"

headers = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3.raw"
}

url = f"https://api.github.com/repos/{REPO}/contents/{FILENAME}"
print(f"Fetching {FILENAME}...")

try:
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        print(resp.text[:5000])
    else:
        print(f"Failed: {resp.status_code}")
except Exception as e:
    print(f"Error: {e}")
