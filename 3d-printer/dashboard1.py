import json
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
from tkinter import ttk, messagebox
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
# Build Tkinter Dashboard
# ------------------------------
class Dashboard(tk.Tk):
    def __init__(self, logfile="simulation_log.jsonl"):
        super().__init__()
        self.title("🖨️ Smart 3D Printer - Admin Dashboard")
        self.geometry("1000x700")

        if not Path(logfile).exists():
            messagebox.showerror("Error", f"No log file found: {logfile}\nRun main.py first.")
            self.destroy()
            return

        self.df = to_dataframe(load_log(logfile))

        # Create notebook (tabs)
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        # Tabs
        self.log_tab = ttk.Frame(notebook)
        self.temp_tab = ttk.Frame(notebook)
        self.events_tab = ttk.Frame(notebook)
        self.ecu_tab = ttk.Frame(notebook)

        notebook.add(self.log_tab, text="📜 Event Log")
        notebook.add(self.temp_tab, text="🌡️ Temperature")
        notebook.add(self.events_tab, text="📊 Event Counts")
        notebook.add(self.ecu_tab, text="⚙️ ECU States")

        # Fill tabs
        self.show_log()
        self.show_temperatures()
        self.show_event_counts()
        self.show_ecu_states()

    def show_log(self):
        cols = list(self.df.columns)
        tree = ttk.Treeview(self.log_tab, columns=cols, show="headings")
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=150, anchor="center")
        for _, row in self.df.iterrows():
            tree.insert("", "end", values=[row.get(c) for c in cols])
        tree.pack(fill="both", expand=True)

    def show_temperatures(self):
        temp_df = extract_temperature_series(self.df)
        if temp_df.empty:
            tk.Label(self.temp_tab, text="No temperature data available").pack()
            return

        fig, ax = plt.subplots(figsize=(6, 4))
        for comp in temp_df["component"].unique():
            subset = temp_df[temp_df["component"] == comp]
            ax.plot(subset["time"], subset["temp"], label=comp)
        ax.set_xlabel("Time")
        ax.set_ylabel("Temperature (°C)")
        ax.legend()
        ax.set_title("Temperature Over Time")

        canvas = FigureCanvasTkAgg(fig, master=self.temp_tab)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def show_event_counts(self):
        counts = self.df["event_type"].value_counts()
        fig, ax = plt.subplots(figsize=(6, 4))
        counts.plot(kind="bar", ax=ax)
        ax.set_title("Event Counts")
        ax.set_ylabel("Count")

        canvas = FigureCanvasTkAgg(fig, master=self.events_tab)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def show_ecu_states(self):
        states = self.df[self.df["event_type"] == "STATE_CHANGE"].copy()
        if states.empty:
            tk.Label(self.ecu_tab, text="No ECU state change data available").pack()
            return

        states["details_str"] = states["details"].astype(str)
        util_counts = states.groupby(["component", "details_str"]).size().reset_index(name="count")

        fig, ax = plt.subplots(figsize=(6, 4))
        util_counts.plot(kind="bar", x="details_str", y="count", ax=ax, legend=False)
        ax.set_title("ECU State Changes")
        ax.set_ylabel("Count")

        canvas = FigureCanvasTkAgg(fig, master=self.ecu_tab)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)


# ------------------------------
# Run the GUI
# ------------------------------
if __name__ == "__main__":
    app = Dashboard("simulation_log.jsonl")
    app.mainloop()
