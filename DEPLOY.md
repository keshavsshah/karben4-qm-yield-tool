# Deploying the QM Yield Tool

## 1. Streamlit Community Cloud (free, multi-user)

This gets you a shared URL anyone can open — no server to manage, no Azure. The
tradeoff on the free tier: the GitHub repo backing it must be **public**, so
don't commit real workbook data or secrets (the `.gitignore` here already
excludes `*.xlsx`, `manual_batches.json`, and `.streamlit/secrets.toml`).

**One-time setup:**

1. Create a GitHub repo (e.g. `karben4-qm-yield-tool`) — public, since the free
   tier requires it.
2. From this folder:
   ```
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/<your-username>/karben4-qm-yield-tool.git
   git push -u origin main
   ```
3. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub,
   click "New app", pick the repo/branch, and set the main file to `app.py`.
4. Click Deploy. A few minutes later you get a URL like
   `https://karben4-qm-yield-tool.streamlit.app` — share that with the QM/anyone
   who needs it. Each visitor sees the same live app; the sidebar Upload buttons
   work exactly like they do locally (each user uploads their own workbook copy
   for their session).

**Redeploying after a code change:** just `git push` — Streamlit Cloud
auto-redeploys on every push to the branch you picked.

## 2. Auto-read workbooks from OneDrive/SharePoint (optional)

Without this, every visitor uses the sidebar Upload buttons each session (fine,
just a bit repetitive). With it, the app reads the live workbook files directly
— cached 5 min, with a "Refresh from OneDrive" button to force it.

**Needs an Azure AD app registration (ask Karben4 IT, or do it yourself if you
have a Microsoft 365 admin account):**

1. [portal.azure.com](https://portal.azure.com) -> Azure Active Directory ->
   App registrations -> New registration. Name it e.g. "QM Yield Tool". No
   redirect URI needed (this uses app-only auth, not a user login).
2. Certificates & secrets -> New client secret. Copy the value immediately (only
   shown once).
3. API permissions -> Add a permission -> Microsoft Graph -> Application
   permissions -> `Files.Read.All`. Then "Grant admin consent" (needs a Global
   Admin — this is the one step you can't do without IT/an admin account).
4. Note the **Application (client) ID**, **Directory (tenant) ID**, and the
   **client secret** from steps 1-2.
5. Find the **drive ID** of the OneDrive/SharePoint location holding the
   workbooks: while signed into Microsoft 365 in a browser, visit
   `https://graph.microsoft.com/v1.0/me/drive` (personal OneDrive) or
   `https://graph.microsoft.com/v1.0/sites/{site-id}/drive` (SharePoint site) —
   the `id` field in the JSON response is the drive ID.

**Add these as Streamlit Cloud "Secrets"** (app dashboard -> Settings ->
Secrets — paste as TOML, this is the Cloud equivalent of environment variables):

```toml
MS_TENANT_ID = "xxxxxxxx-xxxx-..."
MS_CLIENT_ID = "xxxxxxxx-xxxx-..."
MS_CLIENT_SECRET = "..."
MS_DRIVE_ID = "..."
MS_LAUTER_ITEM_PATH = "Inputs/Lauter_Checks_2.xlsx"   # optional, this is the default
MS_YIELDS_ITEM_PATH = "Inputs/Brewery_Yields.xlsx"    # optional, this is the default
```

Once all four required keys (`MS_TENANT_ID`, `MS_CLIENT_ID`, `MS_CLIENT_SECRET`,
`MS_DRIVE_ID`) are set, the app auto-detects this on next load and switches the
sidebar from "Upload" buttons to "Reading live from OneDrive/SharePoint" — no
code changes needed. If the fetch ever fails (bad creds, file moved), it falls
back to the upload UI with an error message rather than crashing.

## 3. Alternative: self-hosted (Docker)

If Streamlit Cloud's public-repo requirement is ever a dealbreaker, the
`Dockerfile` + `requirements.txt` here work on any container host — a small
Render/Railway/Fly.io instance ($5-10/mo, private), a spare on-prem server, or
Azure App Service if Karben4 ever gets a subscription. Locally:
```
docker build -t qm-yield-tool .
docker run -p 8501:8501 --env-file .env qm-yield-tool
```
where `.env` holds the same `MS_*` variables as env vars instead of Streamlit
secrets (`onedrive.py` checks both).
