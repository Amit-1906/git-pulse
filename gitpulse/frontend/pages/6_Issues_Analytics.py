"""
Page 6 — Issue Analytics
Track bug and feature request volume, backlog aging, resolution times, repository distribution,
and community engagement. Calculates resolution time strictly for closed issues using exact timestamps.
"""
from pathlib import Path
import sys
from datetime import datetime, timedelta
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
    create_resolution_cohort_bar,
    create_repository_issue_distribution_chart,
    create_issue_label_distribution_chart,
    create_issue_velocity_chart,
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

# ── 1. REPOSITORY & DATA RETRIEVAL ──────────────────────────────────────────
repos = cached_api.get_repositories()
repo_names = [r.get("full_name") for r in repos if r.get("full_name")]

# Sidebar session state or local selector
session_repo = st.session_state.get("selected_repo", "All Monitored Repositories")
default_repo_idx = 0
if session_repo in repo_names:
    default_repo_idx = repo_names.index(session_repo) + 1

# Fetch complete issues dataset
issues = cached_api.get_issues(limit=500)

if not issues:
    render_empty_state(
        "No Issues Recorded",
        "No issue data exists in the database. Trigger extraction via Pipeline Monitor or Settings.",
    )
    st.stop()

df = pd.DataFrame(issues)

# Ensure datetime parse
if "created_at" in df.columns:
    df["created_dt"] = pd.to_datetime(df["created_at"], errors="coerce")
if "closed_at" in df.columns:
    df["closed_dt"] = pd.to_datetime(df["closed_at"], errors="coerce")

# Fill repository_name if missing
if "repository_name" not in df.columns and "repository_full_name" in df.columns:
    df["repository_name"] = df["repository_full_name"]
elif "repository_name" not in df.columns:
    repo_lookup = {r.get("id"): r.get("full_name") for r in repos}
    df["repository_name"] = df["repository_id"].map(repo_lookup).fillna("Unknown Repository")

# ── 2. INTERACTIVE CONTROLS & FILTERS ─────────────────────────────────────────
render_section_header("Interactive Filters & Search", "Filter by repository, issue status, label category, date range, or keywords")

fc1, fc2, fc3, fc4 = st.columns([1.6, 1.2, 1.2, 1.2])

with fc1:
    selected_repo = st.selectbox(
        "Repository Scope",
        ["All Monitored Repositories"] + repo_names,
        index=default_repo_idx if default_repo_idx < len(repo_names) + 1 else 0,
        help="Filter metrics and charts by repository",
    )

with fc2:
    status_filter = st.selectbox(
        "Issue State",
        ["All Statuses", "Open Backlog", "Closed / Resolved"],
        index=0,
    )

with fc3:
    # Extract unique label tags across all issues
    all_labels = set()
    for raw_l in df.get("labels", []):
        if isinstance(raw_l, list):
            for item in raw_l:
                if isinstance(item, str) and item.strip():
                    all_labels.add(item.strip())
        elif isinstance(raw_l, str) and raw_l.strip():
            all_labels.add(raw_l.strip())
    sorted_labels = sorted(list(all_labels))
    label_filter = st.selectbox(
        "Label Category",
        ["All Labels"] + sorted_labels,
        index=0,
    )

with fc4:
    date_filter = st.selectbox(
        "Date Horizon",
        ["All Time", "Last 14 Days", "Last 30 Days", "Last 60 Days", "Last 90 Days"],
        index=0,
    )

# Search Bar
search_query = st.text_input(
    "Search Issues",
    placeholder="Search by issue number (#123), title, author, or keywords...",
)

# ── APPLY FILTER PIPELINE ─────────────────────────────────────────────────────
filtered_df = df.copy()

if selected_repo != "All Monitored Repositories":
    filtered_df = filtered_df[filtered_df["repository_name"] == selected_repo]

if status_filter == "Open Backlog":
    filtered_df = filtered_df[filtered_df["state"].str.lower() == "open"]
elif status_filter == "Closed / Resolved":
    filtered_df = filtered_df[filtered_df["state"].str.lower() == "closed"]

if label_filter != "All Labels":
    def match_label(item_labels):
        if isinstance(item_labels, list):
            return label_filter in item_labels
        return str(item_labels) == label_filter
    filtered_df = filtered_df[filtered_df["labels"].apply(match_label)]

if date_filter != "All Time" and "created_dt" in filtered_df.columns:
    days_map = {"Last 14 Days": 14, "Last 30 Days": 30, "Last 60 Days": 60, "Last 90 Days": 90}
    cutoff = datetime.utcnow() - timedelta(days=days_map.get(date_filter, 30))
    filtered_df = filtered_df[filtered_df["created_dt"] >= cutoff]

if search_query.strip():
    q = search_query.strip().lower()
    if q.startswith("#") and q[1:].isdigit():
        target_num = int(q[1:])
        filtered_df = filtered_df[filtered_df["number"] == target_num]
    else:
        filtered_df = filtered_df[
            filtered_df["title"].str.lower().str.contains(q, na=False)
            | filtered_df["user_login"].str.lower().str.contains(q, na=False)
            | filtered_df["number"].astype(str).str.contains(q, na=False)
        ]

# ── 3. KPI METRICS (CALCULATED ON FILTERED DATA) ──────────────────────────────
is_open = filtered_df["state"].str.lower() == "open"
is_closed = filtered_df["state"].str.lower() == "closed"

total_issues = len(filtered_df)
open_count = int(is_open.sum())
closed_count = int(is_closed.sum())
closure_rate = round((closed_count / total_issues * 100), 1) if total_issues > 0 else 0.0

# Calculate resolution cycle times strictly on closed issues
closed_df = filtered_df[is_closed].copy()
if not closed_df.empty and "created_dt" in closed_df.columns and "closed_dt" in closed_df.columns:
    closed_df["res_days"] = (closed_df["closed_dt"] - closed_df["created_dt"]).dt.total_seconds() / 86400.0
    valid_res_days = closed_df["res_days"].dropna()
    valid_res_days = valid_res_days[valid_res_days >= 0]
    avg_res_days = valid_res_days.mean() if not valid_res_days.empty else 0.0
    median_res_days = valid_res_days.median() if not valid_res_days.empty else 0.0
    fast_pct = round(((valid_res_days <= 1.0).sum() / len(valid_res_days)) * 100, 1) if not valid_res_days.empty else 0.0
else:
    avg_res_days = 0.0
    median_res_days = 0.0
    fast_pct = 0.0
    valid_res_days = pd.Series(dtype=float)

render_section_header("Backlog Health & Resolution Velocity", "Core metrics computed dynamically from filtered issues")

m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    render_metric_card("Total Tracked", str(total_issues), delta=f"{len(df)} total in scope", icon="🐛")
with m2:
    open_pct = round((open_count / total_issues * 100), 1) if total_issues > 0 else 0.0
    render_metric_card("Open Backlog", str(open_count), delta=f"{open_pct}% of tracked", icon="⚠️")
with m3:
    render_metric_card("Resolved / Closed", str(closed_count), delta=f"{closure_rate}% closure rate", icon="✅")
with m4:
    med_str = f"{median_res_days:.1f}d" if median_res_days >= 1.0 else f"{median_res_days * 24:.1f}h"
    render_metric_card("Median Resolution", med_str, delta=f"{fast_pct}% <24h triage", icon="⏱️")
with m5:
    avg_str = f"{avg_res_days:.1f}d" if avg_res_days >= 1.0 else f"{avg_res_days * 24:.1f}h"
    render_metric_card("Mean Duration", avg_str, delta=f"{len(valid_res_days)} resolved", icon="📊")

# ── 4. VISUALIZATION SECTION 1: STATE & REPOSITORY DISTRIBUTIONS ──────────────
render_section_header("Distribution & Repository Telemetry", "Status proportion and cross-repository issue concentration")

col_state_donut, col_repo_dist = st.columns([1, 1.8])

with col_state_donut:
    st.plotly_chart(create_issue_state_donut(open_count, closed_count), use_container_width=True)

with col_repo_dist:
    # Compute repository-wise open vs closed issue count
    if not filtered_df.empty and "repository_name" in filtered_df.columns:
        repo_agg = filtered_df.groupby(["repository_name", "state"]).size().unstack(fill_value=0)
        repo_list = list(repo_agg.index)
        open_c = [int(repo_agg.loc[r].get("open", 0)) for r in repo_list]
        closed_c = [int(repo_agg.loc[r].get("closed", 0)) for r in repo_list]
        st.plotly_chart(
            create_repository_issue_distribution_chart(repo_list, open_c, closed_c),
            use_container_width=True,
        )
    else:
        render_empty_state("No Repository Distribution", "No issues match the selected filter criteria.")

# ── 5. VISUALIZATION SECTION 2: LABELS & RESOLUTION COHORTS ───────────────────
render_section_header("Issue Categories & Resolution Cycle Times", "Categorization breakdown alongside turnaround duration cohorts")

col_labels, col_cohorts = st.columns([1.5, 1.5])

with col_labels:
    # Flatten and aggregate labels
    label_records = []
    for row_labels in filtered_df.get("labels", []):
        if isinstance(row_labels, list):
            for l in row_labels:
                if l and str(l).strip():
                    label_records.append(str(l).strip())
        elif isinstance(row_labels, str) and row_labels.strip():
            label_records.append(row_labels.strip())

    if label_records:
        label_counts = pd.Series(label_records).value_counts().head(8)
        st.plotly_chart(
            create_issue_label_distribution_chart(list(label_counts.index), list(label_counts.values)),
            use_container_width=True,
        )
    else:
        render_empty_state("No Categorized Labels", "No label taxonomy metadata found for these issues.")

with col_cohorts:
    if not valid_res_days.empty:
        bins = [-1, 1, 7, 30, 90, 10000]
        cohort_labels = ["< 24 Hours", "1-7 Days", "1-4 Weeks", "1-3 Months", "> 3 Months"]
        cohort_series = pd.cut(valid_res_days, bins=bins, labels=cohort_labels)
        cohort_counts = cohort_series.value_counts().reindex(cohort_labels).fillna(0)
        st.plotly_chart(
            create_resolution_cohort_bar(cohort_labels, list(cohort_counts.values.astype(int))),
            use_container_width=True,
        )
    else:
        render_empty_state("No Closed Issues", "At least one resolved issue is required to generate resolution cohorts.")

# ── 6. VISUALIZATION SECTION 3: INFLOW VS RESOLUTION VELOCITY ─────────────────
render_section_header("Issue Creation & Closure Velocity Timeline", "Daily cadence comparing incoming bug reports against resolved items")

if "created_dt" in filtered_df.columns and not filtered_df.empty:
    created_ts = filtered_df.dropna(subset=["created_dt"]).set_index("created_dt").resample("D").size()
    closed_ts = pd.Series(dtype=int)
    if "closed_dt" in filtered_df.columns:
        closed_ts = filtered_df.dropna(subset=["closed_dt"]).set_index("closed_dt").resample("D").size()

    # Align dates across both series
    all_dates_idx = created_ts.index.union(closed_ts.index) if not closed_ts.empty else created_ts.index
    if not all_dates_idx.empty:
        c_aligned = created_ts.reindex(all_dates_idx, fill_value=0)
        cl_aligned = closed_ts.reindex(all_dates_idx, fill_value=0) if not closed_ts.empty else pd.Series(0, index=all_dates_idx)
        dates_formatted = [d.strftime("%b %d") for d in all_dates_idx]
        st.plotly_chart(
            create_issue_velocity_chart(dates_formatted, list(c_aligned.values), list(cl_aligned.values)),
            use_container_width=True,
        )
    else:
        render_empty_state("No Timeline Data", "Issue timestamp information is not available.")
else:
    render_empty_state("No Creation Dates", "Created timestamps not present in the current dataset.")

# ── 7. COMPLETE SEARCHABLE & SORTABLE ISSUE LEDGER ────────────────────────────
render_section_header(
    f"Complete Issue Ledger ({len(filtered_df)} records)",
    "Interactive, sortable, and filterable table of all tracked issues",
)

if filtered_df.empty:
    render_empty_state("No Matching Issues", "Adjust the search filters above to view issue records.")
else:
    display_df = filtered_df.copy()

    # Format labels cleanly as readable comma-separated string
    def format_labels(l):
        if isinstance(l, list):
            return ", ".join(str(x) for x in l if x)
        return str(l) if pd.notna(l) else ""
    display_df["tags"] = display_df["labels"].apply(format_labels)

    # Format resolution duration
    def format_res(row):
        if row.get("state", "").lower() == "open":
            return "In Progress"
        val = row.get("resolution_days")
        if pd.notna(val) and val is not None:
            return f"{float(val):.1f} days" if float(val) >= 1.0 else f"{float(val)*24:.1f} hrs"
        return "Closed"
    display_df["turnaround"] = display_df.apply(format_res, axis=1)

    table_cols = [
        c for c in [
            "number",
            "repository_name",
            "title",
            "state",
            "user_login",
            "tags",
            "comments_count",
            "turnaround",
            "created_at",
            "closed_at",
        ]
        if c in display_df.columns
    ]

    st.dataframe(
        display_df[table_cols],
        column_config={
            "number": st.column_config.NumberColumn("Issue #", format="#%d"),
            "repository_name": st.column_config.TextColumn("Repository"),
            "title": st.column_config.TextColumn("Title", width="large"),
            "state": st.column_config.TextColumn("Status"),
            "user_login": st.column_config.TextColumn("Reporter"),
            "tags": st.column_config.TextColumn("Labels & Categories"),
            "comments_count": st.column_config.NumberColumn("Comments", format="%d"),
            "turnaround": st.column_config.TextColumn("Resolution Time"),
            "created_at": st.column_config.TextColumn("Opened At"),
            "closed_at": st.column_config.TextColumn("Closed At"),
        },
        use_container_width=True,
        hide_index=True,
    )

    # CSV Download capability
    csv_bytes = display_df[table_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Issues Dataset as CSV",
        data=csv_bytes,
        file_name=f"gitpulse_issues_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        use_container_width=False,
    )
