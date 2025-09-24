
import sys
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

OUT_DIR = Path(".")

def load_log(filename: str) -> pd.DataFrame:
    df = pd.read_json(filename, lines=True)
    df['time'] = df['time'].astype(float)
    return df.sort_values('time').reset_index(drop=True)

def extract_temperature_series(df):
    temps = []
    for _, row in df.iterrows():
        d = row.get('details', {}) or {}
        for k in ('current_temp','temp','temperature'):
            if k in d:
                temps.append({'time': row['time'], 'component': row['component'], 'temp': float(d[k])})
                break
    return pd.DataFrame(temps)

def compute_utilization(df, sim_end=None):
    if sim_end is None:
        sim_end = df['time'].max()
    events = df[['time','component','event_type']].to_dict('records')
    busy = {}
    stacks = {}
    for ev in events:
        comp = ev['component']
        et = ev['event_type']
        if comp not in stacks:
            stacks[comp] = {}
            busy[comp] = 0.0
        if '_' in et:
            base, suffix = et.rsplit('_', 1)
            if suffix.lower() in ('start','begin','on'):
                stacks[comp].setdefault(base, []).append(ev['time'])
            elif suffix.lower() in ('end','finish','done','off'):
                if stacks[comp].get(base):
                    t0 = stacks[comp][base].pop()
                    busy[comp] += max(0.0, ev['time'] - t0)
    for comp, comp_stacks in stacks.items():
        for base, start_list in comp_stacks.items():
            for t0 in start_list:
                busy[comp] += max(0.0, sim_end - t0)
    rows = []
    for comp, b in busy.items():
        rows.append({'component': comp, 'busy_time': b, 'sim_time': sim_end, 'utilization': b / sim_end if sim_end>0 else 0.0})
    return pd.DataFrame(rows)

def count_events(df):
    return df['event_type'].value_counts().rename_axis('event_type').reset_index(name='count')

def run_all(filename: str):
    df = load_log(filename)
    sim_end = df['time'].max()
    temp_df = extract_temperature_series(df)
    if not temp_df.empty:
        plt.figure()
        plt.plot(temp_df['time'], temp_df['temp'])
        plt.xlabel('Time (s)')
        plt.ylabel('Temperature (°C)')
        plt.title('Temperature vs Time')
        plt.tight_layout()
        plt.savefig(OUT_DIR / "temperature_plot.png")
        plt.close()
    util_df = compute_utilization(df, sim_end=sim_end)
    if not util_df.empty:
        plt.figure()
        plt.bar(util_df['component'], util_df['utilization'])
        plt.xlabel('Component')
        plt.ylabel('Utilization (fraction)')
        plt.title('Component Utilization')
        plt.tight_layout()
        plt.savefig(OUT_DIR / "utilization_plot.png")
        plt.close()
    ev_counts = count_events(df)
    plt.figure()
    plt.bar(ev_counts['event_type'], ev_counts['count'])
    plt.xticks(rotation=45, ha='right')
    plt.title('Event Counts')
    plt.tight_layout()
    plt.savefig(OUT_DIR / "event_counts.png")
    plt.close()
    # summary
    summary = {}
    if not temp_df.empty:
        summary['temp_mean'] = temp_df['temp'].mean()
        summary['temp_min'] = temp_df['temp'].min()
        summary['temp_max'] = temp_df['temp'].max()
    summary['total_events'] = len(df)
    summary['sim_time'] = sim_end
    s_df = pd.DataFrame(list(summary.items()), columns=['metric','value'])
    s_df.to_csv(OUT_DIR / "analysis_summary.csv", index=False)
    util_df.to_csv(OUT_DIR / "utilization_table.csv", index=False)
    return {
        "plots": ["temperature_plot.png","utilization_plot.png","event_counts.png"],
        "summary_csv": "analysis_summary.csv",
        "util_table": "utilization_table.csv"
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze.py simulation_log.jsonl")
    else:
        run_all(sys.argv[1])
