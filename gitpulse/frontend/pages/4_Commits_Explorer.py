"""
Page 4 — Commit Explorer
Search, filter, and inspect detailed git commit transactions.
Filter by repository, author, date ranges, and commit message.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
import streamlit as st
import pandas as pd

frontend_dir = Path(__file__).parent.parent
if str(frontend_dir) not in sys.path:
    sys.path.insert(0, str(frontend_dir))

from components.header import render_header
from components.sidebar import render_sidebar
from components.metrics import render_metric_card
from components.charts import create_daily_activity_line
from services.api_client import api_client

st.set_page_config(
    page_title="GitPulse | Commits Explorer",
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
    title="Commit Explorer",
    subtitle="Detailed inspection of code changes, additions, deletions, and authorship history",
    current_repo=current_repo,
)

# ── Load Repositories for Filtering ────────────────────────────────────────
repos = api_client.get_repositories()
repo_options = ["All Monitored Repositories"] + [r["full_name"] for r in repos]
initial_repo_idx = repo_options.index(current_repo) if current_repo in repo_options else 0

# ── Filter Controls ────────────────────────────────────────────────────────
with st.container():
    f1, f2, f3, f4 = st.columns([2, 1.5, 1.5, 1])
    with f1:
        search_query = st.text_input("🔍 Search commit message / SHA", placeholder="e.g. fix(api): auth header...")
    with f2:
        author_input = st.text_input("👤 Filter by Author", placeholder="Author name or email...")
    with f3:
        selected_repo_filter = st.selectbox("Repository", options=repo_options, index=initial_repo_idx)
    with f4:
        limit_select = st.selectbox("Limit", [50, 100, 200, 500], index=2)

target_repo_id = None
if selected_repo_filter != "All Monitored Repositories":
    matched = [r for r in repos if r["full_name"] == selected_repo_filter]
    if matched:
        target_repo_id = matched[0]["id"]

# ── Fetch Data ─────────────────────────────────────────────────────────────
with st.spinner("Fetching commits from backend..."):
    commits = api_client.get_commits(
        repository_id=target_repo_id,
        author=author_input if author_input else None,
        limit=limit_select,
    )

if not commits:
    st.info("No commits found matching the specified criteria. Make sure data has been extracted from GitHub.")
else:
    df = pd.DataFrame(commits)

    # Apply client-side text search if provided
    if search_query:
        sq = search_query.lower()
        df = df[
            df["message"].fillna("").str.lower().str.contains(sq)
            | df["sha"].fillna("").str.lower().str.contains(sq)
        ]

    # Metrics Row
    total_found = len(df)
    total_adds = df["additions"].sum() if "additions" in df.columns else 0
    total_dels = df["deletions"].sum() if "deletions" in df.columns else 0
    net_changes = total_adds - total_dels

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

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    # ── Timeline Visualization ─────────────────────────────────────────────
    if "author_date" in df.columns and not df.empty:
        df["date"] = pd.to_datetime(df["author_date"], errors="coerce").dt.date
        daily_counts = df.dropna(subset=["date"]).groupby("date").size()
        if not daily_counts.empty:
            dates_str = [d.strftime("%b %d") for d in daily_counts.index]
            fig = create_daily_activity_line(
                dates_str,
                list(daily_counts.values),
                name="Commit Frequency",
                color="#58a6ff",
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── Commits Table with Pagination ──────────────────────────────────────
    st.markdown(f"### 📋 Commit Log ({len(df)} records)")

    page_size = 15
    total_pages = max(1, (len(df) - 1) // page_size + 1)
    col_p1, col_p2 = st.columns([1, 4])
    with col_p1:
        current_page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)

    start_idx = (current_page - 1) * page_size
    end_idx = start_idx + page_size
    page_df = df.iloc[start_idx:end_idx].copy()

    # Format SHA short and message single-line
    if "sha" in page_df.columns:
        page_df["short_sha"] = page_df["sha"].str[:7]
    if "message" in page_df.columns:
        page_df["summary"] = page_df["message"].str.split("\n").str[0]

    cols_to_show = [
        c for c in ["short_sha", "author_name", "author_date", "summary", "additions", "deletions"]
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
