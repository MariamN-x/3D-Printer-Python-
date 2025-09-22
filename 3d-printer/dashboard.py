import json
import pandas as pd
import streamlit as st
import plotly.express as px
from pathlib import Path

# ------------------------------
# Load log into DataFrame
# ------------------------------
def load_log(file):
    with open(file, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]

def to_dataframe(log):
    return pd.DataFrame(log)

# ------------------------------
# Extract temperature readings
# ------------------------------
def extract_temperature_series(df):
    temps = []
    for _, row in df.iterrows():
        d = row.get("details", {}) or {}
        for k in ("hotend", "bed", "temp", "temperature"):
            if k in d:
                temps.append({
                    "time": row["time"],
                    "component": row["component"],
                    "temp": float(d[k])
                })
    return pd.DataFrame(temps)

# ------------------------------
# Streamlit Dashboard
# ------------------------------
def run_dashboard(logfile):
    st.set_page_config(page_title="3D Printer Admin Dashboard", layout="wide")
    st.title("🖨️ Smart 3D Printer - Admin Dashboard")

    log = load_log(logfile)
    df = to_dataframe(log)

    # 🔹 KPI Summary
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Events", len(df))
    with col2:
        st.metric("Unique Components", df['component'].nunique())
    with col3:
        st.metric("Event Types", df['event_type'].nunique())
    with col4:
        errors = df[df['event_type'].str.contains("ERROR", case=False)]
        st.metric("Errors", len(errors))

    # 🔹 Event Counts (interactive)
    st.header("📊 Event Counts")
    event_counts = df["event_type"].value_counts().reset_index()
    event_counts.columns = ["event_type", "count"]
    fig = px.bar(event_counts, x="event_type", y="count", title="Event Counts")
    st.plotly_chart(fig, use_container_width=True)

    # 🔹 Temperature Charts (interactive)
    st.header("🌡️ Temperature Over Time")
    temp_df = extract_temperature_series(df)
    if not temp_df.empty:
        fig = px.line(temp_df, x="time", y="temp", color="component",
                      title="Temperature Over Time")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No temperature data in log.")

    # 🔹 ECU State Changes (interactive)
    st.header("⚙️ ECU State Changes")
    states = df[df["event_type"] == "STATE_CHANGE"].copy()
    if not states.empty:
        states["details_str"] = states["details"].astype(str)
        util_counts = states.groupby(["component", "details_str"]).size().reset_index(name="count")

        fig = px.bar(util_counts, x="details_str", y="count", color="component",
                     title="ECU State Changes")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No state change events in log.")

    # 🔹 Raw Event Log
    st.header("📜 Raw Event Log")
    st.dataframe(df)

# ------------------------------
# Entry Point
# ------------------------------
if __name__ == "__main__":
    logfile = "simulation_log.jsonl"
    if Path(logfile).exists():
        run_dashboard(logfile)
    else:
        print("❌ No log file found. Run main.py first to generate simulation_log.jsonl")
