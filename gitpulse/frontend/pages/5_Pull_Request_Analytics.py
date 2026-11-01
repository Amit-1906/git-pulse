"""
Page 5 — Pull Request Analytics
Evaluate code review throughput, merge cycle times, and PR lifecycle distributions.
Clearly distinguishes between merged and unmerged pull requests, and computes durations from real timestamps.
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
    create_pr_status_donut,
    create_merge_time_histogram,
    create_daily_activity_line,
    create_pr_size_distribution,
)
from services import cached_api

page_setup("Pull Request Analytics", icon="🔀")
render_sidebar()

# Page Header
render_page_header(
    title="Pull Request Analytics",
    subtitle="Code review efficiency, cycle times to merge, and branch lifecycle velocity",
    icon="🔀",
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

# Fetch PRs with Caching
prs = cached_api.get_pull_requests(repository_id=target_repo_id, limit=300)

if not prs:
    render_empty_state(
        "No Pull Requests Found",
        "No PR records exist for this scope. Ingest pull requests via the sidebar or Pipeline Monitor.",
    )
else:
    df = pd.DataFrame(prs)

    if "created_at" in df.columns:
        df["created_dt"] = pd.to_datetime(df["created_at"], errors="coerce")
    if "merged_at" in df.columns:
        df["merged_dt"] = pd.to_datetime(df["merged_at"], errors="coerce")
    if "closed_at" in df.columns:
        df["closed_dt"] = pd.to_datetime(df["closed_at"], errors="coerce")

    is_merged_mask = df["is_merged"].fillna(False) | (
        df["merged_dt"].notna() if "merged_dt" in df.columns else False
    )
    is_open_mask = df["state"].str.lower() == "open"
    is_closed_unmerged_mask = (df["state"].str.lower() == "closed") & (~is_merged_mask)

    total_prs = len(df)
    open_count = int(is_open_mask.sum())
    merged_count = int(is_merged_mask.sum())
    closed_unmerged_count = int(is_closed_unmerged_mask.sum())

    # Merge Cycle Hours Calculation
    merged_prs = df[is_merged_mask].copy()
    if not merged_prs.empty and "merged_dt" in merged_prs.columns and "created_dt" in merged_prs.columns:
        merged_prs["cycle_hours"] = (
            merged_prs["merged_dt"] - merged_prs["created_dt"]
        ).dt.total_seconds() / 3600.0
        valid_cycle_hours = merged_prs["cycle_hours"].dropna()
        valid_cycle_hours = valid_cycle_hours[valid_cycle_hours >= 0]
        avg_cycle_hours = valid_cycle_hours.mean() if not valid_cycle_hours.empty else 0.0
        median_cycle_hours = valid_cycle_hours.median() if not valid_cycle_hours.empty else 0.0
    else:
        avg_cycle_hours = 0.0
        median_cycle_hours = 0.0
        valid_cycle_hours = pd.Series(dtype=float)

    # Section 1: KPI Metrics
    render_section_header("Lifecycle Throughput", "Review velocity, merge volumes, and duration metrics")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        render_metric_card("Total PRs", str(total_prs), icon="🔀")
    with c2:
        render_metric_card("Open Reviews", str(open_count), icon="🔵")
    with c3:
        render_metric_card("Merged Branches", str(merged_count), icon="🟣")
    with c4:
        render_metric_card("Closed Unmerged", str(closed_unmerged_count), icon="⚪")
    with c5:
        med_str = f"{median_cycle_hours:.1f}h" if median_cycle_hours < 72 else f"{median_cycle_hours / 24:.1f}d"
        render_metric_card("Median Merge Time", med_str, icon="⏱️")

    # Section 2: Visualizations
    render_section_header("State & Merge-Time Distributions", "Resolution segmentation and duration frequency")
    col_donut, col_hist = st.columns([1, 1.8])
    with col_donut:
        st.plotly_chart(
            create_pr_status_donut(open_count, merged_count, closed_unmerged_count),
            use_container_width=True,
        )
    with col_hist:
        if not valid_cycle_hours.empty:
            st.plotly_chart(
                create_merge_time_histogram(list(valid_cycle_hours)),
                use_container_width=True,
            )
        else:
            render_empty_state("No Merge Durations", "Merged pull requests with valid timestamps required.")

    # Section 3: Creation Trends & Size Breakdown
    render_section_header("Inflow Velocity & Size Profiles", "Creation trend alongside code-change complexity")
    col_trend, col_size = st.columns([1.8, 1])
    with col_trend:
        if "created_dt" in df.columns:
            daily_prs = df.dropna(subset=["created_dt"]).set_index("created_dt").resample("D").size()
            if not daily_prs.empty:
                dates_str = [d.strftime("%b %d") for d in daily_prs.index]
                fig_trend = create_daily_activity_line(
                    dates_str,
                    list(daily_prs.values),
                    name="PR Creation Trend",
                    color="#8b5cf6",
                )
                st.plotly_chart(fig_trend, use_container_width=True)
        else:
            render_empty_state("No Creation Dates", "Created timestamps not present.")

    with col_size:
        if "additions" in df.columns and "deletions" in df.columns:
            df["lines_changed"] = df["additions"].fillna(0) + df["deletions"].fillna(0)
            bins = [-1, 20, 100, 500, 1000000]
            labels = ["XS (<20)", "S (20-100)", "M (100-500)", "L (>500)"]
            df["size_cat"] = pd.cut(df["lines_changed"], bins=bins, labels=labels)
            size_counts = df["size_cat"].value_counts().reindex(labels).fillna(0)
            st.plotly_chart(
                create_pr_size_distribution(labels, list(size_counts.values.astype(int))),
                use_container_width=True,
            )
        else:
            render_empty_state("No Line Counts", "Addition/deletion columns not present.")

    # Section 4: PR Ledger
    render_section_header(f"Pull Request Ledger ({len(df)} records)", "Detailed record of pull requests")
    disp_cols = [
        c
        for c in ["number", "title", "state", "is_merged", "user_login", "created_at", "merged_at", "comments_count"]
        if c in df.columns
    ]
    st.dataframe(
        df[disp_cols],
        column_config={
            "number": st.column_config.NumberColumn("PR #", format="#%d"),
            "title": "Title",
            "state": "Status",
            "is_merged": "Merged",
            "user_login": "Author",
            "created_at": "Created",
            "merged_at": "Merged",
            "comments_count": st.column_config.NumberColumn("Comments", format="%d"),
        },
        use_container_width=True,
        hide_index=True,
    )
