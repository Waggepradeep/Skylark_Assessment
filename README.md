# Skylark Drones - Drone Operations Coordinator AI Agent

A Streamlit-based conversational coordinator for managing pilots, drones, mission assignments, and operational conflicts with CSV + Google Sheets sync.

## What This Prototype Covers

- Pilot roster management
- Query pilots by skill, certification, location, and status
- Update pilot status (local + Google Sheets write when enabled)
- Pilot cost calculation by mission duration

- Assignment tracking
- Match pilots to missions by skills/certs/location/status/budget
- Match drones to missions by capability/location/status/weather/maintenance
- Track active assignments
- Support urgent reassignment suggestions

- Drone inventory management
- Query drones by capability/availability/location
- Weather compatibility filtering
- Maintenance risk checks
- Update drone status (local + Google Sheets write when enabled)

- Conflict detection
- Skill/certification mismatch
- Budget overrun warnings
- Weather risk alerts
- Maintenance conflicts
- Location mismatch alerts
- Double-booking detection support (`current_assignment` like `PRJ001|PRJ002`)

## Tech Stack

- Python 3.10+
- Streamlit
- pandas
- gspread + google-auth
- python-dotenv

## Project Structure

- `app.py`: UI, chat loop, quick actions
- `coordinator.py`: matching, conflicts, costing, assignment logic
- `data_store.py`: CSV + sync orchestration
- `sheets_sync.py`: Google Sheets read/write client
- `pilot_roster.csv`: sample pilot data
- `drone_fleet.csv`: sample drone data
- `missions.csv`: sample mission data
- `DECISION_LOG.md`: assumptions/trade-offs

## Local Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

### One-line Run Command (PowerShell)

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt; streamlit run app.py
```

### Example Prompt Flow (after app opens)

Run these in order inside the chat box:

1. `show conflicts`
2. `match PRJ001`
3. `cost P001 PRJ001`
4. `update pilot P001 status to On Leave`
5. `update drone D003 status to Maintenance`
6. `urgent PRJ002`

## Chat Commands to Test

- `show conflicts`
- `available pilots`
- `available drones`
- `match PRJ001`
- `cost P001 PRJ001`
- `update pilot P001 status to On Leave`
- `update drone D003 status to Maintenance`
- `urgent PRJ002`

## Google Sheets Setup (2-Way Sync)

### 1) Create sheets/tabs

Use one spreadsheet with tabs:

- `pilot_roster`
- `drone_fleet`
- `missions`

### 2) Share spreadsheet with service account

Share the sheet with your service account email (Editor access).

### 3) Configure `.env`

Recommended local setup (credential file path):

```env
GOOGLE_SHEETS_ENABLED=true
GOOGLE_SHEETS_CREDENTIALS_FILE=C:/path/to/service-account.json
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id
PILOT_SHEET_NAME=pilot_roster
DRONE_SHEET_NAME=drone_fleet
MISSIONS_SHEET_NAME=missions
```

Alternative setup (single-line JSON string):

```env
GOOGLE_SHEETS_ENABLED=true
GOOGLE_SHEETS_CREDENTIALS_JSON={...single_line_json...}
GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id
```

### Sync behavior

- Read: loads from Google Sheets when enabled and available; falls back to local CSV.
- Write: pilot/drone status updates save to CSV and attempt sheet sync.

## Deployment

Recommended: Streamlit Community Cloud

1. Push project to GitHub.
2. Create new Streamlit app from repo.
3. Add environment variables/secrets (do not upload credential files).
4. Deploy and test chat commands.

## Security Notes

- Never commit `.env` or service account JSON keys.
- Rotate keys if accidentally exposed.
- Use platform secrets in cloud deployments.

## Current Limitations

- Full-sheet write updates (not row-delta writes).
- Limited natural language parser patterns.
- No auth layer (single-operator prototype).
- No persistent event ledger for historical assignment audit.
