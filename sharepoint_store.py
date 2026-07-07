"""
sharepoint_store.py — durable batch store backed by SharePoint / OneDrive (Graph)
=================================================================================
Same interface as workbook_store (load_batches / save_batch / delete_batch) but the
`brewery_data.xlsx` workbook lives in a **SharePoint document library** instead of on
local disk — so the *hosted* Streamlit app keeps data durably (survives restarts) and
the QM/team can also open the same file in Excel Online. Best fit for a Microsoft 365
shop; the alternative local store (workbook_store.py) needs the app on a real disk.

Auth + config reuse onedrive.py (app-only / client-credentials via MSAL). Activates
only when the Microsoft creds AND a data-file path are configured; otherwise
`is_configured()` is False and app.py falls back to the local workbook_store. Config
keys (env vars or Streamlit "Secrets"):

    MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET   — the Entra app registration
    MS_DRIVE_ID                                    — the SharePoint document library (drive)
    MS_DATA_ITEM_PATH   (optional)                 — path to the data file within that drive
                                                     (default "brewery_data.xlsx")

Karben4 IT provides the first five (one Entra app registration + Graph `Sites.Selected`
consent + the target library's drive id). See SHAREPOINT_SETUP.md.
"""
import io

import openpyxl
import requests

import onedrive
import workbook_store

GRAPH = "https://graph.microsoft.com/v1.0"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# reuse onedrive's exact required creds, plus a drive id for where the file lives
_REQUIRED_KEYS = ("MS_TENANT_ID", "MS_CLIENT_ID", "MS_CLIENT_SECRET", "MS_DRIVE_ID")


def _item_path() -> str:
    return onedrive.get_config("MS_DATA_ITEM_PATH", "brewery_data.xlsx")


def is_configured() -> bool:
    """True only when every Microsoft cred is present — otherwise app.py uses the
    local workbook_store instead. Keeps the tool working with zero config."""
    return all(onedrive.get_config(k) for k in _REQUIRED_KEYS)


def _headers():
    return {"Authorization": f"Bearer {onedrive._access_token()}"}


def _content_url() -> str:
    drive_id = onedrive.get_config("MS_DRIVE_ID")
    return f"{GRAPH}/drives/{drive_id}/root:/{_item_path()}:/content"


# --- store interface (mirrors workbook_store) --------------------------------
def load_batches() -> dict:
    """Download brewery_data.xlsx from SharePoint and parse it -> {num: Batch}.
    Returns {} if the file doesn't exist yet (first run)."""
    resp = requests.get(_content_url(), headers=_headers(), timeout=30)
    if resp.status_code == 404:
        return {}                      # not created yet — first save will make it
    resp.raise_for_status()
    wb = openpyxl.load_workbook(io.BytesIO(resp.content), data_only=True)
    return workbook_store.workbook_to_batches(wb)


def _write_all(batches: dict):
    """Serialize all batches to a workbook and upload (create/overwrite) it."""
    wb = workbook_store.batches_to_workbook(batches)
    buf = io.BytesIO()
    wb.save(buf)
    resp = requests.put(
        _content_url(),
        headers={**_headers(), "Content-Type": XLSX_MIME},
        data=buf.getvalue(),
        timeout=60,
    )
    resp.raise_for_status()


def save_batch(batch):
    """Upsert one batch (keyed by batch_number) and re-upload the whole workbook."""
    batches = load_batches()
    batches[workbook_store._batch_id(batch.batch_number)] = batch
    _write_all(batches)


def delete_batch(batch_number):
    batches = load_batches()
    batches.pop(workbook_store._batch_id(batch_number), None)
    _write_all(batches)


def store_label() -> str:
    """Human label for the sidebar 'Your saved data' status."""
    return f"SharePoint · `{_item_path()}`"
