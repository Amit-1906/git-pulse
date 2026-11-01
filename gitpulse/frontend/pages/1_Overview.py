"""
Page 1 — Overview Dashboard
Platform-wide health, ingestion volume, and activity metrics.
"""
from pathlib import Path
import sys
from datetime import datetime
import streamlit as st
import pandas as pd

frontend_dir = Path(__file__).parent.parent
if str(frontend_dir) not in sys.path:
    sys.path.insert(0, str(frontend_dir))

from components.ui import (
    page_setup,
    render_page_header,
    render_section_header,
    render_metric_card,
    render_empty_state,
)
from components.sidebar import render_sidebar
from components.charts import (
    create_activity_area_chart,
    create_pr_status_donut,
    create_issue_state_donut,
    create_contributors_leaderboard,
)
from services import cached_api

page_setup("Overview Dashboard", icon="⚡")
render_sidebar()

# Page Header
render_page_header(
    title="Overview Dashboard",
    subtitle="Enterprise ingestion telemetry, pipeline throughput, and operational metrics",
    icon="⚡",
)

# Fetch Telemetry with Caching
metrics = cached_api.get_overview_metrics()
pipeline_runs = cached_api.get_pipeline_runs(limit=10)
contributors = cached_api.get_contributors()
prs = cached_api.get_pull_requests(limit=300)
issues = cached_api.get_issues(limit=300)

# Section 1: Key Performance Indicators
render_section_header("Executive Telemetry", "Cross-repository volume and platform health")
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
    success_rate = metrics.get("pipeline_success_rate", 100.0)
    render_metric_card("Pipeline Success", f"{success_rate:.1f}%", icon="🛡️")

# Section 2: Activity Velocity
render_section_header("Activity Velocity", "PR and Issue ingestion volume over time")
if prs or issues:
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
        fig = create_activity_area_chart(dates, pr_vals, issue_vals)
        fig.data[0].name = "Pull Requests"
        fig.data[1].name = "Issues"
        st.plotly_chart(fig, use_container_width=True)
    else:
        render_empty_state("No Activity Data", "Run an extraction to populate timeline activity.")
else:
    render_empty_state("No Activity Records", "Connect GitHub and trigger ELT sync to view metrics.")

# Section 3: State Distributions & Contributor Rankings
render_section_header("Lifecycle & Engineering Participation", "PR & Issue state segmentation alongside top committers")
col_pr, col_iss, col_contrib = st.columns([1, 1, 1.4])

with col_pr:
    st.markdown("<h5 style='color: var(--gp-text-main); font-size: 0.95rem; margin-bottom: 0.5rem;'>Pull Request States</h5>", unsafe_allow_html=True)
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
            render_empty_state("No State Data", "PR state field unavailable.")
    else:
        render_empty_state("No Pull Requests", "PR data will appear after synchronization.")

with col_iss:
    st.markdown("<h5 style='color: var(--gp-text-main); font-size: 0.95rem; margin-bottom: 0.5rem;'>Issue Backlog Status</h5>", unsafe_allow_html=True)
    if issues:
        iss_df2 = pd.DataFrame(issues)
        if "state" in iss_df2.columns:
            open_iss = int((iss_df2["state"] == "open").sum())
            closed_iss = int((iss_df2["state"] == "closed").sum())
            st.plotly_chart(create_issue_state_donut(open_iss, closed_iss), use_container_width=True)
        else:
            render_empty_state("No Issue Data", "Issue state field unavailable.")
    else:
        render_empty_state("No Issues", "Issue metrics will appear after synchronization.")

with col_contrib:
    st.markdown("<h5 style='color: var(--gp-text-main); font-size: 0.95rem; margin-bottom: 0.5rem;'>Top Contributor Volume</h5>", unsafe_allow_html=True)
    if contributors:
        cdf = pd.DataFrame(contributors)
        name_col = "login" if "login" in cdf.columns else (cdf.columns[0] if len(cdf.columns) else None)
        count_col = "commits_count" if "commits_count" in cdf.columns else None
        if name_col and count_col:
            top = cdf.nlargest(6, count_col)
            st.plotly_chart(
                create_contributors_leaderboard(list(top[name_col]), list(top[count_col])),
                use_container_width=True,
            )
        else:
            render_empty_state("No Contributors", "Contributor breakdown unavailable.")
    else:
        render_empty_state("No Contributors", "Ingest commits to identify contributors.")

# Section 4: Recent Ingestion Batches
render_section_header("ELT Ingestion Batches", "Recent pipeline runs logged in the operational database")
if pipeline_runs:
    run_df = pd.DataFrame(pipeline_runs)
    display_cols = [
        c
        for c in [
            "id",
            "pipeline_name",
            "stage",
            "status",
            "started_at",
            "duration_seconds",
            "records_loaded",
        ]
        if c in run_df.columns
    ]
    st.dataframe(
        run_df[display_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "id": st.column_config.NumberColumn("Run ID", format="%d"),
            "pipeline_name": "Pipeline",
            "stage": "Stage",
            "status": "Status",
            "started_at": "Timestamp",
            "duration_seconds": st.column_config.NumberColumn("Duration (s)", format="%.2f"),
            "records_loaded": st.column_config.NumberColumn("Records Loaded", format="%d"),
        },
    )
else:
    render_empty_state("No Pipeline Runs", "Trigger a pipeline run from the sidebar to inspect execution history.")
