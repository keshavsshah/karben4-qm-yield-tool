# SharePoint durable storage — setup guide

This makes the **hosted** app (the shared `streamlit.app` link) save the QM's batches
**durably into Karben4's SharePoint** via Microsoft 365, instead of the local
`brewery_data.xlsx` that only persists when the app runs on a real computer. The same
file is then openable by the team in **Excel Online / SharePoint**.

It's **optional** — with none of this configured, the tool falls back to the local
`brewery_data.xlsx` and works exactly as before. Turn it on by giving the app six values
from Karben4 IT (below).

---

## What Karben4 IT needs to create (one-time)

Karben4 has a Microsoft 365 business license, which is sufficient — this needs **SharePoint
Online + Entra ID Free**, both included. No paid Azure subscription is required. The only
hard requirement is a **tenant administrator** to register the app and grant consent.

IT creates **one Entra ID (Azure AD) app registration** and returns these six items:

| # | Item | Notes |
|---|------|-------|
| 1 | **Tenant ID** (Directory ID) | Entra admin center → the org's directory |
| 2 | **Client ID** (Application ID) | the new app registration |
| 3 | **Client secret** (the *value*, not the ID) | app registration → Certificates & secrets → New client secret |
| 4 | **Graph application permission `Sites.Selected`** + **admin consent granted** | API permissions. `Sites.Selected` is the least-privilege option — it grants access to *only* the one site IT chooses, not all of SharePoint |
| 5 | **The app granted *write* on the target site** | one Graph call, below — required because `Sites.Selected` grants nothing until a specific site is assigned |
| 6 | **Drive ID of the document library** + the file path within it | where `brewery_data.xlsx` will live |

### The Graph call for item #5 (IT runs once, after granting Sites.Selected)
Assign the app write access to the chosen site (replace `{site-id}` and `{client-id}`):

```
POST https://graph.microsoft.com/v1.0/sites/{site-id}/permissions
{
  "roles": ["write"],
  "grantedToIdentities": [
    { "application": { "id": "{client-id}", "displayName": "Karben4 QM Yield Tool" } }
  ]
}
```

### Getting item #6 (drive id)
After #5, the document library's drive id comes from:
```
GET https://graph.microsoft.com/v1.0/sites/{site-id}/drives
```
Copy the `id` of the target library (e.g. "Documents"). That's `MS_DRIVE_ID`.
The file path (`MS_DATA_ITEM_PATH`) is where in that library the file lives, e.g.
`Brewing/brewery_data.xlsx` (a subfolder is fine; it's created on first save).

---

## Where the six values go (done by Keshav, not IT)

In **Streamlit Community Cloud** → your app → **⋮ → Settings → Secrets**, paste (TOML):

```toml
MS_TENANT_ID    = "……"     # item 1
MS_CLIENT_ID    = "……"     # item 2
MS_CLIENT_SECRET= "……"     # item 3
MS_DRIVE_ID     = "……"     # item 6 (the library's drive id)
MS_DATA_ITEM_PATH = "brewery_data.xlsx"   # or "Brewing/brewery_data.xlsx"
```

Save — the app reboots and now reads/writes the workbook in SharePoint. The sidebar
"Your saved data" section will switch to *"Stored in Karben4's SharePoint …"*.

> For a **local** test before deploying, put the same keys in `.streamlit/secrets.toml`
> (git-ignored — never committed). See `.streamlit/secrets.toml.example`.

Nothing to change in code: `sharepoint_store.is_configured()` flips on once all the
`MS_*` keys are present, and the app uses SharePoint automatically; otherwise it stays
on the local file.

---

## Copy-paste email to send IT

> **Subject:** Small Entra app registration for a brewery tool (SharePoint read/write)
>
> Hi Jason,
>
> I've built an internal tool for the brewery (a single-user quality/yields app) and I'd
> like it to store its data file in our SharePoint so it's durable and openable in Excel
> Online. It uses the Microsoft Graph API with app-only (client-credentials) auth. Our
> M365 business license already covers this — it just needs a one-time app registration
> by an admin. Could you set up the following and send me the values?
>
> 1. A new **Entra ID app registration** (name it e.g. "Karben4 QM Yield Tool"). I need the
>    **Tenant ID**, the **Client ID**, and a **client secret** (the value).
> 2. Add the Microsoft Graph **application** permission **`Sites.Selected`** and **grant admin
>    consent**. (This is least-privilege — it gives access to only the one site you pick below,
>    not all of SharePoint.)
> 3. Grant that app **write** access to the specific SharePoint site we want the file in, via:
>    `POST /sites/{site-id}/permissions` with `{"roles":["write"],"grantedToIdentities":[{"application":{"id":"<client-id>"}}]}`
> 4. Tell me the **site** and **document library** to use, and the library's **drive id**
>    (`GET /sites/{site-id}/drives`).
>
> No Azure subscription or premium license needed — standard Graph + Entra Free. Happy to hop
> on a quick call. Thanks!
>
> — Keshav

---

## Security notes
- **`Sites.Selected`** scopes the app to one SharePoint site only — it cannot read or write
  anything else in the tenant. Prefer it over `Files.ReadWrite.All`.
- The **client secret** is a credential — it lives only in Streamlit Secrets (or a local,
  git-ignored `secrets.toml`), never in the repo. Rotate it if it's ever exposed; set a
  reasonable expiry when IT creates it.
- The app only ever touches the single `brewery_data.xlsx` file at the configured path.
