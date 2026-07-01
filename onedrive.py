"""Optional OneDrive/SharePoint workbook fetching via Microsoft Graph (app-only /
client-credentials auth). Only activates when MS_TENANT_ID, MS_CLIENT_ID,
MS_CLIENT_SECRET, and MS_DRIVE_ID are all set — as environment variables (Docker/
any generic host) or as Streamlit Cloud "Secrets" (checked via st.secrets). See
DEPLOY.md for how Karben4 IT sets those up. Without them, app.py falls back to
manual upload / local files, same as before.
"""
import io
import os

import msal
import requests
import streamlit as st

GRAPH_SCOPE = ["https://graph.microsoft.com/.default"]
_REQUIRED_KEYS = ("MS_TENANT_ID", "MS_CLIENT_ID", "MS_CLIENT_SECRET", "MS_DRIVE_ID")


def get_config(key: str, default=None):
    if key in os.environ:
        return os.environ[key]
    try:
        return st.secrets[key]
    except (FileNotFoundError, KeyError, st.errors.StreamlitAPIException):
        return default


def is_configured() -> bool:
    return all(get_config(k) for k in _REQUIRED_KEYS)


def _access_token() -> str:
    tenant_id = get_config("MS_TENANT_ID")
    app = msal.ConfidentialClientApplication(
        get_config("MS_CLIENT_ID"),
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=get_config("MS_CLIENT_SECRET"),
    )
    result = app.acquire_token_for_client(scopes=GRAPH_SCOPE)
    if "access_token" not in result:
        raise RuntimeError(f"Microsoft Graph auth failed: {result.get('error_description', result)}")
    return result["access_token"]


def fetch_workbook(item_path: str) -> io.BytesIO:
    """Download a workbook from the configured OneDrive/SharePoint drive by path
    (e.g. 'Inputs/Lauter_Checks_2.xlsx'). Returns an in-memory file-like object that
    openpyxl/load_batches can read directly, same as a Streamlit-uploaded file."""
    token = _access_token()
    drive_id = get_config("MS_DRIVE_ID")
    url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{item_path}:/content"
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    resp.raise_for_status()
    return io.BytesIO(resp.content)
