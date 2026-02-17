from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd


def _split_multi(value: str) -> List[str]:
    if pd.isna(value):
        return []
    return [v.strip().lower() for v in str(value).split(",") if v.strip()]


def _parse_date(value: str) -> pd.Timestamp:
    return pd.to_datetime(value, errors="coerce")


def _days_inclusive(start: pd.Timestamp, end: pd.Timestamp) -> int:
    if pd.isna(start) or pd.isna(end):
        return 0
    return max(1, (end - start).days + 1)


def _is_rainy(weather: str) -> bool:
    text = str(weather).lower()
    return "rain" in text or "storm" in text


def _drone_weather_ok(drone_weather_resistance: str, forecast: str) -> bool:
    if not _is_rainy(forecast):
        return True
    return "rain" in str(drone_weather_resistance).lower() or "ip43" in str(drone_weather_resistance).lower()


class Coordinator:
    def __init__(self, pilots: pd.DataFrame, drones: pd.DataFrame, missions: pd.DataFrame):
        self.pilots = pilots.copy()
        self.drones = drones.copy()
        self.missions = missions.copy()
        self._normalize()

    def _normalize(self) -> None:
        for col in ["available_from"]:
            if col in self.pilots.columns:
                self.pilots[col] = self.pilots[col].apply(_parse_date)

        for col in ["maintenance_due"]:
            if col in self.drones.columns:
                self.drones[col] = self.drones[col].apply(_parse_date)

        for col in ["start_date", "end_date"]:
            if col in self.missions.columns:
                self.missions[col] = self.missions[col].apply(_parse_date)

        if "current_assignment" in self.pilots.columns:
            self.pilots["current_assignment"] = self.pilots["current_assignment"].fillna("-")
        if "current_assignment" in self.drones.columns:
            self.drones["current_assignment"] = self.drones["current_assignment"].fillna("-")

    def query_pilots(
        self,
        skill: Optional[str] = None,
        certification: Optional[str] = None,
        location: Optional[str] = None,
        status: Optional[str] = None,
    ) -> pd.DataFrame:
        df = self.pilots.copy()
        if skill:
            needle = skill.lower()
            df = df[df["skills"].str.lower().str.contains(needle, na=False)]
        if certification:
            needle = certification.lower()
            df = df[df["certifications"].str.lower().str.contains(needle, na=False)]
        if location:
            df = df[df["location"].str.lower() == location.lower()]
        if status:
            df = df[df["status"].str.lower() == status.lower()]
        return df

    def query_drones(
        self,
        capability: Optional[str] = None,
        location: Optional[str] = None,
        status: Optional[str] = None,
        weather: Optional[str] = None,
    ) -> pd.DataFrame:
        df = self.drones.copy()
        if capability:
            needle = capability.lower()
            df = df[df["capabilities"].str.lower().str.contains(needle, na=False)]
        if location:
            df = df[df["location"].str.lower() == location.lower()]
        if status:
            df = df[df["status"].str.lower() == status.lower()]
        if weather:
            df = df[df["weather_resistance"].apply(lambda x: _drone_weather_ok(x, weather))]
        return df

    def update_pilot_status(self, pilot_id: str, new_status: str) -> Tuple[bool, str]:
        idx = self.pilots[self.pilots["pilot_id"].str.lower() == pilot_id.lower()].index
        if len(idx) == 0:
            return False, f"Pilot {pilot_id} not found"
        self.pilots.loc[idx, "status"] = new_status
        if new_status.lower() != "assigned":
            self.pilots.loc[idx, "current_assignment"] = "-"
        return True, f"Pilot {pilot_id} updated to {new_status}"

    def update_drone_status(self, drone_id: str, new_status: str) -> Tuple[bool, str]:
        idx = self.drones[self.drones["drone_id"].str.lower() == drone_id.lower()].index
        if len(idx) == 0:
            return False, f"Drone {drone_id} not found"
        self.drones.loc[idx, "status"] = new_status
        if new_status.lower() != "assigned":
            self.drones.loc[idx, "current_assignment"] = "-"
        return True, f"Drone {drone_id} updated to {new_status}"

    def mission_by_id(self, project_id: str) -> Optional[pd.Series]:
        rows = self.missions[self.missions["project_id"].str.lower() == project_id.lower()]
        if rows.empty:
            return None
        return rows.iloc[0]

    def pilot_cost_for_mission(self, pilot_id: str, project_id: str) -> Tuple[Optional[float], str]:
        pilot_rows = self.pilots[self.pilots["pilot_id"].str.lower() == pilot_id.lower()]
        mission = self.mission_by_id(project_id)
        if pilot_rows.empty:
            return None, f"Pilot {pilot_id} not found"
        if mission is None:
            return None, f"Mission {project_id} not found"
        days = _days_inclusive(mission["start_date"], mission["end_date"])
        cost = float(pilot_rows.iloc[0].get("daily_rate_inr", 0)) * days
        return cost, f"Pilot cost for {project_id} is INR {cost:.0f} ({days} day(s))"

    def _pilot_qualified_for_mission(self, pilot: pd.Series, mission: pd.Series) -> Tuple[bool, List[str]]:
        reasons = []
        req_skills = _split_multi(mission.get("required_skills", ""))
        req_certs = _split_multi(mission.get("required_certs", ""))
        pilot_skills = _split_multi(pilot.get("skills", ""))
        pilot_certs = _split_multi(pilot.get("certifications", ""))

        missing_skills = [s for s in req_skills if s not in pilot_skills]
        missing_certs = [c for c in req_certs if c not in pilot_certs]
        if missing_skills:
            reasons.append(f"missing skills: {', '.join(missing_skills)}")
        if missing_certs:
            reasons.append(f"missing certifications: {', '.join(missing_certs)}")

        if str(pilot.get("status", "")).lower() != "available":
            reasons.append(f"status is {pilot.get('status')}")

        if str(pilot.get("location", "")).lower() != str(mission.get("location", "")).lower():
            reasons.append("location mismatch")

        cost = float(pilot.get("daily_rate_inr", 0)) * _days_inclusive(mission["start_date"], mission["end_date"])
        budget = float(mission.get("mission_budget_inr", 0))
        if cost > budget:
            reasons.append("budget overrun")

        return len(reasons) == 0, reasons

    def _drone_qualified_for_mission(self, drone: pd.Series, mission: pd.Series) -> Tuple[bool, List[str]]:
        reasons = []
        req_skills = _split_multi(mission.get("required_skills", ""))
        capabilities = _split_multi(drone.get("capabilities", ""))

        if req_skills and not any(req in capabilities for req in req_skills):
            reasons.append("capability mismatch")

        if str(drone.get("status", "")).lower() != "available":
            reasons.append(f"status is {drone.get('status')}")

        if str(drone.get("location", "")).lower() != str(mission.get("location", "")).lower():
            reasons.append("location mismatch")

        if not _drone_weather_ok(drone.get("weather_resistance", ""), mission.get("weather_forecast", "")):
            reasons.append("weather risk")

        due = drone.get("maintenance_due")
        start = mission.get("start_date")
        if pd.notna(due) and pd.notna(start) and due <= start:
            reasons.append("maintenance due before mission")

        return len(reasons) == 0, reasons

    def match_pilots(self, project_id: str, top_k: int = 5) -> List[Dict]:
        mission = self.mission_by_id(project_id)
        if mission is None:
            return []

        ranked = []
        for _, pilot in self.pilots.iterrows():
            ok, reasons = self._pilot_qualified_for_mission(pilot, mission)
            score = 100
            if not ok:
                score -= 20 * len(reasons)
            if str(pilot.get("location", "")).lower() == str(mission.get("location", "")).lower():
                score += 10
            cost = float(pilot.get("daily_rate_inr", 0)) * _days_inclusive(mission["start_date"], mission["end_date"])
            score -= int(cost / 1000)
            ranked.append(
                {
                    "pilot_id": pilot["pilot_id"],
                    "name": pilot.get("name"),
                    "score": score,
                    "qualified": ok,
                    "reasons": "; ".join(reasons) if reasons else "OK",
                }
            )

        ranked.sort(key=lambda x: x["score"], reverse=True)
        return ranked[:top_k]

    def match_drones(self, project_id: str, top_k: int = 5) -> List[Dict]:
        mission = self.mission_by_id(project_id)
        if mission is None:
            return []

        ranked = []
        for _, drone in self.drones.iterrows():
            ok, reasons = self._drone_qualified_for_mission(drone, mission)
            score = 100
            if not ok:
                score -= 20 * len(reasons)
            if str(drone.get("location", "")).lower() == str(mission.get("location", "")).lower():
                score += 10
            ranked.append(
                {
                    "drone_id": drone["drone_id"],
                    "model": drone.get("model"),
                    "score": score,
                    "qualified": ok,
                    "reasons": "; ".join(reasons) if reasons else "OK",
                }
            )

        ranked.sort(key=lambda x: x["score"], reverse=True)
        return ranked[:top_k]

    def assign(self, project_id: str, pilot_id: str, drone_id: str) -> Dict:
        mission = self.mission_by_id(project_id)
        if mission is None:
            return {"ok": False, "message": f"Mission {project_id} not found", "warnings": []}

        pilot_rows = self.pilots[self.pilots["pilot_id"].str.lower() == pilot_id.lower()]
        drone_rows = self.drones[self.drones["drone_id"].str.lower() == drone_id.lower()]
        if pilot_rows.empty:
            return {"ok": False, "message": f"Pilot {pilot_id} not found", "warnings": []}
        if drone_rows.empty:
            return {"ok": False, "message": f"Drone {drone_id} not found", "warnings": []}

        pilot = pilot_rows.iloc[0]
        drone = drone_rows.iloc[0]

        _, pilot_reasons = self._pilot_qualified_for_mission(pilot, mission)
        _, drone_reasons = self._drone_qualified_for_mission(drone, mission)
        warnings = pilot_reasons + drone_reasons

        pidx = pilot_rows.index
        didx = drone_rows.index

        self.pilots.loc[pidx, "status"] = "Assigned"
        self.pilots.loc[pidx, "current_assignment"] = project_id

        self.drones.loc[didx, "status"] = "Assigned"
        self.drones.loc[didx, "current_assignment"] = project_id

        return {
            "ok": True,
            "message": f"Assigned pilot {pilot_id} and drone {drone_id} to {project_id}",
            "warnings": warnings,
        }

    def active_assignments(self) -> pd.DataFrame:
        p = self.pilots[["pilot_id", "name", "current_assignment", "status", "location"]].copy()
        p = p[p["current_assignment"] != "-"]
        p["asset_type"] = "Pilot"

        d = self.drones[["drone_id", "model", "current_assignment", "status", "location"]].copy()
        d = d[d["current_assignment"] != "-"]
        d = d.rename(columns={"drone_id": "pilot_id", "model": "name"})
        d["asset_type"] = "Drone"

        cols = ["asset_type", "pilot_id", "name", "current_assignment", "status", "location"]
        return pd.concat([p[cols], d[cols]], ignore_index=True)

    def detect_conflicts(self) -> List[Dict]:
        conflicts = []

        mission_map = {row["project_id"]: row for _, row in self.missions.iterrows()}

        for _, pilot in self.pilots.iterrows():
            assn = str(pilot.get("current_assignment", "-"))
            if assn == "-":
                continue
            mission = mission_map.get(assn)
            if mission is None:
                conflicts.append(
                    {
                        "type": "Missing Mission",
                        "severity": "high",
                        "message": f"Pilot {pilot['pilot_id']} assigned to unknown mission {assn}",
                    }
                )
                continue

            ok, reasons = self._pilot_qualified_for_mission(pilot, mission)
            if not ok:
                for reason in reasons:
                    severity = "high" if "missing" in reason else "medium"
                    conflicts.append(
                        {
                            "type": "Pilot Conflict",
                            "severity": severity,
                            "message": f"Pilot {pilot['pilot_id']} on {assn}: {reason}",
                        }
                    )

        for _, drone in self.drones.iterrows():
            assn = str(drone.get("current_assignment", "-"))
            if assn == "-":
                continue
            mission = mission_map.get(assn)
            if mission is None:
                conflicts.append(
                    {
                        "type": "Missing Mission",
                        "severity": "high",
                        "message": f"Drone {drone['drone_id']} assigned to unknown mission {assn}",
                    }
                )
                continue

            ok, reasons = self._drone_qualified_for_mission(drone, mission)
            if not ok:
                for reason in reasons:
                    severity = "high" if reason in {"weather risk", "maintenance due before mission"} else "medium"
                    conflicts.append(
                        {
                            "type": "Drone Conflict",
                            "severity": severity,
                            "message": f"Drone {drone['drone_id']} on {assn}: {reason}",
                        }
                    )

        mission_windows = []
        for _, m in self.missions.iterrows():
            mission_windows.append((m["project_id"], m["start_date"], m["end_date"]))

        pilot_assignments = self.pilots[self.pilots["current_assignment"] != "-"][["pilot_id", "current_assignment"]]
        for _, row in pilot_assignments.iterrows():
            pid = row["pilot_id"]
            assigned = str(row["current_assignment"]).split("|")
            assigned = [a.strip() for a in assigned if a.strip()]
            for i in range(len(assigned)):
                for j in range(i + 1, len(assigned)):
                    m1 = self.mission_by_id(assigned[i])
                    m2 = self.mission_by_id(assigned[j])
                    if m1 is None or m2 is None:
                        continue
                    if m1["start_date"] <= m2["end_date"] and m2["start_date"] <= m1["end_date"]:
                        conflicts.append(
                            {
                                "type": "Double Booking",
                                "severity": "high",
                                "message": f"Pilot {pid} has overlapping missions {assigned[i]} and {assigned[j]}",
                            }
                        )

        return sorted(conflicts, key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x["severity"], 3))

    def urgent_reassignment(self, project_id: str) -> Dict:
        mission = self.mission_by_id(project_id)
        if mission is None:
            return {"ok": False, "message": f"Mission {project_id} not found"}

        urgency = str(mission.get("priority", "")).lower() in {"urgent", "high"}
        today = pd.Timestamp(datetime.utcnow().date())
        starts_soon = pd.notna(mission["start_date"]) and (mission["start_date"] - today).days <= 2

        if not urgency and not starts_soon:
            return {
                "ok": True,
                "message": f"Mission {project_id} is not urgent by rule (priority/date)",
                "pilot_options": [],
                "drone_options": [],
            }

        pilot_options = [x for x in self.match_pilots(project_id, top_k=5) if x["qualified"]]
        drone_options = [x for x in self.match_drones(project_id, top_k=5) if x["qualified"]]

        return {
            "ok": True,
            "message": f"Urgent reassignment options for {project_id}",
            "pilot_options": pilot_options,
            "drone_options": drone_options,
        }

    def handle_query(self, text: str) -> Tuple[str, Optional[pd.DataFrame]]:
        q = text.strip().lower()

        if "conflict" in q:
            conflicts = self.detect_conflicts()
            if not conflicts:
                return "No conflicts detected.", None
            lines = [f"- [{c['severity']}] {c['message']}" for c in conflicts]
            return "Conflicts:\n" + "\n".join(lines), pd.DataFrame(conflicts)

        if "active assignment" in q:
            df = self.active_assignments()
            return "Active assignments listed below.", df

        match = re.search(r"pilot\s+(p\d+)\s+status\s+([a-z\s]+)", q)
        if match:
            raw_status = match.group(2).strip()
            if raw_status.startswith("to "):
                raw_status = raw_status[3:]
            status = self._normalize_status(raw_status, for_drone=False)
            ok, msg = self.update_pilot_status(match.group(1).upper(), status)
            return msg, None

        match = re.search(r"drone\s+(d\d+)\s+status\s+([a-z\s]+)", q)
        if match:
            raw_status = match.group(2).strip()
            if raw_status.startswith("to "):
                raw_status = raw_status[3:]
            status = self._normalize_status(raw_status, for_drone=True)
            ok, msg = self.update_drone_status(match.group(1).upper(), status)
            return msg, None

        match = re.search(r"match\s+(prj\d+)", q)
        if match:
            pid = match.group(1).upper()
            pilots = pd.DataFrame(self.match_pilots(pid))
            drones = pd.DataFrame(self.match_drones(pid))
            merged = {"pilots": pilots, "drones": drones}
            return f"Top matches for {pid} shown in tables.", merged

        match = re.search(r"urgent\s+(prj\d+)", q)
        if match:
            out = self.urgent_reassignment(match.group(1).upper())
            if not out["ok"]:
                return out["message"], None
            return out["message"], {
                "pilot_options": pd.DataFrame(out["pilot_options"]),
                "drone_options": pd.DataFrame(out["drone_options"]),
            }

        match = re.search(r"cost\s+(p\d+)\s+(prj\d+)", q)
        if match:
            cost, msg = self.pilot_cost_for_mission(match.group(1).upper(), match.group(2).upper())
            return msg, None

        if "available pilots" in q:
            df = self.query_pilots(status="Available")
            return "Available pilots listed below.", df

        if "available drones" in q:
            df = self.query_drones(status="Available")
            return "Available drones listed below.", df

        help_text = (
            "Try: 'show conflicts', 'available pilots', 'available drones', 'match PRJ001', "
            "'cost P001 PRJ001', 'pilot P001 status On Leave', 'drone D003 status Maintenance', "
            "or 'urgent PRJ002'."
        )
        return help_text, None

    @staticmethod
    def _normalize_status(raw: str, for_drone: bool) -> str:
        cleaned = raw.strip().lower()
        if cleaned.startswith("to "):
            cleaned = cleaned[3:].strip()

        if for_drone:
            mapping = {
                "available": "Available",
                "assigned": "Assigned",
                "maintenance": "Maintenance",
                "unavailable": "Unavailable",
            }
        else:
            mapping = {
                "available": "Available",
                "assigned": "Assigned",
                "on leave": "On Leave",
                "leave": "On Leave",
                "unavailable": "Unavailable",
            }
        return mapping.get(cleaned, cleaned.title())
