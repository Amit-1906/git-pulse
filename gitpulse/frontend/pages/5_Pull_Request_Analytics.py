"""
Page 5 — Pull Request Analytics
Evaluate code review throughput, merge cycle times, and PR lifecycle distributions.
Clearly distinguishes between merged and unmerged pull requests, and computes durations from real timestamps.
"""
import sys
from pathlib import Path
from datetime import datetime
import streamlit as st
import pandas as pd
import numpy as np

frontend_dir = Path(__file__).parent.parent
if str(frontend_dir) not in sys.path:
    sys.path.insert(0, str(frontend_dir))

from components.header import render_header
from components.sidebar import render_sidebar
from components.metrics import render_metric_card, render_status_pill
from components.charts import (
    create_pr_status_donut,
    create_merge_time_histogram,
    create_daily_activity_line,
    create_pr_size_distribution,
)
from services.api_client import api_client

st.set_page_config(
    page_title="GitPulse | Pull Request Analytics",
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
    title="Pull Request Analytics",
    subtitle="Code review efficiency, cycle times to merge, and branch lifecycle velocity",
    current_repo=current_repo,
)

# ── Load Repositories for Filtering ────────────────────────────────────────
repos = api_client.get_repositories()
target_repo_id = None
if current_repo != "All Monitored Repositories":
    for r in repos:
        if r.get("full_name") == current_repo:
            target_repo_id = r.get("id")
            break

# ── Fetch Data ─────────────────────────────────────────────────────────────
with st.spinner("Fetching pull requests from backend..."):
    prs = api_client.get_pull_requests(repository_id=target_repo_id, limit=300)

if not prs:
    st.info("No pull requests recorded yet. Trigger an ELT extraction for pull requests to populate this dashboard.")
else:
    df = pd.DataFrame(prs)

    # Clean & normalize timestamps
    if "created_at" in df.columns:
        df["created_dt"] = pd.to_datetime(df["created_at"], errors="coerce")
    if "merged_at" in df.columns:
        df["merged_dt"] = pd.to_datetime(df["merged_at"], errors="coerce")
    if "closed_at" in df.columns:
        df["closed_dt"] = pd.to_datetime(df["closed_at"], errors="coerce")

    # Accurate state segmentation
    is_merged_mask = df["is_merged"].fillna(False) | (df["merged_dt"].notna() if "merged_dt" in df.columns else False)
    is_open_mask = df["state"].str.lower() == "open"
    is_closed_unmerged_mask = (df["state"].str.lower() == "closed") & (~is_merged_mask)

    total_prs = len(df)
    open_count = int(is_open_mask.sum())
    merged_count = int(is_merged_mask.sum())
    closed_unmerged_count = int(is_closed_unmerged_mask.sum())

    # Cycle time calculations: only for MERGED PRs, based on actual timestamps
    merged_prs = df[is_merged_mask].copy()
    if not merged_prs.empty and "merged_dt" in merged_prs.columns and "created_dt" in merged_prs.columns:
        merged_prs["cycle_hours"] = (
            merged_prs["merged_dt"] - merged_prs["created_dt"]
        ).dt.total_seconds() / 3600.0
        # Filter negative or invalid cycle times
        valid_cycle_hours = merged_prs["cycle_hours"].dropna()
        valid_cycle_hours = valid_cycle_hours[valid_cycle_hours >= 0]
        avg_cycle_hours = valid_cycle_hours.mean() if not valid_cycle_hours.empty else 0.0
        median_cycle_hours = valid_cycle_hours.median() if not valid_cycle_hours.empty else 0.0
    else:
        avg_cycle_hours = 0.0
        median_cycle_hours = 0.0
        valid_cycle_hours = pd.Series(dtype=float)

    # ── KPI Cards ──────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        render_metric_card("Total PRs", str(total_prs), icon="🔀")
    with c2:
        render_metric_card("Open", str(open_count), icon="🔵")
    with c3:
        render_metric_card("Merged", str(merged_count), icon="🟣")
    with c4:
        render_metric_card("Closed (Unmerged)", str(closed_unmerged_count), icon="⚪")
    with c5:
        med_str = f"{median_cycle_hours:.1f}h" if median_cycle_hours < 72 else f"{median_cycle_hours / 24:.1f}d"
        render_metric_card("Median Merge Time", med_str, icon="⏱️")

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    # ── Visualizations Row ─────────────────────────────────────────────────
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
            st.info("No merged PRs with valid timestamps to compute merge-time histogram.")

    # ── PR Creation Trends & Size Breakdown ────────────────────────────────
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
            st.info("Creation timestamp trend not available.")

    with col_size:
        # Categorize PR size by lines changed
        if "additions" in df.columns and "deletions" in df.columns:
            df["lines_changed"] = df["additions"].fillna(0) + df["deletions"].fillna(0)
            bins = [-1, 20, 100, 500, 1000000]
            labels = ["XS (<20 lines)", "S (20-100)", "M (100-500)", "L (>500 lines)"]
            df["size_cat"] = pd.cut(df["lines_changed"], bins=bins, labels=labels)
            size_counts = df["size_cat"].value_counts().reindex(labels).fillna(0)
            st.plotly_chart(
                create_pr_size_distribution(labels, list(size_counts.values.astype(int))),
                use_container_width=True,
            )
        else:
            st.info("Line addition/deletion metrics not available for size breakdown.")

    # ── PR Data Table ──────────────────────────────────────────────────────
    st.markdown("### 📋 Pull Request Directory")
    disp_cols = [
        c for c in ["number", "title", "state", "is_merged", "user_login", "created_at", "merged_at", "comments_count"]
        if c in df.columns
    ]
    st.dataframe(
        df[disp_cols],
        column_config={
            "number": st.column_config.NumberColumn("PR #", format="#%d"),
            "title": "Title",
            "state": "Status",
            "is_merged": "Merged?",
            "user_login": "Author",
            "created_at": "Created",
            "merged_at": "Merged",
            "comments_count": st.column_config.NumberColumn("Comments", format="%d"),
        },
        use_container_width=True,
        hide_index=True,
    )
