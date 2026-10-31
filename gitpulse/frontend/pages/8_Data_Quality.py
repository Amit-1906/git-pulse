"""
Page 8 — Data Quality & dbt Transformations
Test suite results, schema assertions, referential integrity checks, and dbt execution control.
Provides data lineage visualization and live transformation run triggers.
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
from components.charts import create_quality_gauge
from services.api_client import api_client

st.set_page_config(
    page_title="GitPulse | Data Quality",
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
    title="Data Quality & Transformations",
    subtitle="dbt Core model assertions, schema integrity, and transformation lineage observability",
    current_repo=current_repo,
)

# ── Fetch Telemetry & Quality Results ──────────────────────────────────────
with st.spinner("Fetching transformation & quality telemetry..."):
    status = api_client.get_transformation_status()
    quality = api_client.get_quality_results()
    history = api_client.get_transformation_history(limit=20)
    lineage = api_client.get_data_lineage()

total_checks = quality.get("total_checks", 0)
passed_checks = quality.get("passed", 0)
failed_checks = quality.get("failed", 0)
pass_rate = quality.get("pass_rate_pct", 100.0)

# ── KPI Row ────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    render_metric_card("Total Assertions", str(total_checks), icon="🧪")
with c2:
    render_metric_card("Passed Checks", str(passed_checks), icon="✅")
with c3:
    render_metric_card("Violations / Failed", str(failed_checks), icon="⚠️")
with c4:
    render_metric_card("Pass Rate", f"{pass_rate:.1f}%", icon="🛡️")
with c5:
    models_cnt = status.get("total_models", 0)
    render_metric_card("dbt Models", str(models_cnt), icon="🧱")

st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

# ── Quality Gauge & Actions ────────────────────────────────────────────────
col_gauge, col_actions = st.columns([1, 1.5])
with col_gauge:
    st.plotly_chart(create_quality_gauge(pass_rate), use_container_width=True)

with col_actions:
    st.markdown("### ⚡ Transformation & Test Runner")
    st.caption("Trigger controlled dbt executions against the local PostgreSQL warehouse.")

    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("🧪 Run dbt Test Suite", use_container_width=True, type="primary"):
            with st.spinner("Executing dbt test in background..."):
                res = api_client.test_transformation()
                if res and res.get("status") == "success":
                    st.success(f"Tests passed! Output: {res.get('stdout', '')[:200]}")
                    st.rerun()
                elif res:
                    st.error(f"Test run completed with status: {res.get('status')}")
                else:
                    st.info("Test run triggered in preview mode.")
    with c_btn2:
        if st.button("🔄 Execute dbt Run", use_container_width=True):
            with st.spinner("Executing dbt run..."):
                res = api_client.run_transformation()
                if res and res.get("status") == "success":
                    st.success(f"Transformation complete! Output: {res.get('stdout', '')[:200]}")
                    st.rerun()
                elif res:
                    st.error(f"Transformation status: {res.get('status')}")
                else:
                    st.info("Transformation execution queued.")

    st.markdown(
        f"""
        <div style="background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 0.75rem; font-size: 0.8rem; margin-top: 0.75rem;">
            <div><strong>dbt Project:</strong> <span style="color: #58a6ff;">{status.get('project_name', 'gitpulse_transforms')}</span></div>
            <div><strong>Active Target:</strong> <span style="color: #f0f6fc;">{status.get('active_target', 'dev')}</span></div>
            <div><strong>Total Tests Configured:</strong> <span style="color: #3fb950;">{status.get('total_tests', 0)} tests</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── Data Lineage Architecture ──────────────────────────────────────────────
st.markdown("---")
st.markdown("### 🕸️ End-to-End Data Lineage Flow")
st.markdown(
    """
    ```mermaid
    graph LR
        GH[GitHub REST API] --> RAW[PostgreSQL Bronze JSONB<br/>raw_repositories, raw_commits, raw_prs, raw_issues]
        RAW --> STG[dbt Staging Models<br/>stg_repositories, stg_commits, stg_prs, stg_issues]
        STG --> INT[Intermediate Layer<br/>int_pull_request_lifecycle, int_issue_lifecycle, int_contributor_activity]
        INT --> MARTS[Analytical Marts & Dimensional Models<br/>dim_repositories, dim_contributors, fct_commits, fct_pull_requests, fct_issues]
        MARTS --> BI[Streamlit Executive Dashboards]

        style GH fill:#161b22,stroke:#58a6ff,stroke-width:2px,color:#f0f6fc
        style RAW fill:#161b22,stroke:#2f81f7,stroke-width:2px,color:#f0f6fc
        style STG fill:#161b22,stroke:#8b5cf6,stroke-width:2px,color:#f0f6fc
        style INT fill:#161b22,stroke:#d29922,stroke-width:2px,color:#f0f6fc
        style MARTS fill:#161b22,stroke:#3fb950,stroke-width:2px,color:#f0f6fc
        style BI fill:#161b22,stroke:#f85149,stroke-width:2px,color:#f0f6fc
    ```
    """
)

# ── Data Quality Assertions Log ────────────────────────────────────────────
st.markdown("### 📋 Test Assertions Breakdown")

results = quality.get("results", [])
if results:
    qdf = pd.DataFrame(results)
    disp_cols = [c for c in ["rule_name", "resource_type", "passed", "severity", "failure_count", "evaluated_at"] if c in qdf.columns]
    st.dataframe(
        qdf[disp_cols],
        column_config={
            "rule_name": "Test Name",
            "resource_type": "Resource",
            "passed": "Passed",
            "severity": "Severity",
            "failure_count": st.column_config.NumberColumn("Failures", format="%d"),
            "evaluated_at": "Evaluated At",
        },
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No test assertions recorded yet. Click 'Run dbt Test Suite' to execute validations.")

# ── Transformation History Log ─────────────────────────────────────────────
if history:
    st.markdown("### 🕒 Recent Transformation Runs")
    hdf = pd.DataFrame(history)
    st.dataframe(hdf, use_container_width=True, hide_index=True)
