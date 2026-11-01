"""
Page 4 — Commit Explorer
Search, filter, and inspect detailed git commit transactions.
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
from components.charts import create_daily_activity_line
from services import cached_api

page_setup("Commits Explorer", icon="🔨")
render_sidebar()

# Page Header
render_page_header(
    title="Commit Explorer",
    subtitle="Detailed inspection of code changes, additions, deletions, and authorship history",
    icon="🔨",
)

# Repositories for Filtering
repos = cached_api.get_repositories()
repo_options = ["All Monitored Repositories"] + [r["full_name"] for r in repos if "full_name" in r]
current_repo = st.session_state.get("selected_repo", "All Monitored Repositories")
initial_repo_idx = repo_options.index(current_repo) if current_repo in repo_options else 0

# Section 1: Filters
render_section_header("Search & Filters", "Query commits by commit message, hash, author or repository")
with st.container():
    f1, f2, f3, f4 = st.columns([2.5, 1.5, 1.5, 1])
    with f1:
        search_query = st.text_input(
            "Search message or SHA",
            placeholder="Search commit messages or SHA hashes...",
            label_visibility="collapsed",
        )
    with f2:
        author_input = st.text_input(
            "Author",
            placeholder="Filter by author name or email...",
            label_visibility="collapsed",
        )
    with f3:
        selected_repo_filter = st.selectbox(
            "Repository",
            options=repo_options,
            index=initial_repo_idx,
            label_visibility="collapsed",
        )
    with f4:
        limit_select = st.selectbox(
            "Limit",
            [50, 100, 200, 400],
            index=2,
            label_visibility="collapsed",
        )

target_repo_id = None
if selected_repo_filter != "All Monitored Repositories":
    matched = [r for r in repos if r.get("full_name") == selected_repo_filter]
    if matched:
        target_repo_id = matched[0]["id"]

# Fetch Commits with Caching
commits = cached_api.get_commits(
    repository_id=target_repo_id,
    author=author_input if author_input else None,
    limit=limit_select,
)

if not commits:
    render_empty_state(
        "No Commits Found",
        "No commit transactions match your filter criteria. Try broadening your query or trigger ELT sync.",
    )
else:
    df = pd.DataFrame(commits)

    # Filter by text search if provided
    if search_query:
        sq = search_query.lower()
        df = df[
            df["message"].fillna("").str.lower().str.contains(sq)
            | df["sha"].fillna("").str.lower().str.contains(sq)
        ]

    total_found = len(df)
    total_adds = int(df["additions"].sum()) if "additions" in df.columns else 0
    total_dels = int(df["deletions"].sum()) if "deletions" in df.columns else 0
    net_changes = total_adds - total_dels

    # Section 2: Metrics
    render_section_header("Code Churn Metrics", "Aggregate delta across currently filtered commits")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_metric_card("Filtered Commits", str(total_found), icon="🔨")
    with c2:
        render_metric_card("Lines Added", f"+{total_adds:,}", icon="🟢")
    with c3:
        render_metric_card("Lines Deleted", f"-{total_dels:,}", icon="🔴")
    with c4:
        net_str = f"+{net_changes:,}" if net_changes >= 0 else f"{net_changes:,}"
        render_metric_card("Net Code Churn", net_str, icon="📈")

    # Section 3: Ingestion Velocity
    render_section_header("Commit Timeline Cadence", "Daily commit frequency across selected timeframe")
    if "author_date" in df.columns and not df.empty:
        df["date"] = pd.to_datetime(df["author_date"], errors="coerce").dt.date
        daily_counts = df.dropna(subset=["date"]).groupby("date").size()
        if not daily_counts.empty:
            dates_str = [d.strftime("%b %d") for d in daily_counts.index]
            fig = create_daily_activity_line(
                dates_str,
                list(daily_counts.values),
                name="Commit Frequency",
                color="#60a5fa",
            )
            st.plotly_chart(fig, use_container_width=True)

    # Section 4: Log Table with Pagination
    render_section_header(f"Commit Ledger ({len(df)} records)", "Chronological transaction history")
    page_size = 15
    total_pages = max(1, (len(df) - 1) // page_size + 1)
    col_p1, col_p2 = st.columns([1, 5])
    with col_p1:
        current_page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)

    start_idx = (current_page - 1) * page_size
    end_idx = start_idx + page_size
    page_df = df.iloc[start_idx:end_idx].copy()

    if "sha" in page_df.columns:
        page_df["short_sha"] = page_df["sha"].str[:7]
    if "message" in page_df.columns:
        page_df["summary"] = page_df["message"].str.split("\n").str[0]

    cols_to_show = [
        c
        for c in ["short_sha", "author_name", "author_date", "summary", "additions", "deletions"]
        if c in page_df.columns
    ]

    st.dataframe(
        page_df[cols_to_show],
        column_config={
            "short_sha": "SHA",
            "author_name": "Author",
            "author_date": "Timestamp",
            "summary": "Commit Message",
            "additions": st.column_config.NumberColumn("Additions", format="+%d"),
            "deletions": st.column_config.NumberColumn("Deletions", format="-%d"),
        },
        use_container_width=True,
        hide_index=True,
    )
