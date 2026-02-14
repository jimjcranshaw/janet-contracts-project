import requests
import os
import sys

TOKEN = os.getenv("GITHUB_TOKEN", "your_token_here")
REPO = "jimjcranshaw/azure-production-v2"
FILES_TO_CHECK = [
    "insert_unique_funders.py",
    "manage_funders.py",
    "match_and_insert_charity_foundation_funders.py"
]

headers = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3.raw"
}

for filename in FILES_TO_CHECK:
    url = f"https://api.github.com/repos/{REPO}/contents/{filename}"
    print(f"\n--- Checking {filename} ---")
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            print(resp.text[:3000]) # Increased limit to find SQL
        else:
            print(f"Failed: {resp.status_code}")
    except Exception as e:
        print(f"Error: {e}")
