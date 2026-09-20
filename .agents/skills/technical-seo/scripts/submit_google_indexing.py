#!/usr/bin/env python3

import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
"""Submit updated URLs to Google Indexing API via Service Account."""

import json
import os
import sys
from pathlib import Path

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
except ImportError:
    # fallback to requests with google.oauth2
    service_account = None

INDEXING_SCOPE = ["https://www.googleapis.com/auth/indexing"]
INDEXING_URL = "https://indexing.googleapis.com/v3/urlNotifications:publish"

def get_credentials():
    from env_load import env_file_path  # из worktree — .env основной копии
    env_path = env_file_path()
    creds_json = None
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        marker = "GSC_SERVICE_ACCOUNT_JSON="
        idx = content.find(marker)
        if idx != -1:
            rest = content[idx + len(marker):]
            start = rest.index("{")
            depth = 0
            end = None
            for i, ch in enumerate(rest[start:], start):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end:
                creds_json = rest[start:end]
    
    if not creds_json:
        creds_json = os.environ.get("GSC_SERVICE_ACCOUNT_JSON")
        
    if not creds_json:
        sys.exit("GSC_SERVICE_ACCOUNT_JSON not found in .env")
        
    info = json.loads(creds_json)
    from google.oauth2 import service_account
    return service_account.Credentials.from_service_account_info(info, scopes=INDEXING_SCOPE)

def submit_url(creds, url):
    import requests
    import google.auth.transport.requests

    auth_req = google.auth.transport.requests.Request()
    creds.refresh(auth_req)
    token = creds.token

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    body = {
        "url": url,
        "type": "URL_UPDATED"
    }
    resp = requests.post(INDEXING_URL, headers=headers, json=body)
    print(f"URL: {url} -> Status: {resp.status_code} Result: {resp.text}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        urls = sys.argv[1:]
    else:
        urls = [
            "https://fastup.by/",
            "https://fastup.by/razrabotka-saitov/",
            "https://fastup.by/seo-prodvizhenie/",
            "https://fastup.by/kontekstnaya-reklama/",
            "https://fastup.by/geo-prodvizhenie/",
            "https://fastup.by/graficheskiy-i-veb-dizayn/",
            "https://fastup.by/geo-audit-system/"
        ]
    try:
        creds = get_credentials()
        print("=== SUBMITTING URLS TO GOOGLE INDEXING API ===")
        for u in urls:
            submit_url(creds, u)
    except Exception as e:
        print(f"Google Indexing API submission error/notice: {e}")
