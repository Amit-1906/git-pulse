"""
Page 6 — Issue Analytics
Track bug and feature request volume, backlog aging, resolution times, and community engagement.
Calculates resolution time strictly for closed issues using exact timestamps.
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
from components.charts import (
    create_issue_state_donut,
    create_issue_resolution_histogram,
    create_daily_activity_line,
    create_resolution_cohort_bar,
)
from services import cached_api

page_setup("Issue Analytics", icon="🐛")
render_sidebar()

# Page Header
render_page_header(
    title="Issue Analytics",
    subtitle="Backlog health, resolution cycle times, triage responsiveness, and community bug reports",
    icon="🐛",
)

# Repository Scope
current_repo = st.session_state.get("selected_repo", "All Monitored Repositories")
repos = cached_api.get_repositories()
target_repo_id = None
if current_repo != "All Monitored Repositories":
    for r in repos:
        if r.get("full_name") == current_repo:
            target_repo_id = r.get("id")
            break

# Fetch Issues with Caching
issues = cached_api.get_issues(repository_id=target_repo_id, limit=300)

if not issues:
    render_empty_state(
        "No Issues Recorded",
        "No issue data exists for this scope. Ingest issues via the sidebar or Pipeline Monitor.",
    )
else:
    df = pd.DataFrame(issues)

    if "created_at" in df.columns:
        df["created_dt"] = pd.to_datetime(df["created_at"], errors="coerce")
    if "closed_at" in df.columns:
        df["closed_dt"] = pd.to_datetime(df["closed_at"], errors="coerce")

    is_open = df["state"].str.lower() == "open"
    is_closed = df["state"].str.lower() == "closed"

    total_issues = len(df)
    open_count = int(is_open.sum())
    closed_count = int(is_closed.sum())
    closure_rate = round((closed_count / total_issues * 100), 1) if total_issues > 0 else 0.0

    # Resolution times calculated only on closed issues
    closed_df = df[is_closed].copy()
    if not closed_df.empty and "created_dt" in closed_df.columns and "closed_dt" in closed_df.columns:
        closed_df["res_days"] = (closed_df["closed_dt"] - closed_df["created_dt"]).dt.total_seconds() / 86400.0
        valid_res_days = closed_df["res_days"].dropna()
        valid_res_days = valid_res_days[valid_res_days >= 0]
        avg_res_days = valid_res_days.mean() if not valid_res_days.empty else 0.0
        median_res_days = valid_res_days.median() if not valid_res_days.empty else 0.0
    else:
        avg_res_days = 0.0
        median_res_days = 0.0
        valid_res_days = pd.Series(dtype=float)

    # Section 1: KPI Metrics
    render_section_header("Backlog Health Metrics", "Open volume, closure ratio, and resolution speed")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        render_metric_card("Total Tracked", str(total_issues), icon="🐛")
    with c2:
        render_metric_card("Open Backlog", str(open_count), icon="⚠️")
    with c3:
        render_metric_card("Resolved / Closed", str(closed_count), icon="✅")
    with c4:
        render_metric_card("Closure Ratio", f"{closure_rate}%", icon="📈")
    with c5:
        med_str = f"{median_res_days:.1f}d" if median_res_days >= 1.0 else f"{median_res_days * 24:.1f}h"
        render_metric_card("Median Resolution", med_str, icon="⏱️")

    # Section 2: Visualizations
    render_section_header("State & Resolution Distributions", "Resolution segmentation and duration frequency")
    col_donut, col_hist = st.columns([1, 1.8])
    with col_donut:
        st.plotly_chart(create_issue_state_donut(open_count, closed_count), use_container_width=True)
    with col_hist:
        if not valid_res_days.empty:
            st.plotly_chart(create_issue_resolution_histogram(list(valid_res_days)), use_container_width=True)
        else:
            render_empty_state("No Closed Issues", "Closed issues with valid timestamps required.")

    # Section 3: Creation Trends & Cohorts
    render_section_header("Inflow Velocity & Resolution Cohorts", "Issue inflow trend alongside resolution aging")
    col_trend, col_cohort = st.columns([1.8, 1])
    with col_trend:
        if "created_dt" in df.columns:
            daily_issues = df.dropna(subset=["created_dt"]).set_index("created_dt").resample("D").size()
            if not daily_issues.empty:
                dates_str = [d.strftime("%b %d") for d in daily_issues.index]
                fig_trend = create_daily_activity_line(
                    dates_str,
                    list(daily_issues.values),
                    name="Issue Inflow",
                    color="#f59e0b",
                )
                st.plotly_chart(fig_trend, use_container_width=True)
        else:
            render_empty_state("No Creation Dates", "Created timestamps not present.")

    with col_cohort:
        if not valid_res_days.empty:
            bins = [-1, 1, 7, 30, 90, 10000]
            cohort_labels = ["< 24h", "1-7 Days", "1-4 Weeks", "1-3 Mo", "> 3 Mo"]
            cohort_series = pd.cut(valid_res_days, bins=bins, labels=cohort_labels)
            cohort_counts = cohort_series.value_counts().reindex(cohort_labels).fillna(0)
            st.plotly_chart(
                create_resolution_cohort_bar(cohort_labels, list(cohort_counts.values.astype(int))),
                use_container_width=True,
            )
        else:
            render_empty_state("No Cohorts", "Resolution times required to group cohorts.")

    # Section 4: Issue Ledger
    render_section_header(f"Issue Ledger ({len(df)} records)", "Detailed record of tracked issues")
    disp_cols = [
        c
        for c in ["number", "title", "state", "user_login", "created_at", "closed_at", "comments_count"]
        if c in df.columns
    ]
    st.dataframe(
        df[disp_cols],
        column_config={
            "number": st.column_config.NumberColumn("Issue #", format="#%d"),
            "title": "Title",
            "state": "Status",
            "user_login": "Author",
            "created_at": "Opened At",
            "closed_at": "Closed At",
            "comments_count": st.column_config.NumberColumn("Comments", format="%d"),
        },
        use_container_width=True,
        hide_index=True,
    )
