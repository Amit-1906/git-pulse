"""
Page 7 — Pipeline Monitor
Live observability and orchestration control for GitHub ELT extraction jobs.
Monitors GitHub API rate limits, job history, checkpoints, and provides manual triggers.
"""
from pathlib import Path
import sys
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
from components.charts import create_pipeline_latency_chart
from services import cached_api

page_setup("Pipeline Monitor", icon="⚡")
render_sidebar()

# Page Header
render_page_header(
    title="Pipeline Monitor & Orchestration",
    subtitle="Extraction job control, GitHub API rate limit tracking, and ingestion telemetry",
    icon="⚡",
)

# Fetch Telemetry with Caching
rate_info = cached_api.get_github_rate_limit() or {}
jobs = cached_api.list_extraction_history(limit=50)
repos = cached_api.get_repositories()

core_rate = rate_info.get("resources", {}).get("core", {})
rate_limit = core_rate.get("limit", 60)
rate_remaining = core_rate.get("remaining", 60)
rate_pct = round((rate_remaining / rate_limit * 100), 1) if rate_limit > 0 else 100.0

total_jobs = len(jobs)
completed_jobs = sum(1 for j in jobs if str(j.get("status", "")).lower() in ("completed", "success"))
success_rate = round(completed_jobs / total_jobs * 100, 1) if total_jobs > 0 else 100.0
total_extracted = sum(j.get("records_extracted", 0) or 0 for j in jobs)

# Section 1: Rate Limits & Telemetry
render_section_header("API Quota & Extraction Velocity", "Real-time rate-limit budget and historical extraction yields")
c1, c2, c3, c4 = st.columns(4)
with c1:
    render_metric_card("GitHub API Quota", f"{rate_remaining:,} / {rate_limit:,}", delta=f"{rate_pct}% remaining", icon="🌐")
with c2:
    render_metric_card("Extraction Runs", str(total_jobs), icon="⚡")
with c3:
    render_metric_card("Job Success Rate", f"{success_rate}%", icon="🛡️")
with c4:
    render_metric_card("Total Ingested Records", f"{total_extracted:,}", icon="📦")

# Section 2: On-Demand Extraction Dispatcher
render_section_header("Trigger Extraction Job", "Configure and dispatch extraction jobs to the background engine")
with st.container():
    st.markdown(
        """
        <div class="gp-panel">
            <div style="font-weight: 600; color: var(--gp-text-main); margin-bottom: 0.5rem;">Pipeline Extraction Parameters</div>
            <p style="font-size: 0.8rem; color: var(--gp-text-secondary); margin-bottom: 1rem;">
                Select target repository and resources to pull from the GitHub REST API.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    repo_names = [r["full_name"] for r in repos] if repos else ["tiangolo/fastapi"]
    selected_target = st.selectbox("Select Target Repository", options=repo_names)

    c_r1, c_r2, c_r3, c_r4 = st.columns(4)
    with c_r1:
        ext_repo = st.checkbox("Repository Metadata", value=True)
    with c_r2:
        ext_commits = st.checkbox("Commits", value=True)
    with c_r3:
        ext_prs = st.checkbox("Pull Requests", value=True)
    with c_r4:
        ext_issues = st.checkbox("Issues", value=True)

    c_inc, c_btn = st.columns([2, 1])
    with c_inc:
        incremental_mode = st.toggle("Incremental Extraction (use checkpoints)", value=True)

    with c_btn:
        if st.button("⚡ Dispatch Job", type="primary", use_container_width=True):
            resources = []
            if ext_repo:
                resources.append("repository")
            if ext_commits:
                resources.append("commits")
            if ext_prs:
                resources.append("pull_requests")
            if ext_issues:
                resources.append("issues")

            with st.spinner("Submitting extraction job to engine..."):
                res = cached_api.start_extraction(
                    repository_full_name=selected_target,
                    resources=resources,
                    incremental=incremental_mode,
                    run_sync=False,
                )
                if res and "job_id" in res:
                    st.success(f"Extraction job `{res['job_id']}` submitted successfully!")
                    st.rerun()
                elif res:
                    st.success("Extraction job accepted!")
                    st.rerun()
                else:
                    st.info("Extraction queued.")

# Section 3: Latency Trend
render_section_header("Pipeline Execution Latency", "Duration curve across the most recent extraction jobs")
if jobs:
    valid_durations = [j for j in jobs if j.get("duration_seconds") is not None]
    if valid_durations:
        durations = [float(j["duration_seconds"]) for j in valid_durations[-15:]]
        run_labels = [f"Job #{j.get('id', idx)}" for idx, j in enumerate(valid_durations[-15:])]
        st.plotly_chart(
            create_pipeline_latency_chart(run_labels, durations),
            use_container_width=True,
        )
    else:
        render_empty_state("No Latency Metrics", "Completed jobs will display duration curves.")
else:
    render_empty_state("No Job Records", "Trigger an extraction job to view latency metrics.")

# Section 4: History Log Table
render_section_header(f"Extraction Job Log ({len(jobs)} runs)", "Complete ledger of ingestion jobs and error diagnostics")
if jobs:
    jdf = pd.DataFrame(jobs)
    cols = [
        c
        for c in [
            "id",
            "job_id",
            "repository_full_name",
            "stage",
            "status",
            "started_at",
            "duration_seconds",
            "records_extracted",
            "records_loaded",
            "error_message",
        ]
        if c in jdf.columns
    ]
    st.dataframe(
        jdf[cols],
        column_config={
            "id": st.column_config.NumberColumn("ID", format="%d"),
            "repository_full_name": "Repository",
            "stage": "Stage",
            "status": "Status",
            "started_at": "Timestamp",
            "duration_seconds": st.column_config.NumberColumn("Duration (s)", format="%.2f"),
            "records_extracted": st.column_config.NumberColumn("Extracted", format="%d"),
            "records_loaded": st.column_config.NumberColumn("Loaded", format="%d"),
            "error_message": "Error Message",
        },
        use_container_width=True,
        hide_index=True,
    )
else:
    render_empty_state("No Extraction Runs", "Trigger an extraction above to populate the job ledger.")
