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
print(f"Scanning {FILENAME} for INSERT statements...")

try:
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        content = resp.text
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "INSERT INTO" in line:
                print(f"Line {i+1}: {line.strip()}")
                # Print context
                for j in range(i+1, min(len(lines), i+30)):
                    print(f"  {lines[j]}")
                print("-" * 40)
    else:
        print(f"Failed: {resp.status_code}")
except Exception as e:
    print(f"Error: {e}")
