import json
import os
from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class SheetsConfig:
    enabled: bool = False
    spreadsheet_id: str = ""
    pilot_sheet: str = "pilot_roster"
    drone_sheet: str = "drone_fleet"
    missions_sheet: str = "missions"
    credentials_json: str = ""
    credentials_file: str = ""


class GoogleSheetsSync:
    def __init__(self, config: SheetsConfig):
        self.config = config
        self._client = None
        self._spreadsheet = None
        if self.config.enabled:
            self._connect()

    @staticmethod
    def from_env() -> "GoogleSheetsSync":
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except Exception:
            pass

        enabled = os.getenv("GOOGLE_SHEETS_ENABLED", "false").lower() == "true"
        config = SheetsConfig(
            enabled=enabled,
            spreadsheet_id=os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", ""),
            pilot_sheet=os.getenv("PILOT_SHEET_NAME", "pilot_roster"),
            drone_sheet=os.getenv("DRONE_SHEET_NAME", "drone_fleet"),
            missions_sheet=os.getenv("MISSIONS_SHEET_NAME", "missions"),
            credentials_json=os.getenv("GOOGLE_SHEETS_CREDENTIALS_JSON", ""),
            credentials_file=os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE", ""),
        )
        return GoogleSheetsSync(config)

    @property
    def available(self) -> bool:
        return self.config.enabled and self._spreadsheet is not None

    def _connect(self) -> None:
        try:
            import gspread
            from google.oauth2.service_account import Credentials

            if not self.config.spreadsheet_id:
                return

            creds_data = self._load_creds_data()
            if creds_data is None:
                return

            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            creds = Credentials.from_service_account_info(creds_data, scopes=scopes)
            self._client = gspread.authorize(creds)
            self._spreadsheet = self._client.open_by_key(self.config.spreadsheet_id)
        except Exception:
            self._client = None
            self._spreadsheet = None

    def _load_creds_data(self) -> Optional[dict]:
        if self.config.credentials_json:
            try:
                return json.loads(self.config.credentials_json)
            except Exception:
                pass

        if self.config.credentials_file and os.path.exists(self.config.credentials_file):
            try:
                with open(self.config.credentials_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def read_sheet(self, sheet_name: str) -> Optional[pd.DataFrame]:
        if not self.available:
            return None
        try:
            ws = self._spreadsheet.worksheet(sheet_name)
            records = ws.get_all_records()
            return pd.DataFrame(records)
        except Exception:
            return None

    def write_sheet(self, sheet_name: str, df: pd.DataFrame) -> bool:
        if not self.available:
            return False
        try:
            ws = self._spreadsheet.worksheet(sheet_name)
            values = [list(df.columns)] + df.fillna("").astype(str).values.tolist()
            ws.clear()
            ws.update(values)
            return True
        except Exception:
            return False
