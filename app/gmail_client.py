from __future__ import annotations
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

ROOT = Path(__file__).resolve().parents[1]
CLIENT_SECRET_PATH = ROOT / "client_secret.json"
TOKEN_PATH = ROOT / "token.json"

def get_gmail_service():
    if not CLIENT_SECRET_PATH.exists():
        raise FileNotFoundError("client_secret.json not found in project root.")

    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # IMPORTANT: If token exists but doesn't have the needed scopes, force new consent
    if not creds or not creds.valid or not creds.has_scopes(SCOPES):
        if creds and creds.expired and creds.refresh_token and creds.has_scopes(SCOPES):
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
            creds = flow.run_local_server(port=0)

        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds)
