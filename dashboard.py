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
        # Check multiple possible temperature field names
        for k in ("hotend", "bed", "temp", "temperature", "target_temp", "current_temp"):
            if k in d:
                temps.append({
                    "time": row["time"],
                    "component": row.get("component", "unknown"),
                    "temp": float(d[k])
                })
    return pd.DataFrame(temps)

# ------------------------------
# Debug function to see actual data structure
# ------------------------------
def debug_data_structure(df):
    st.sidebar.header("🔍 Data Structure Debug")
    st.sidebar.write("Columns:", list(df.columns))
    st.sidebar.write("First few rows:")
    st.sidebar.dataframe(df.head())
    st.sidebar.write("Sample event types:")
    st.sidebar.write(df['event_type'].value_counts() if 'event_type' in df.columns else "No event_type column")

# ------------------------------
# Streamlit Dashboard
# ------------------------------
def run_dashboard(logfile):
    st.set_page_config(page_title="3D Printer Admin Dashboard", layout="wide")
    st.title("🖨️ Smart 3D Printer - Admin Dashboard")

    log = load_log(logfile)
    df = to_dataframe(log)
    
    # Debug information
    debug_data_structure(df)

    # 🔹 KPI Summary - Safe column access
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Events", len(df))
    with col2:
        # Safe component count - use available column
        if 'component' in df.columns:
            st.metric("Unique Components", df['component'].nunique())
        elif 'event_type' in df.columns:
            st.metric("Unique Event Types", df['event_type'].nunique())
        else:
            st.metric("Unique Entries", len(df.drop_duplicates()))
    with col3:
        if 'event_type' in df.columns:
            st.metric("Event Types", df['event_type'].nunique())
        else:
            st.metric("Data Columns", len(df.columns))
    with col4:
        if 'event_type' in df.columns:
            errors = df[df['event_type'].str.contains("ERROR", case=False, na=False)]
            st.metric("Errors", len(errors))
        else:
            st.metric("Data Points", len(df))

    # 🔹 Event Counts (interactive) - only if event_type exists
    if 'event_type' in df.columns:
        st.header("📊 Event Counts")
        event_counts = df["event_type"].value_counts().reset_index()
        event_counts.columns = ["event_type", "count"]
        fig = px.bar(event_counts, x="event_type", y="count", title="Event Counts")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No event_type data available for event counts chart.")

    # 🔹 Temperature Charts (interactive)
    st.header("🌡️ Temperature Over Time")
    temp_df = extract_temperature_series(df)
    if not temp_df.empty:
        fig = px.line(temp_df, x="time", y="temp", color="component",
                      title="Temperature Over Time")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No temperature data in log.")

    # 🔹 ECU State Changes (interactive) - only if relevant columns exist
    if 'event_type' in df.columns and 'component' in df.columns:
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
    else:
        st.info("No component or event_type data available for state changes chart.")

    # 🔹 Raw Event Log with column selector
    st.header("📜 Raw Event Log")
    
    # Allow column selection for better viewing
    if st.checkbox("Select columns to display"):
        available_columns = list(df.columns)
        selected_columns = st.multiselect("Choose columns:", available_columns, default=available_columns)
        st.dataframe(df[selected_columns] if selected_columns else df)
    else:
        st.dataframe(df)

# ------------------------------
# Entry Point
# ------------------------------
if __name__ == "__main__":
    logfile = "simulation_log.jsonl"
    if Path(logfile).exists():
        # First, let's check what's actually in the log file
        print("🔍 Checking log file structure...")
        try:
            with open(logfile, "r", encoding="utf-8") as f:
                first_line = f.readline()
                if first_line:
                    sample_data = json.loads(first_line)
                    print("Sample log entry structure:", sample_data)
        except Exception as e:
            print(f"Error reading log file: {e}")
        
        run_dashboard(logfile)
    else:
        st.error("❌ No log file found. Run main.py first to generate simulation_log.jsonl")
        print("❌ No log file found. Run main.py first to generate simulation_log.jsonl")