"""Shared auth for the X-ON-X Knowledge Base.

Two modes (auto-detected), so the same code runs locally and headless in cloud:
  * LOCAL  — cached OAuth token (~/.claude-sheets/token.json), shared with the
    rest of the sheets tooling.
  * CLOUD  — Google service account, used when env GOOGLE_SA_KEY points to a
    service-account JSON (or a kb_sa.json sits next to this file). Needed for
    headless runs (e.g. a scheduled cloud routine) — no interactive OAuth there.
"""
import os
import warnings

warnings.filterwarnings("ignore")

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as SACredentials
from googleapiclient.discovery import build

TOKEN_FILE = os.path.expanduser("~/.claude-sheets/token.json")
SA_KEY = os.environ.get("GOOGLE_SA_KEY") or os.path.join(
    os.path.dirname(__file__), "kb_sa.json")
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/script.projects",
]


def _creds():
    # CLOUD: service account if a key is present
    if os.path.exists(SA_KEY):
        return SACredentials.from_service_account_file(SA_KEY, scopes=SCOPES)
    # LOCAL: cached OAuth token
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return creds


def get_clients():
    """Return (gspread_client, drive_service) sharing one credential."""
    creds = _creds()
    return gspread.authorize(creds), build("drive", "v3", credentials=creds)
