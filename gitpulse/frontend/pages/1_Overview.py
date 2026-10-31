"""
Page 1 — Overview Dashboard
Shows platform-wide KPIs, activity timeline, PR/issue distributions, and recent pipeline batches.
All data sourced from the FastAPI backend. No fabricated numbers.
"""
import sys
from pathlib import Path
import streamlit as st
import pandas as pd
from datetime import datetime

frontend_dir = Path(__file__).parent.parent
if str(frontend_dir) not in sys.path:
    sys.path.insert(0, str(frontend_dir))

from components.header import render_header
from components.sidebar import render_sidebar
from components.metrics import render_metric_card, render_status_pill
from components.charts import (
    create_activity_area_chart,
    create_pr_status_donut,
    create_issue_state_donut,
    create_contributors_leaderboard,
)
from services.api_client import api_client

st.set_page_config(
    page_title="GitPulse | Overview",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

css_path = frontend_dir / "assets" / "style.css"
if css_path.exists():
    st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

render_sidebar()

current_repo = st.session_state.get("selected_repo", "All Monitored Repositories")
render_header(
    title="Overview Dashboard",
    subtitle="Platform-wide health, ingestion volume, and activity metrics",
    current_repo=current_repo,
)

# ── Refresh control ────────────────────────────────────────────────────────
col_refresh, col_ts = st.columns([1, 5])
with col_refresh:
    refresh = st.button("🔄 Refresh", use_container_width=True)

# ── Data fetch ─────────────────────────────────────────────────────────────
with st.spinner("Loading overview metrics…"):
    metrics = api_client.get_overview_metrics()
    repos = api_client.get_repositories()
    pipeline_runs = api_client.get_pipeline_runs()
    contributors = api_client.get_contributors()
    prs = api_client.get_pull_requests()
    issues = api_client.get_issues()

with col_ts:
    st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ── KPI Row ────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    render_metric_card("Tracked Repos", str(metrics.get("total_repositories", 0)), icon="📁")
with c2:
    render_metric_card("Ingested Commits", f"{metrics.get('total_commits_tracked', 0):,}", icon="🔨")
with c3:
    render_metric_card("Pull Requests", str(metrics.get("total_pull_requests", 0)), icon="🔀")
with c4:
    render_metric_card("Open Issues", str(metrics.get("total_issues", 0)), icon="🐛")
with c5:
    render_metric_card("Contributors", str(metrics.get("total_contributors", 0)), icon="👥")
with c6:
    success_rate = metrics.get("pipeline_success_rate", 0.0)
    render_metric_card("Pipeline Success", f"{success_rate:.1f}%", icon="🛡️")

st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)

# ── Activity Timeline ──────────────────────────────────────────────────────
st.markdown("### 📈 Activity Velocity")

if prs or issues:
    # Build daily commit/PR series from real data
    pr_df = pd.DataFrame(prs) if prs else pd.DataFrame()
    issue_df = pd.DataFrame(issues) if issues else pd.DataFrame()

    def _daily_counts(df: pd.DataFrame, ts_col: str) -> pd.Series:
        if df.empty or ts_col not in df.columns:
            return pd.Series(dtype=int)
        df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")
        return df.dropna(subset=[ts_col]).set_index(ts_col).resample("D").size()

    pr_daily = _daily_counts(pr_df, "created_at")
    issue_daily = _daily_counts(issue_df, "created_at")

    combined_idx = pr_daily.index.union(issue_daily.index)
    if len(combined_idx):
        dates = [d.strftime("%b %d") for d in combined_idx]
        pr_vals = [int(pr_daily.get(d, 0)) for d in combined_idx]
        issue_vals = [int(issue_daily.get(d, 0)) for d in combined_idx]
        from components.charts import create_activity_area_chart as _act
        import plotly.graph_objects as go
        fig = _act(dates, pr_vals, issue_vals)
        fig.data[0].name = "Pull Requests"
        fig.data[1].name = "Issues"
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No time-series data yet — run an extraction to populate charts.")
else:
    st.info("No pull request or issue data yet. Connect GitHub and run an extraction.")

# ── PR + Issue Distributions ───────────────────────────────────────────────
col_pr, col_iss = st.columns(2)

with col_pr:
    st.markdown("### 🔀 PR State Distribution")
    if prs:
        pr_df2 = pd.DataFrame(prs)
        state_col = "state" if "state" in pr_df2.columns else None
        merged_col = "merged_at" if "merged_at" in pr_df2.columns else None
        if state_col:
            open_cnt = int((pr_df2[state_col] == "open").sum())
            closed_cnt = int((pr_df2[state_col] == "closed").sum())
            if merged_col:
                merged_cnt = int(pr_df2[merged_col].notna().sum())
                closed_cnt = max(0, closed_cnt - merged_cnt)
            else:
                merged_cnt = 0
            st.plotly_chart(create_pr_status_donut(open_cnt, merged_cnt, closed_cnt), use_container_width=True)
        else:
            st.info("PR state field not available.")
    else:
        st.info("No PR data available.")

with col_iss:
    st.markdown("### 🐛 Issue State Distribution")
    if issues:
        iss_df2 = pd.DataFrame(issues)
        if "state" in iss_df2.columns:
            open_iss = int((iss_df2["state"] == "open").sum())
            closed_iss = int((iss_df2["state"] == "closed").sum())
            st.plotly_chart(create_issue_state_donut(open_iss, closed_iss), use_container_width=True)
        else:
            st.info("Issue state field not available.")
    else:
        st.info("No issue data available.")

# ── Contributor Leaderboard ────────────────────────────────────────────────
st.markdown("### 👥 Contributor Activity")
if contributors:
    cdf = pd.DataFrame(contributors)
    name_col = "login" if "login" in cdf.columns else (cdf.columns[0] if len(cdf.columns) else None)
    count_col = "commits_count" if "commits_count" in cdf.columns else None
    if name_col and count_col:
        top = cdf.nlargest(10, count_col)
        st.plotly_chart(
            create_contributors_leaderboard(list(top[name_col]), list(top[count_col])),
            use_container_width=True,
        )
    else:
        st.dataframe(cdf, use_container_width=True, hide_index=True)
else:
    st.info("No contributor data yet.")

# ── Recent Pipeline Batches ────────────────────────────────────────────────
st.markdown("### ⚡ Recent ELT Pipeline Batches")
if pipeline_runs:
    run_df = pd.DataFrame(pipeline_runs)
    display_cols = [c for c in ["id", "pipeline_name", "stage", "status", "started_at", "duration_seconds", "records_loaded"] if c in run_df.columns]
    if display_cols:
        # Colour the status column via HTML
        def _fmt_row(row):
            return row

        st.dataframe(
            run_df[display_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": st.column_config.NumberColumn("Run ID", format="%d"),
                "duration_seconds": st.column_config.NumberColumn("Duration (s)", format="%.1f"),
                "records_loaded": st.column_config.NumberColumn("Records Loaded", format="%d"),
            },
        )
    else:
        st.dataframe(run_df, use_container_width=True, hide_index=True)
else:
    st.info("No pipeline runs recorded yet.")
