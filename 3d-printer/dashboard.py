import json
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
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

    # Show raw data
    with st.expander("📜 Raw Event Log"):
        st.dataframe(df)

    # --- Event counts ---
    st.subheader("📊 Event Counts")
    event_counts = df["event_type"].value_counts()
    st.bar_chart(event_counts)

    # --- Temperature charts ---
    st.subheader("🌡️ Temperature Over Time")
    temp_df = extract_temperature_series(df)
    if not temp_df.empty:
        fig, ax = plt.subplots()
        for comp in temp_df["component"].unique():
            subset = temp_df[temp_df["component"] == comp]
            ax.plot(subset["time"], subset["temp"], label=comp)
        ax.set_xlabel("Time")
        ax.set_ylabel("Temperature (°C)")
        ax.legend()
        st.pyplot(fig)
    else:
        st.info("No temperature data in log.")

    # --- Utilization stats ---
    st.subheader("⚙️ ECU State Changes")
    states = df[df["event_type"] == "STATE_CHANGE"]
    if not states.empty:
        util_counts = states.groupby(["component", "details"]).size()
        st.write(util_counts)
    else:
        st.info("No state change events in log.")

    st.success("✅ Dashboard Loaded Successfully")

# ------------------------------
# Entry Point
# ------------------------------
if __name__ == "__main__":
    logfile = "simulation_log.jsonl"
    if Path(logfile).exists():
        run_dashboard(logfile)
    else:
        print("❌ No log file found. Run main.py first to generate simulation_log.jsonl")
