# Setup Guide — Karben4 QM Yield Tool (Windows)

How to install and run the yield tool on a Windows computer. Running it locally
this way means **your data saves permanently** to a file on this computer
(`brewery_data.xlsx`) and stays put between sessions — unlike the shared web link,
whose data resets.

One-time setup takes about 10 minutes. After that, starting the tool is 3 quick steps.

---

## One-time setup

### Step 1 — Install Python
1. Go to **https://www.python.org/downloads/** and click the big **Download Python 3.x** button.
2. Run the downloaded installer.
3. **On the first screen, check the box that says "Add python.exe to PATH"** (bottom of the window) — this is important. Then click **Install Now**.
4. When it finishes, click **Close**.

### Step 2 — Download the tool
1. Go to **https://github.com/keshavsshah/karben4-qm-yield-tool**
2. Click the green **`< > Code`** button, then **Download ZIP**.
3. Find the downloaded `karben4-qm-yield-tool-main.zip` (usually in your **Downloads** folder), right-click it → **Extract All…** → **Extract**.
4. Move the extracted **`karben4-qm-yield-tool-main`** folder somewhere permanent, e.g. your **Documents** folder.
   > ⚠️ Your saved batch data will live *inside* this folder, so don't delete or move it after you start using the tool.

### Step 3 — Open a command window inside the folder
1. Open the `karben4-qm-yield-tool-main` folder in File Explorer.
2. Click the **address bar** at the top (where the folder path is shown).
3. Type **`cmd`** and press **Enter**. A black command window opens, already pointed at the folder.

### Step 4 — Install the tool's components
In that command window, type each line and press Enter (wait for each to finish):

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

The last line downloads what the tool needs (Streamlit, etc.) — it takes a couple of
minutes the first time. You're done when it stops and shows the prompt again.

### Step 5 — Start it
```cmd
streamlit run app.py
```

The tool opens automatically in your web browser at **http://localhost:8501**.
That's it — you're running.

---

## Using it day to day

**To start the tool (each time):**
1. Open the `karben4-qm-yield-tool-main` folder, click the address bar, type `cmd`, press Enter.
2. Run these two lines:
   ```cmd
   .venv\Scripts\activate
   streamlit run app.py
   ```

**To stop it:** close the browser tab, then click the command window and press **Ctrl + C**.

**Entering batches:** go to the **Add batch** tab, type in the numbers, click **Save batch**.
Every save automatically writes to **`brewery_data.xlsx`** inside the folder — no separate
save or export step. Reopen the tool anytime and your batches are still there.

**Your data file:** `brewery_data.xlsx` in the folder is your saved history. Back it up
occasionally (copy it to OneDrive or a USB drive). You can also click **Data → Download
Excel / CSV** anytime for a full computed snapshot.

---

## Updating to a newer version later
1. Download the ZIP again (Step 2) and extract it into a **new** folder.
2. **Copy your existing `brewery_data.xlsx`** from the old folder into the new folder (so your
   history carries over).
3. Repeat Steps 3–5 in the new folder.

---

## If something goes wrong
- **`python` is not recognized** → Python wasn't added to PATH. Re-run the Python installer,
  choose **Modify**, and make sure **"Add python.exe to PATH"** is checked (or reinstall and
  check the box on the first screen).
- **`streamlit` is not recognized** → you skipped `.venv\Scripts\activate`, or Step 4's
  `pip install` didn't finish. Run the activate line, then re-run `pip install -r requirements.txt`.
- **Browser didn't open** → open it yourself and go to **http://localhost:8501**.
- **Nothing else works** → close the command window and start over from Step 3.
