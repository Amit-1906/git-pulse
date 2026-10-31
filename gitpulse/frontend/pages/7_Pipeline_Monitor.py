"""
Page 7 — Pipeline Monitor
Live observability and orchestration control for GitHub ELT extraction jobs.
Monitors GitHub API rate limits, job history, checkpoints, and provides manual triggers.
"""
import sys
from pathlib import Path
from datetime import datetime
import streamlit as st
import pandas as pd

frontend_dir = Path(__file__).parent.parent
if str(frontend_dir) not in sys.path:
    sys.path.insert(0, str(frontend_dir))

from components.header import render_header
from components.sidebar import render_sidebar
from components.metrics import render_metric_card, render_status_pill
from components.charts import create_pipeline_latency_chart
from services.api_client import api_client

st.set_page_config(
    page_title="GitPulse | Pipeline Monitor",
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
    title="Pipeline Monitor",
    subtitle="Extraction job orchestration, GitHub API rate limit tracking, and ingestion telemetry",
    current_repo=current_repo,
)

# ── GitHub Rate Limit & Telemetry ──────────────────────────────────────────
with st.spinner("Fetching pipeline telemetry & rate limits..."):
    rate_info = api_client.get_github_rate_limit() or {}
    jobs = api_client.list_extraction_history(limit=50)
    repos = api_client.get_repositories()

core_rate = rate_info.get("resources", {}).get("core", {})
rate_limit = core_rate.get("limit", 60)
rate_remaining = core_rate.get("remaining", 60)
rate_used = core_rate.get("used", 0)
rate_pct = round((rate_remaining / rate_limit * 100), 1) if rate_limit > 0 else 100.0

c1, c2, c3, c4 = st.columns(4)
with c1:
    render_metric_card("GitHub API Quota", f"{rate_remaining:,} / {rate_limit:,}", delta=f"{rate_pct}% free", icon="🌐")
with c2:
    total_jobs = len(jobs)
    render_metric_card("Total Jobs Logged", str(total_jobs), icon="⚡")
with c3:
    completed_jobs = sum(1 for j in jobs if str(j.get("status", "")).lower() in ("completed", "success"))
    success_rate = round(completed_jobs / total_jobs * 100, 1) if total_jobs > 0 else 100.0
    render_metric_card("Job Success Rate", f"{success_rate}%", icon="🛡️")
with c4:
    total_extracted = sum(j.get("records_extracted", 0) or 0 for j in jobs)
    render_metric_card("Total Records Ingested", f"{total_extracted:,}", icon="📦")

st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

# ── Trigger New Extraction ─────────────────────────────────────────────────
with st.expander("🚀 Trigger On-Demand GitHub Extraction", expanded=False):
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
        if st.button("⚡ Start Extraction", type="primary", use_container_width=True):
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
                res = api_client.start_extraction(
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
                    st.info("Extraction queued (standalone preview mode).")

# ── Pipeline Duration Trend ────────────────────────────────────────────────
if jobs:
    valid_durations = [j for j in jobs if j.get("duration_seconds") is not None]
    if valid_durations:
        durations = [float(j["duration_seconds"]) for j in valid_durations[-15:]]
        run_labels = [f"Job #{j.get('id', idx)}" for idx, j in enumerate(valid_durations[-15:])]
        st.plotly_chart(
            create_pipeline_latency_chart(run_labels, durations),
            use_container_width=True,
        )

# ── Job History Log ────────────────────────────────────────────────────────
st.markdown("### 📋 Extraction Job History")

col_ref, col_space = st.columns([1, 5])
with col_ref:
    if st.button("🔄 Refresh History", use_container_width=True):
        st.rerun()

if jobs:
    jdf = pd.DataFrame(jobs)
    cols = [
        c for c in [
            "id", "job_id", "repository_full_name", "pipeline_name", "stage", "status",
            "started_at", "duration_seconds", "records_extracted", "records_loaded", "error_message"
        ]
        if c in jdf.columns
    ]
    st.dataframe(
        jdf[cols],
        column_config={
            "id": st.column_config.NumberColumn("ID", format="%d"),
            "duration_seconds": st.column_config.NumberColumn("Duration (s)", format="%.2f"),
            "records_extracted": st.column_config.NumberColumn("Extracted", format="%d"),
            "records_loaded": st.column_config.NumberColumn("Loaded", format="%d"),
        },
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No extraction jobs recorded yet. Trigger an extraction above to start ingesting data.")
