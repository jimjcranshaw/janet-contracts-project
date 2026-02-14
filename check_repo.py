import requests
import os
import sys

# Token provided by user
TOKEN = os.getenv("GITHUB_TOKEN", "your_token_here")
REPO = "jimjcranshaw/azure-production-v2"
URL = f"https://api.github.com/repos/{REPO}/contents"

headers = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

print(f"Checking {URL}...")
try:
    resp = requests.get(URL, headers=headers)
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        print("Repo is accessible!")
        for item in resp.json():
            print(f"- {item['type']}: {item['path']}")
    else:
        print(f"Failed to access: {resp.status_code}")
        print(resp.text[:200])
except Exception as e:
    print(f"Error: {e}")
