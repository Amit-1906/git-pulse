"""
Page 8 — Data Quality & dbt Transformations
Test suite results, schema assertions, referential integrity checks, and dbt execution control.
Provides data lineage visualization and live transformation run triggers.
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
    render_status_badge,
    render_empty_state,
)
from components.sidebar import render_sidebar
from components.charts import create_quality_gauge
from services import cached_api

page_setup("Data Quality", icon="🧪")
render_sidebar()

# Page Header
render_page_header(
    title="Data Quality & Transformations",
    subtitle="dbt Core model assertions, schema integrity, and transformation lineage observability",
    icon="🧪",
)

# Fetch Telemetry with Caching
status = cached_api.get_transformation_status()
quality = cached_api.get_quality_results()
history = cached_api.get_transformation_history(limit=20)

total_checks = quality.get("total_checks", 0)
passed_checks = quality.get("passed", 0)
failed_checks = quality.get("failed", 0)
pass_rate = quality.get("pass_rate_pct", 100.0)
models_cnt = status.get("total_models", 15)

# Section 1: KPI Metrics
render_section_header("Transformation Quality Metrics", "Model health, test pass rates, and schema integrity")
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
    render_metric_card("dbt Models", str(models_cnt), icon="🧱")

# Section 2: Gauge & Test Controls
render_section_header("Execution & Assertion Engine", "Trigger dbt Core operations against the analytical warehouse")
col_gauge, col_actions = st.columns([1, 1.6])

with col_gauge:
    st.plotly_chart(create_quality_gauge(pass_rate), use_container_width=True)

with col_actions:
    st.markdown(
        f"""
        <div class="gp-panel" style="margin-bottom: 0.75rem;">
            <div style="font-weight: 600; color: var(--gp-text-main); margin-bottom: 0.25rem;">dbt Environment Configuration</div>
            <div style="display: flex; gap: 1.5rem; font-size: 0.825rem; color: var(--gp-text-secondary); margin-top: 0.4rem;">
                <div>Project: <strong style="color: var(--gp-blue-hover);">{status.get('project_name', 'gitpulse_transforms')}</strong></div>
                <div>Target: <strong style="color: var(--gp-text-main);">{status.get('active_target', 'dev')}</strong></div>
                <div>Configured Tests: <strong style="color: var(--gp-emerald-text);">{status.get('total_tests', 62)}</strong></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("🧪 Run dbt Test Suite", use_container_width=True, type="primary"):
            with st.spinner("Executing dbt test in warehouse..."):
                res = cached_api.test_transformation()
                if res and res.get("status") == "success":
                    st.success("Test assertions passed successfully!")
                    st.rerun()
                elif res:
                    st.error(f"Test suite finished with status: {res.get('status')}")
                else:
                    st.info("Test execution dispatched.")
    with c_btn2:
        if st.button("🔄 Execute dbt Run", use_container_width=True):
            with st.spinner("Executing dbt transformations..."):
                res = cached_api.run_transformation()
                if res and res.get("status") == "success":
                    st.success("Transformation models built successfully!")
                    st.rerun()
                elif res:
                    st.error(f"Transformation status: {res.get('status')}")
                else:
                    st.info("Transformation execution dispatched.")

# Section 3: Data Lineage Flow Architecture
render_section_header("Data Lineage Architecture", "Bronze JSONB payloads to gold dimensional marts")
st.markdown(
    """
    <div style="display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1rem;">
        <div class="gp-panel" style="flex: 1; min-width: 150px; text-align: center; border-top: 3px solid #3b82f6;">
            <div style="font-size: 1.1rem; margin-bottom: 0.25rem;">🌐 <strong>GitHub API</strong></div>
            <div style="font-size: 0.75rem; color: var(--gp-text-muted);">REST Endpoints</div>
        </div>
        <div style="color: var(--gp-text-muted); font-size: 1.2rem;">➔</div>
        <div class="gp-panel" style="flex: 1; min-width: 150px; text-align: center; border-top: 3px solid #f59e0b;">
            <div style="font-size: 1.1rem; margin-bottom: 0.25rem;">🥉 <strong>Bronze Tier</strong></div>
            <div style="font-size: 0.75rem; color: var(--gp-text-muted);">raw_* (JSONB)</div>
        </div>
        <div style="color: var(--gp-text-muted); font-size: 1.2rem;">➔</div>
        <div class="gp-panel" style="flex: 1; min-width: 150px; text-align: center; border-top: 3px solid #8b5cf6;">
            <div style="font-size: 1.1rem; margin-bottom: 0.25rem;">🥈 <strong>Silver Staging</strong></div>
            <div style="font-size: 0.75rem; color: var(--gp-text-muted);">stg_* models</div>
        </div>
        <div style="color: var(--gp-text-muted); font-size: 1.2rem;">➔</div>
        <div class="gp-panel" style="flex: 1; min-width: 150px; text-align: center; border-top: 3px solid #14b8a6;">
            <div style="font-size: 1.1rem; margin-bottom: 0.25rem;">⚡ <strong>Intermediate</strong></div>
            <div style="font-size: 0.75rem; color: var(--gp-text-muted);">int_* lifecycles</div>
        </div>
        <div style="color: var(--gp-text-muted); font-size: 1.2rem;">➔</div>
        <div class="gp-panel" style="flex: 1; min-width: 150px; text-align: center; border-top: 3px solid #10b981;">
            <div style="font-size: 1.1rem; margin-bottom: 0.25rem;">🥇 <strong>Gold Marts</strong></div>
            <div style="font-size: 0.75rem; color: var(--gp-text-muted);">dim_* & fct_*</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Section 4: Test Assertions Ledger
render_section_header("Data Quality Assertions", "Individual test validation outcomes")
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
    render_empty_state("No Test Assertions", "Click 'Run dbt Test Suite' to execute model validations.")

# Section 5: Transformation History
if history:
    render_section_header("Recent Transformation Runs", "Chronological audit of dbt build operations")
    hdf = pd.DataFrame(history)
    st.dataframe(hdf, use_container_width=True, hide_index=True)
