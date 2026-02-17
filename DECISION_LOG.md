# Decision Log (Skylark Drones Assignment)

## 1) Context and Goal

The objective was to deliver a working, hosted, conversational coordinator prototype in ~6 hours that can:

- manage pilot and drone availability,
- match resources to missions,
- detect operational conflicts,
- sync with Google Sheets (read + write for status updates),
- and support urgent reassignment decisions.

The implementation prioritizes deterministic operations logic over broad generative behavior so that assignment outcomes are explainable and auditable.

## 2) Key Assumptions

- A pilot is assignable only when `status == Available`.
- A drone is assignable only when `status == Available`.
- Mission duration is inclusive: `(end_date - start_date) + 1`.
- Pilot cost = `daily_rate_inr * mission_duration_days`.
- Rainy/storm missions require rain-capable drone weather resistance (`Rain` or `IP43` marker).
- If `maintenance_due <= mission_start`, the drone is flagged as maintenance risk.
- Location mismatch is a risk warning; it does not hard-block manual assignment.
- Local CSV files act as cache; when configured, Google Sheets is treated as the operational source.
- `current_assignment` can represent multiple assignments when separated with `|` for overlap checks.

## 3) Architecture Choices

- UI Layer: Streamlit (`app.py`)
- Why: fastest path to a testable conversational interface and table-driven operations dashboard.

- Domain Logic Layer: `Coordinator` service (`coordinator.py`)
- Why: centralizes decision rules for matching, assignments, costing, and conflict detection.

- Data Layer: CSV + optional Google Sheets adapter (`data_store.py`, `sheets_sync.py`)
- Why: aligns directly with assignment constraints while keeping local fallback support.

- Integration Pattern: synchronous read/write with graceful fallback
- Why: simple operational model and reduced moving parts for a short timeline.

## 4) Trade-offs and Rationale

- Rule engine over LLM-based planning
- Benefit: consistent, testable, and explainable outputs for every edge case.
- Cost: narrower natural-language flexibility in user phrasing.

- Full-sheet write updates to Google Sheets
- Benefit: simple implementation and deterministic final state.
- Cost: inefficient for large sheets and weaker concurrency behavior.

- No persistent DB/event log in MVP
- Benefit: reduced setup and fast deployability.
- Cost: limited assignment history/audit and weaker reconciliation under concurrent users.

- Manual confirmation model (human-in-the-loop)
- Benefit: safe operational posture for mission reassignment decisions.
- Cost: slightly slower automated remediation.

## 5) Edge Cases and How They Are Handled

- Pilot assigned to overlapping projects
- Detected when multiple mission IDs exist in `current_assignment` and date windows intersect.

- Pilot missing required certification/skill
- Flagged as high/medium conflict through requirement-vs-profile checks.

- Pilot available but over budget
- Cost computed against mission budget; budget overrun raised as warning/conflict.

- Drone assigned while in maintenance or due before mission
- Drone status/maintenance checks raise conflict warnings.

- Drone not weather rated for forecast
- Rainy mission + non-rain drone triggers weather risk conflict.

- Pilot and drone in different locations from mission
- Location mismatch is surfaced as assignment risk alert.

## 6) Urgent Reassignment Interpretation

“Urgent reassignment” was implemented as a policy trigger when either condition is true:

- Mission priority is `Urgent` or `High`, or
- Mission starts within 48 hours.

When triggered, the system generates ranked alternatives for pilots and drones and filters to qualified candidates using status, skills/certs/capabilities, location, budget, weather, and maintenance constraints.

This was chosen to provide immediate actionability under time pressure while preserving safety constraints.

## 7) Google Sheets Sync Decisions

- Read path: app attempts to load all operational data from Google Sheets first; local CSV is fallback.
- Write path: pilot and drone status changes are persisted locally and then written to the target worksheet.
- Reliability approach: non-blocking error handling with local-state continuity if sheet write fails.
- Security note: service account credentials are loaded from environment/secret values or credential file path in local development.

## 8) Validation Performed

- Static sanity checks via Python compile step for main modules.
- Functional smoke checks for:
- conflict detection,
- mission matching,
- pilot mission cost calculation,
- pilot/drone status mutation flows,
- Google Sheets availability and read/write path.

## 9) Risks and Limitations

- Concurrency risk with full-sheet overwrites under multiple simultaneous coordinators.
- Simplified natural-language parser may miss unusual phrasing.
- Current overlap model relies on assignment field format rather than a normalized assignment ledger.
- No formal auth/authorization boundary in MVP interface.

## 10) What I Would Improve Next

- Introduce normalized assignment/event tables and row-level sheet or DB updates.
- Add test suite covering every required edge case as scenario-based tests.
- Add intent parsing with function-calling plus deterministic policy validation.
- Add role-based access controls and operation audit trails.
- Add proactive alert channels (Slack/email/webhook) for high-severity conflicts.
- Add observability: structured logs, action traces, and operator-facing error diagnostics.
