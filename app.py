from __future__ import annotations

import streamlit as st

from coordinator import Coordinator
from data_store import DataStore

st.set_page_config(page_title="Skylark Drone Operations Coordinator", layout="wide",initial_sidebar_state="collapsed")
st.title("Skylark Drone Operations Coordinator AI Agent")

store = DataStore()

if "coordinator" not in st.session_state:
    pilots_df, drones_df, missions_df = store.load_all()
    st.session_state.coordinator = Coordinator(pilots_df, drones_df, missions_df)
    st.session_state.chat = []
    st.session_state.last_update_heading = ""

coord: Coordinator = st.session_state.coordinator

with st.sidebar:
    st.header("Data + Sync")
    if st.button("Reload from CSV / Google Sheets"):
        pilots_df, drones_df, missions_df = store.load_all()
        st.session_state.coordinator = Coordinator(pilots_df, drones_df, missions_df)
        coord = st.session_state.coordinator
        st.success("Data reloaded")

    st.caption("If Google Sheets env vars are configured, reads are pulled from sheets first.")

    st.subheader("Quick Actions")
    with st.form("pilot_status_form"):
        pid = st.text_input("Pilot ID", "P001")
        pstatus = st.selectbox("Pilot Status", ["Available", "Assigned", "On Leave", "Unavailable"])
        submitted = st.form_submit_button("Update Pilot Status")
        if submitted:
            ok, msg = coord.update_pilot_status(pid.strip().upper(), pstatus)
            if ok:
                sync_ok = store.save_pilots(coord.pilots)
                if sync_ok:
                    st.success(msg + " (synced to Google Sheets)")
                else:
                    st.success(msg + " (saved locally; sync unavailable)")
            else:
                st.error(msg)

    with st.form("drone_status_form"):
        did = st.text_input("Drone ID", "D001")
        dstatus = st.selectbox("Drone Status", ["Available", "Assigned", "Maintenance", "Unavailable"])
        dsubmitted = st.form_submit_button("Update Drone Status")
        if dsubmitted:
            ok, msg = coord.update_drone_status(did.strip().upper(), dstatus)
            if ok:
                sync_ok = store.save_drones(coord.drones)
                if sync_ok:
                    st.success(msg + " (synced to Google Sheets)")
                else:
                    st.success(msg + " (saved locally; sync unavailable)")
            else:
                st.error(msg)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Pilots", len(coord.pilots))
with col2:
    st.metric("Drones", len(coord.drones))
with col3:
    st.metric("Missions", len(coord.missions))

st.subheader("Conversational Assistant")

if st.session_state.get("last_update_heading"):
    st.caption(st.session_state["last_update_heading"])

for role, content in st.session_state.chat:
    with st.chat_message(role):
        if isinstance(content, str):
            st.markdown(content)
        elif isinstance(content, dict):
            for key, val in content.items():
                st.markdown(f"**{key}**")
                if hasattr(val, "empty"):
                    if val.empty:
                        st.caption("No rows")
                    else:
                        st.dataframe(val, use_container_width=True)
        else:
            if hasattr(content, "empty"):
                st.dataframe(content, use_container_width=True)

prompt = st.chat_input("Ask: show conflicts, match PRJ001, urgent PRJ002, pilot P001 status On Leave")
if prompt:
    st.session_state.chat.append(("user", prompt))
    response, payload = coord.handle_query(prompt)

    st.session_state.chat.append(("assistant", response))
    if payload is not None:
        st.session_state.chat.append(("assistant", payload))

    if "pilot" in prompt.lower() and "status" in prompt.lower():
        store.save_pilots(coord.pilots)
        st.session_state["last_update_heading"] = "Updated Pilot Roster"
    if "drone" in prompt.lower() and "status" in prompt.lower():
        store.save_drones(coord.drones)
        st.session_state["last_update_heading"] = "Updated Drone Fleet"
    if "status" not in prompt.lower():
        st.session_state["last_update_heading"] = "Current System State"

    st.rerun()

st.markdown("### Current System State")
with st.expander("Data Tables"):
    st.markdown("**Pilot Roster**")
    st.dataframe(coord.pilots, use_container_width=True)
    st.markdown("**Drone Fleet**")
    st.dataframe(coord.drones, use_container_width=True)
    st.markdown("**Missions**")
    st.dataframe(coord.missions, use_container_width=True)
