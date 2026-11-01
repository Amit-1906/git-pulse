"""
Page 3 — Contributor Analytics
Analyze developer contributions across projects, active timeframes, and commit volumes.
Includes vital context disclaimers to prevent equating raw volume with productivity.
"""
from pathlib import Path
import sys
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

frontend_dir = Path(__file__).parent.parent
if str(frontend_dir) not in sys.path:
    sys.path.insert(0, str(frontend_dir))

from components.ui import (
    page_setup,
    render_page_header,
    render_section_header,
    render_metric_card,
    render_callout,
    render_empty_state,
)
from components.sidebar import render_sidebar
from components.charts import create_contributors_leaderboard
from services import cached_api

page_setup("Contributors", icon="👥")
render_sidebar()

# Page Header
render_page_header(
    title="Contributor Analytics",
    subtitle="Engineering participation, collaboration cadence, and team engagement patterns",
    icon="👥",
)

# Ethical Note
render_callout(
    "Commit counts measure source-control transaction cadence, not individual developer productivity, impact, or code quality. Architectural design, reviews, debugging, and cross-team collaboration are vital engineering dimensions beyond commit frequency.",
    title="Engineering Ethics Disclaimer",
    icon="📌",
)

# Scope Resolution
current_repo = st.session_state.get("selected_repo", "All Monitored Repositories")
repos = cached_api.get_repositories()
repo_id_filter = None
if current_repo != "All Monitored Repositories":
    for r in repos:
        if r.get("full_name") == current_repo:
            repo_id_filter = r.get("id")
            break

# Fetch Contributor Metrics with Caching
contributors = cached_api.get_contributors(repository_id=repo_id_filter)
commits = cached_api.get_commits(repository_id=repo_id_filter, limit=400)

if not contributors:
    render_empty_state(
        "No Contributor Telemetry",
        "Run an extraction for the selected repository to discover and populate contributors.",
    )
else:
    cdf = pd.DataFrame(contributors)
    total_contributors = len(cdf)
    total_commits = cdf["commits_count"].sum() if "commits_count" in cdf.columns else 0
    avg_commits = round(total_commits / total_contributors, 1) if total_contributors > 0 else 0
    top_author = cdf.iloc[0]["login"] if not cdf.empty and "login" in cdf.columns else "N/A"

    # Section 1: KPI Cards
    render_section_header("Participation Overview", "High-level authorship distribution")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_metric_card("Active Contributors", str(total_contributors), icon="👥")
    with c2:
        render_metric_card("Attributed Commits", f"{total_commits:,}", icon="🔨")
    with c3:
        render_metric_card("Mean Commits / Author", str(avg_commits), icon="📊")
    with c4:
        render_metric_card("Top Contributor", top_author, icon="🏆")

    # Section 2: Leaderboard & Directory
    render_section_header("Leaderboard & Roster", "Volume breakdown and earliest/latest commit timestamps")
    col_chart, col_table = st.columns([1.5, 1.5])
    with col_chart:
        st.markdown("<h5 style='color: var(--gp-text-main); font-size: 0.95rem; margin-bottom: 0.5rem;'>Top Contributors by Ingested Commits</h5>", unsafe_allow_html=True)
        top_n = min(12, len(cdf))
        top_contribs = cdf.head(top_n)
        fig = create_contributors_leaderboard(
            list(top_contribs["login"]),
            list(top_contribs["commits_count"]),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_table:
        st.markdown("<h5 style='color: var(--gp-text-main); font-size: 0.95rem; margin-bottom: 0.5rem;'>Contributor Directory</h5>", unsafe_allow_html=True)
        display_cols = [c for c in ["login", "commits_count", "first_commit_date", "last_commit_date"] if c in cdf.columns]
        st.dataframe(
            cdf[display_cols],
            column_config={
                "login": "Author",
                "commits_count": st.column_config.NumberColumn("Commits", format="%d"),
                "first_commit_date": "Earliest Recorded",
                "last_commit_date": "Most Recent",
            },
            use_container_width=True,
            hide_index=True,
        )

    # Section 3: Comparative Commit Activity
    render_section_header("Comparative Activity Cadence", "Side-by-side velocity comparison across authors")
    all_logins = list(cdf["login"].unique())
    selected_authors = st.multiselect(
        "Select up to 4 contributors to compare commit cadence over time:",
        options=all_logins,
        default=all_logins[:2] if len(all_logins) >= 2 else all_logins[:1],
    )

    if selected_authors and commits:
        commit_df = pd.DataFrame(commits)
        if "author_name" in commit_df.columns and "author_date" in commit_df.columns:
            commit_df["date"] = pd.to_datetime(commit_df["author_date"], errors="coerce").dt.date
            fig_compare = go.Figure()
            colors = ["#3b82f6", "#8b5cf6", "#10b981", "#f59e0b"]

            for i, author in enumerate(selected_authors):
                author_commits = commit_df[commit_df["author_name"] == author]
                if not author_commits.empty:
                    daily = author_commits.groupby("date").size()
                    fig_compare.add_trace(
                        go.Scatter(
                            x=[d.strftime("%b %d") for d in daily.index],
                            y=list(daily.values),
                            mode="lines+markers",
                            name=author,
                            line=dict(color=colors[i % len(colors)], width=2.5, shape="spline"),
                            marker=dict(size=4),
                        )
                    )

            fig_compare.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#94a3b8", size=11),
                xaxis=dict(gridcolor="#1f2736", showline=True, linecolor="#2b364a"),
                yaxis=dict(gridcolor="#1f2736", showline=True, linecolor="#2b364a", title="Daily Commits"),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1,
                    bgcolor="rgba(15,20,30,0.7)",
                    bordercolor="#1f2736",
                ),
                margin=dict(l=30, r=20, t=20, b=30),
            )
            st.plotly_chart(fig_compare, use_container_width=True)
        else:
            render_empty_state("No Comparison Data", "Author name or date fields not present in commit stream.")
    elif not commits:
        render_empty_state("No Commit History", "Ingest commit data to display comparison curves.")
