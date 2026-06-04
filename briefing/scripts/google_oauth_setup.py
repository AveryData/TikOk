"""One-time helper to get a Google Calendar refresh token for the briefing.

Usage (on your laptop, not Cloud Run):
    cd briefing
    pip install google-auth google-auth-oauthlib
    python scripts/google_oauth_setup.py path/to/client_secret.json

This opens a browser, you log in + consent, and it prints three lines you
paste into Cloud Run as env vars:
    GOOGLE_OAUTH_CLIENT_ID
    GOOGLE_OAUTH_CLIENT_SECRET
    GOOGLE_OAUTH_REFRESH_TOKEN

The refresh token is long-lived (months to years) and never leaves your
Cloud Run env. The service uses it to mint short-lived access tokens on
each /briefing request.

Prereqs in Google Cloud Console:
1. Enable the Calendar API:
     gcloud services enable calendar-json.googleapis.com
2. Configure OAuth consent screen:
     https://console.cloud.google.com/apis/credentials/consent
     - User Type: External
     - App name: "Daily Briefing" (or whatever)
     - User support + developer email: your address
     - Scopes: skip
     - Test users: add your own email
3. Create OAuth client credentials:
     https://console.cloud.google.com/apis/credentials
     - Click "+ CREATE CREDENTIALS" → "OAuth client ID"
     - Application type: Desktop app
     - Download the JSON — that's the path you pass to this script.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python scripts/google_oauth_setup.py <client_secret.json>", file=sys.stderr)
        sys.exit(2)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print(
            "Missing dependency. Install with:\n"
            "    pip install google-auth google-auth-oauthlib",
            file=sys.stderr,
        )
        sys.exit(1)

    client_secrets_path = Path(sys.argv[1])
    if not client_secrets_path.exists():
        print(f"File not found: {client_secrets_path}", file=sys.stderr)
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secrets_path), scopes=SCOPES
    )
    # Browser flow: opens default browser, captures the OAuth callback on
    # a local port, returns credentials.
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    with open(client_secrets_path) as f:
        secrets = json.load(f)
    client_info = secrets.get("installed") or secrets.get("web") or {}
    client_id = client_info.get("client_id", "")
    client_secret = client_info.get("client_secret", "")

    if not creds.refresh_token:
        print(
            "\n[ERROR] No refresh token returned. This usually means you've already\n"
            "consented for this client. Revoke at https://myaccount.google.com/permissions\n"
            "and re-run, OR pass prompt=consent (already set, but try again).",
            file=sys.stderr,
        )
        sys.exit(1)

    print()
    print("==== Paste these into your Cloud Run env vars ====")
    print(f"GOOGLE_OAUTH_CLIENT_ID={client_id}")
    print(f"GOOGLE_OAUTH_CLIENT_SECRET={client_secret}")
    print(f"GOOGLE_OAUTH_REFRESH_TOKEN={creds.refresh_token}")
    print()
    print("Update the service with:")
    print(
        "  gcloud run services update daily-briefing --region us-central1 \\\n"
        f"    --update-env-vars 'GOOGLE_OAUTH_CLIENT_ID={client_id},GOOGLE_OAUTH_CLIENT_SECRET={client_secret},GOOGLE_OAUTH_REFRESH_TOKEN={creds.refresh_token}'"
    )


if __name__ == "__main__":
    main()
