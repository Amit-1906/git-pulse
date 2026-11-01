"""
GitPulse Platform Gateway & Executive Dashboard
Entry point for the GitPulse GitHub ELT & Analytics suite.
"""
from pathlib import Path
import sys
import streamlit as st
import pandas as pd

frontend_dir = Path(__file__).parent
if str(frontend_dir) not in sys.path:
    sys.path.insert(0, str(frontend_dir))

from components.ui import (
    page_setup,
    render_page_header,
    render_section_header,
    render_metric_card,
    render_status_badge,
    render_empty_state,
)
from components.sidebar import render_sidebar
from components.charts import create_activity_area_chart, create_pr_status_donut
from services import cached_api

page_setup("Executive Gateway", icon="⚡")
render_sidebar()

# Page Header
render_page_header(
    title="Executive Overview & Gateway",
    subtitle="End-to-End ELT Intelligence for GitHub Repositories",
    icon="⚡",
)

# Fetch Platform Overview Telemetry
metrics = cached_api.get_overview_metrics()
repos = cached_api.get_repositories()
pipeline_runs = cached_api.get_pipeline_runs(limit=10)
prs = cached_api.get_pull_requests(limit=150)
commits = cached_api.get_commits(limit=150)

# Section 1: Executive KPI Metrics
render_section_header("Platform Telemetry", "High-level ingestion volume & pipeline health")
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    render_metric_card("Tracked Repos", str(metrics.get("total_repositories", len(repos))), icon="📁")
with c2:
    render_metric_card("Ingested Commits", f"{metrics.get('total_commits_tracked', 0):,}", icon="🔨")
with c3:
    render_metric_card("Pull Requests", str(metrics.get("total_pull_requests", 0)), icon="🔀")
with c4:
    render_metric_card("Issues Tracked", str(metrics.get("total_issues", 0)), icon="🐛")
with c5:
    success_rate = metrics.get("pipeline_success_rate", 100.0)
    render_metric_card("ELT Success Rate", f"{success_rate:.1f}%", icon="🛡️")

# Section 2: Activity Velocity & Resolution Distribution
render_section_header("Activity Velocity & Throughput", "Ingestion velocity and PR resolution distribution")
col_vel, col_pr = st.columns([2, 1])

with col_vel:
    if commits or prs:
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
            fig = create_activity_area_chart(dates_fmt, c_vals, p_vals)
            st.plotly_chart(fig, use_container_width=True)
        else:
            render_empty_state("No Timeline Activity", "Run an extraction to populate activity velocity.")
    else:
        render_empty_state("No Activity Data", "Connect GitHub and trigger ELT sync from the sidebar.")

with col_pr:
    if prs:
        p_df2 = pd.DataFrame(prs)
        open_c = int((p_df2.get("state", pd.Series()) == "open").sum())
        merged_c = int((p_df2.get("is_merged", pd.Series()) == True).sum())
        closed_c = int(
            (
                (p_df2.get("state", pd.Series()) == "closed")
                & (~p_df2.get("is_merged", pd.Series()).fillna(False))
            ).sum()
        )
        st.plotly_chart(create_pr_status_donut(open_c, merged_c, closed_c), use_container_width=True)
    else:
        render_empty_state("No Pull Requests", "PR metrics will display once data is synchronized.")

# Section 3: Navigation Launchpad
render_section_header("Analytics Modules", "Direct access to deep-dive analytics workflows")
m1, m2, m3, m4 = st.columns(4)

with m1:
    st.markdown(
        """
        <div class="gp-panel">
            <div style="font-size: 1.3rem; margin-bottom: 0.35rem;">📁 <strong>Repositories</strong></div>
            <p style="font-size: 0.8rem; color: var(--gp-text-muted); margin-bottom: 0.75rem;">
                Explore metadata, stars, forks, and repository trends.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Open Repositories →", use_container_width=True, key="nav_repo"):
        st.switch_page("pages/2_Repositories.py")

with m2:
    st.markdown(
        """
        <div class="gp-panel">
            <div style="font-size: 1.3rem; margin-bottom: 0.35rem;">👥 <strong>Contributors</strong></div>
            <p style="font-size: 0.8rem; color: var(--gp-text-muted); margin-bottom: 0.75rem;">
                Participation cadence, author activity, and team trends.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Open Contributors →", use_container_width=True, key="nav_contrib"):
        st.switch_page("pages/3_Contributors.py")

with m3:
    st.markdown(
        """
        <div class="gp-panel">
            <div style="font-size: 1.3rem; margin-bottom: 0.35rem;">🔀 <strong>PR Analytics</strong></div>
            <p style="font-size: 0.8rem; color: var(--gp-text-muted); margin-bottom: 0.75rem;">
                Review cycle time, merge duration, and PR sizes.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Open PR Analytics →", use_container_width=True, key="nav_prs"):
        st.switch_page("pages/5_Pull_Request_Analytics.py")

with m4:
    st.markdown(
        """
        <div class="gp-panel">
            <div style="font-size: 1.3rem; margin-bottom: 0.35rem;">🧪 <strong>Data Quality</strong></div>
            <p style="font-size: 0.8rem; color: var(--gp-text-muted); margin-bottom: 0.75rem;">
                dbt transformation tests, model lineage, and assertions.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Open Data Quality →", use_container_width=True, key="nav_dq"):
        st.switch_page("pages/8_Data_Quality.py")

# Section 4: Recent Ingestion Batches
render_section_header("Recent Ingestion Batches", "Live execution status of ELT sync operations")
if pipeline_runs:
    runs_df = pd.DataFrame(pipeline_runs)
    cols = [
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
        if c in runs_df.columns
    ]
    st.dataframe(
        runs_df[cols],
        column_config={
            "id": st.column_config.NumberColumn("Run ID", format="%d"),
            "pipeline_name": "Pipeline",
            "stage": "Stage",
            "status": "Status",
            "started_at": "Timestamp",
            "duration_seconds": st.column_config.NumberColumn("Duration (s)", format="%.2f"),
            "records_loaded": st.column_config.NumberColumn("Records Ingested", format="%d"),
        },
        use_container_width=True,
        hide_index=True,
    )
else:
    render_empty_state("No Runs Recorded", "Trigger a pipeline run from the sidebar to inspect execution batches.")
