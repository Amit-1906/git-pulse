"""
Page 3 — Contributor Analytics
Analyze developer contributions across projects, active timeframes, and commit volumes.
Includes vital context disclaimers to prevent equating raw volume with productivity.
"""
import sys
from pathlib import Path
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

frontend_dir = Path(__file__).parent.parent
if str(frontend_dir) not in sys.path:
    sys.path.insert(0, str(frontend_dir))

from components.header import render_header
from components.sidebar import render_sidebar
from components.metrics import render_metric_card
from components.charts import create_contributors_leaderboard, create_daily_activity_line
from services.api_client import api_client

st.set_page_config(
    page_title="GitPulse | Contributors",
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
    title="Contributor Analytics",
    subtitle="Understand engineering participation, collaboration cadence, and team engagement",
    current_repo=current_repo,
)

# ── Methodological Disclaimer ──────────────────────────────────────────────
st.markdown(
    """
    <div style="background: rgba(47, 129, 247, 0.08); border-left: 4px solid #2f81f7; padding: 0.85rem 1.25rem; border-radius: 4px; margin-bottom: 1.5rem; font-size: 0.85rem; color: #8b949e;">
        <strong style="color: #58a6ff;">📌 Important Engineering Ethics Note:</strong>
        Commit counts represent source-control transaction frequency and do not measure developer productivity, impact, or code quality. Complex architectural refactors, debugging, code reviews, and design discussions are not captured by raw commit counts.
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Target Repository Scope ────────────────────────────────────────────────
repos = api_client.get_repositories()
repo_id_filter = None
if current_repo != "All Monitored Repositories":
    for r in repos:
        if r.get("full_name") == current_repo:
            repo_id_filter = r.get("id")
            break

# ── Fetch Data ─────────────────────────────────────────────────────────────
with st.spinner("Fetching contributor metrics..."):
    contributors = api_client.get_contributors(repository_id=repo_id_filter)
    commits = api_client.get_commits(repository_id=repo_id_filter, limit=500)

if not contributors:
    st.info("No contributor data found. Make sure repositories have been ingested through the extraction pipeline.")
else:
    cdf = pd.DataFrame(contributors)

    total_contributors = len(cdf)
    total_commits = cdf["commits_count"].sum() if "commits_count" in cdf.columns else 0
    avg_commits = round(total_commits / total_contributors, 1) if total_contributors > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_metric_card("Active Contributors", str(total_contributors), icon="👥")
    with c2:
        render_metric_card("Total Attributed Commits", f"{total_commits:,}", icon="🔨")
    with c3:
        render_metric_card("Mean Commits / Author", str(avg_commits), icon="📊")
    with c4:
        top_author = cdf.iloc[0]["login"] if not cdf.empty else "N/A"
        render_metric_card("Most Active Committer", top_author, icon="🏆")

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    # ── Leaderboard & Timeline ─────────────────────────────────────────────
    col_chart, col_table = st.columns([1.6, 1.4])
    with col_chart:
        st.markdown("### 🏆 Top Contributors by Commit Volume")
        top_n = min(15, len(cdf))
        top_contribs = cdf.head(top_n)
        fig = create_contributors_leaderboard(
            list(top_contribs["login"]),
            list(top_contribs["commits_count"]),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_table:
        st.markdown("### 📋 Contributor Directory")
        display_cols = [c for c in ["login", "commits_count", "first_commit_date", "last_commit_date"] if c in cdf.columns]
        st.dataframe(
            cdf[display_cols],
            column_config={
                "login": "Contributor",
                "commits_count": st.column_config.NumberColumn("Commits", format="%d"),
                "first_commit_date": "Earliest Commit",
                "last_commit_date": "Latest Commit",
            },
            use_container_width=True,
            hide_index=True,
        )

    # ── Contributor Comparison & Activity ──────────────────────────────────
    st.markdown("---")
    st.markdown("### 👥 Contributor Activity Comparison")

    all_logins = list(cdf["login"].unique())
    selected_authors = st.multiselect(
        "Select up to 4 contributors to compare activity timelines:",
        options=all_logins,
        default=all_logins[:2] if len(all_logins) >= 2 else all_logins[:1],
    )

    if selected_authors and commits:
        commit_df = pd.DataFrame(commits)
        if "author_name" in commit_df.columns and "author_date" in commit_df.columns:
            commit_df["date"] = pd.to_datetime(commit_df["author_date"], errors="coerce").dt.date
            fig_compare = go.Figure()
            colors = ["#2f81f7", "#8b5cf6", "#3fb950", "#d29922"]

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
                            line=dict(color=colors[i % len(colors)], width=2),
                        )
                    )

            fig_compare.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#8b949e"),
                xaxis=dict(gridcolor="#21262d"),
                yaxis=dict(gridcolor="#21262d", title="Daily Commits"),
                title="Comparative Commit Cadence Over Time",
                legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="#21262d"),
            )
            st.plotly_chart(fig_compare, use_container_width=True)
        else:
            st.info("Commit author details not available for comparison.")
    elif not commits:
        st.info("No individual commit histories loaded to generate comparison charts.")
