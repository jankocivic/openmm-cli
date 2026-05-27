"""Streamlit dashboard for visualising openmm-cli output CSVs."""
import argparse
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# Parse args passed after `--` from the launcher
_parser = argparse.ArgumentParser()
_parser.add_argument("--directory", default=str(Path.cwd()))
_args, _ = _parser.parse_known_args()

st.set_page_config(page_title="openmm-cli dashboard", layout="wide")
st.title("openmm-cli — simulation dashboard")

output_dir = Path(st.text_input("Directory", _args.directory))

if not output_dir.exists():
    st.warning(f"Directory {output_dir} not found.")
    st.stop()

csvs = sorted(output_dir.glob("*.csv"))
if not csvs:
    st.info("No CSV files found in this directory yet.")
    st.stop()

# Sidebar: which CSVs to show
selected = st.sidebar.multiselect(
    "Files to display",
    options=[p.name for p in csvs],
    default=[p.name for p in csvs],
)
for path in csvs:
    if path.name not in selected:
        continue

    st.subheader(path.name)

    try:
        df = pd.read_csv(path)
    except Exception as e:
        st.error(f"Could not read {path.name}: {e}")
        continue
    # Clean OpenMM-style headers
    df.columns = [c.lstrip("#").strip() for c in df.columns]
    
    if df.empty:
        st.write("(empty file)")
        continue
    
    # Non-numeric first column → table (hbonds-like)
    if not pd.api.types.is_numeric_dtype(df.iloc[:, 0]):
        st.dataframe(df, width="stretch")
        continue
    
    # Find time- and step-like columns
    time_cols = [c for c in df.columns if "time" in c.lower()]
    step_cols = [c for c in df.columns if c.lower() in ("step","frame")]
    
    # Neither time nor step → not a time series; show as a table (rmsf-like)
    if not time_cols and not step_cols:
        st.dataframe(df, width="stretch")
        continue
    
    # Prefer time over step as the x-axis
    x = time_cols[0] if time_cols else step_cols[0]
    
    # Drop time/step/progress columns from y options
    skip = set(time_cols) | set(step_cols) | {c for c in df.columns if "progress" in c.lower()}
    y_options = [c for c in df.columns if c not in skip and pd.api.types.is_numeric_dtype(df[c])]
    
    y_cols = st.multiselect(
        f"Columns to plot for {path.name}",
        options=y_options,
        default=y_options,
        key=path.name,
    )
   
    for col in y_cols:
        fig = px.line(df, x=x, y=col, title=col)
        st.plotly_chart(fig, width="stretch", key=f"{path.name}:{col}")
