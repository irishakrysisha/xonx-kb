"""Google Drive upload into the KB _Inbox folder.

Credentials follow the sales-bot pattern: GOOGLE_TOKEN_JSON env (Railway) or
the local ~/.claude-sheets/token.json. The _Inbox folder lives on the
"X-ON-X Legal" shared drive, so every API call passes supportsAllDrives.
"""
import io
import json
import os
import re

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

LOCAL_TOKEN = os.path.expanduser("~/.claude-sheets/token.json")
SCOPES = ["https://www.googleapis.com/auth/drive"]


def _load_credentials(token_json: str) -> Credentials:
    if token_json.strip():
        info = json.loads(token_json)
        creds = Credentials.from_authorized_user_info(info, SCOPES)
    elif os.path.exists(LOCAL_TOKEN):
        creds = Credentials.from_authorized_user_file(LOCAL_TOKEN, SCOPES)
    else:
        raise RuntimeError(
            "No Google credentials: set GOOGLE_TOKEN_JSON or provide ~/.claude-sheets/token.json")
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


def unique_name(name: str, taken: set[str]) -> str:
    """file.docx -> file (2).docx -> file (3).docx ... until free."""
    if name not in taken:
        return name
    stem, ext = os.path.splitext(name)
    stem = re.sub(r" \(\d+\)$", "", stem)
    n = 2
    while f"{stem} ({n}){ext}" in taken:
        n += 1
    return f"{stem} ({n}){ext}"


class DriveInbox:
    def __init__(self, folder_id: str, token_json: str = ""):
        self._svc = build("drive", "v3", credentials=_load_credentials(token_json),
                          cache_discovery=False)
        self._folder = folder_id

    def existing_names(self) -> set[str]:
        names, token = set(), None
        while True:
            resp = self._svc.files().list(
                q=f"'{self._folder}' in parents and trashed=false",
                fields="nextPageToken, files(name)", pageSize=1000, pageToken=token,
                supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
            names |= {f["name"] for f in resp.get("files", [])}
            token = resp.get("nextPageToken")
            if not token:
                return names

    def upload(self, data: bytes, name: str, mime: str, description: str) -> tuple[str, str]:
        """Upload bytes into _Inbox; returns (final_name, webViewLink)."""
        final = unique_name(name, self.existing_names())
        media = MediaIoBaseUpload(io.BytesIO(data),
                                  mimetype=mime or "application/octet-stream",
                                  resumable=False)
        meta = {"name": final, "parents": [self._folder], "description": description}
        created = self._svc.files().create(
            body=meta, media_body=media, fields="id, webViewLink",
            supportsAllDrives=True).execute()
        return final, created.get("webViewLink", "")
