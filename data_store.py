from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import pandas as pd

from sheets_sync import GoogleSheetsSync


@dataclass
class DataPaths:
    pilot: Path = Path("pilot_roster.csv")
    drone: Path = Path("drone_fleet.csv")
    missions: Path = Path("missions.csv")


class DataStore:
    def __init__(self, paths: DataPaths | None = None, sheets: GoogleSheetsSync | None = None):
        self.paths = paths or DataPaths()
        self.sheets = sheets or GoogleSheetsSync.from_env()

    def load_all(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        pilots = self._load(self.paths.pilot, self.sheets.config.pilot_sheet)
        drones = self._load(self.paths.drone, self.sheets.config.drone_sheet)
        missions = self._load(self.paths.missions, self.sheets.config.missions_sheet)
        return pilots, drones, missions

    def _load(self, local_path: Path, sheet_name: str) -> pd.DataFrame:
        if self.sheets.available:
            remote_df = self.sheets.read_sheet(sheet_name)
            if remote_df is not None and not remote_df.empty:
                remote_df.to_csv(local_path, index=False)
                return remote_df
        return pd.read_csv(local_path)

    def save_pilots(self, pilots: pd.DataFrame) -> bool:
        pilots.to_csv(self.paths.pilot, index=False)
        return self.sheets.write_sheet(self.sheets.config.pilot_sheet, pilots)

    def save_drones(self, drones: pd.DataFrame) -> bool:
        drones.to_csv(self.paths.drone, index=False)
        return self.sheets.write_sheet(self.sheets.config.drone_sheet, drones)

    def save_missions(self, missions: pd.DataFrame) -> bool:
        missions.to_csv(self.paths.missions, index=False)
        return self.sheets.write_sheet(self.sheets.config.missions_sheet, missions)
