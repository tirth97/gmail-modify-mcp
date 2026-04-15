"""Google OAuth handling for the Gmail MCP server.

Uses the standard installed-app flow:
  - Reads ``credentials.json`` (downloaded from Google Cloud Console -> OAuth
    client of type "Desktop app").
  - Caches the granted token in ``token.json`` next to it.
  - Refreshes the token automatically when it expires.

The first call to :func:`get_service` will open a browser for consent if no
cached token exists. Subsequent calls are silent.
"""

from __future__ import annotations

import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# gmail.modify is the smallest scope that allows users.messages.modify.
# It does NOT grant permanent delete (users.messages.delete).
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# Files live next to the project root by default. Override with env vars if
# you want to keep them somewhere else (e.g. %APPDATA%).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = Path(
    os.environ.get("GMAIL_MCP_CREDENTIALS", _PROJECT_ROOT / "credentials.json")
)
TOKEN_PATH = Path(
    os.environ.get("GMAIL_MCP_TOKEN", _PROJECT_ROOT / "token.json")
)


def _load_credentials() -> Credentials:
    creds: Credentials | None = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
        return creds

    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"OAuth client secrets not found at {CREDENTIALS_PATH}. "
            "Download a Desktop OAuth client from Google Cloud Console and "
            "save it there, or set GMAIL_MCP_CREDENTIALS."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_PATH.write_text(creds.to_json())
    return creds


def get_service():
    """Return an authenticated Gmail API service client."""
    creds = _load_credentials()
    # cache_discovery=False avoids noisy warnings about file_cache on Windows.
    return build("gmail", "v1", credentials=creds, cache_discovery=False)
