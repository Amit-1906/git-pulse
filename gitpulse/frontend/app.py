import os
import sys
from pathlib import Path
from datetime import datetime
import streamlit as st
import pandas as pd

# Ensure frontend directory is in python path
frontend_dir = Path(__file__).parent
if str(frontend_dir) not in sys.path:
    sys.path.insert(0, str(frontend_dir))

# Streamlit Multi-page App Configuration
st.set_page_config(
    page_title="GitPulse | GitHub ELT Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load Enterprise CSS
css_path = frontend_dir / "assets" / "style.css"
if css_path.exists():
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Initialize Session State
if "selected_repo" not in st.session_state:
    st.session_state["selected_repo"] = "All Monitored Repositories"

from components.header import render_header
from components.sidebar import render_sidebar
from components.metrics import render_metric_card
from components.charts import (
    create_activity_area_chart,
    create_pr_status_donut,
    create_issue_state_donut,
    create_contributors_leaderboard,
)
from services.api_client import api_client

# Render common navigation sidebar
render_sidebar()

# Overview Landing Content
render_header(
    title="GitPulse Executive Overview",
    subtitle="End-to-End ELT Intelligence for GitHub Repositories",
    current_repo=st.session_state["selected_repo"],
)

with st.spinner("Fetching platform telemetry..."):
    metrics = api_client.get_overview_metrics()
    prs = api_client.get_pull_requests(limit=300)
    issues = api_client.get_issues(limit=300)
    commits = api_client.get_commits(limit=300)
    runs = api_client.get_pipeline_runs()
    contributors = api_client.get_contributors()

# Top KPI Metric Cards
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    render_metric_card("Tracked Repos", str(metrics.get("total_repositories", 0)), icon="📁")
with c2:
    render_metric_card("Ingested Commits", f"{metrics.get('total_commits_tracked', 0):,}", icon="🔨")
with c3:
    render_metric_card("Pull Requests", str(metrics.get("total_pull_requests", 0)), icon="🔀")
with c4:
    render_metric_card("Issues Tracked", str(metrics.get("total_issues", 0)), icon="🐛")
with c5:
    success_rate = metrics.get("pipeline_success_rate", 100.0)
    render_metric_card("ELT Success Rate", f"{success_rate:.1f}%", icon="🛡️")

st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

# Visualizations Row
col_left, col_right = st.columns([2, 1])
with col_left:
    st.markdown("### 📈 Ingestion & Activity Velocity")
    if commits or prs:
        # Compute real activity velocity
        c_df = pd.DataFrame(commits) if commits else pd.DataFrame()
        p_df = pd.DataFrame(prs) if prs else pd.DataFrame()

        def _get_daily_counts(df: pd.DataFrame, col: str) -> pd.Series:
            if df.empty or col not in df.columns:
                return pd.Series(dtype=int)
            df[col] = pd.to_datetime(df[col], errors="coerce")
            return df.dropna(subset=[col]).set_index(col).resample("D").size()

        c_daily = _get_daily_counts(c_df, "author_date")
        p_daily = _get_daily_counts(p_df, "created_at")

        idx_union = c_daily.index.union(p_daily.index)
        if len(idx_union):
            dates_fmt = [d.strftime("%b %d") for d in idx_union]
            c_vals = [int(c_daily.get(d, 0)) for d in idx_union]
            p_vals = [int(p_daily.get(d, 0)) for d in idx_union]
            fig_act = create_activity_area_chart(dates_fmt, c_vals, p_vals)
            st.plotly_chart(fig_act, use_container_width=True)
        else:
            st.info("No timeline activity recorded yet.")
    else:
        st.info("No commit or pull request activity recorded yet. Run an extraction to populate.")

with col_right:
    st.markdown("### 🔀 Pull Request State Distribution")
    if prs:
        p_df2 = pd.DataFrame(prs)
        open_c = int((p_df2.get("state", pd.Series()) == "open").sum())
        merged_c = int((p_df2.get("is_merged", pd.Series()) == True).sum())
        closed_c = int(((p_df2.get("state", pd.Series()) == "closed") & (~p_df2.get("is_merged", pd.Series()).fillna(False))).sum())
        st.plotly_chart(create_pr_status_donut(open_cnt=open_c, merged_cnt=merged_c, closed_cnt=closed_c), use_container_width=True)
    else:
        st.info("No PR data available.")

st.markdown("### ⚡ Recent ELT Ingestion Batches")
if runs:
    runs_df = pd.DataFrame(runs)
    cols = [c for c in ["id", "pipeline_name", "stage", "status", "started_at", "duration_seconds", "records_loaded"] if c in runs_df.columns]
    st.dataframe(
        runs_df[cols],
        column_config={
            "id": st.column_config.NumberColumn("Run ID", format="%d"),
            "pipeline_name": "Pipeline",
            "stage": "Stage",
            "status": "Status",
            "started_at": "Timestamp",
            "duration_seconds": st.column_config.NumberColumn("Duration (s)", format="%.2f"),
            "records_loaded": st.column_config.NumberColumn("Records Loaded", format="%d"),
        },
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No pipeline batches logged yet.")
