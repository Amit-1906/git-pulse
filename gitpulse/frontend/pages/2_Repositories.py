"""
Page 2 — Repository Explorer
Search, inspect, and analyze tracked repositories.
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
from components.charts import create_commits_bar_chart
from services import cached_api

page_setup("Repositories", icon="📁")
render_sidebar()

# Page Header
render_page_header(
    title="Repository Explorer",
    subtitle="Inspect metadata, tracked health, and activity velocity across repositories",
    icon="📁",
)

# Fetch repositories with caching
repos = cached_api.get_repositories()

# Section 1: Filters & Search Controls
render_section_header("Repository Search & Filters", "Narrow down monitored codebases")
c_search, c_lang, c_status = st.columns([3, 1.5, 1.5])
with c_search:
    search_query = st.text_input(
        "Search repositories",
        placeholder="Search by repository name, owner, or description...",
        label_visibility="collapsed",
    )
with c_lang:
    languages = sorted(list({r.get("language") for r in repos if r.get("language")}))
    lang_filter = st.selectbox(
        "Language",
        ["All Languages"] + languages,
        label_visibility="collapsed",
    )
with c_status:
    status_filter = st.selectbox(
        "Status",
        ["All Statuses", "Active Only", "Inactive Only"],
        label_visibility="collapsed",
    )

# Filter logic
filtered_repos = repos
if search_query:
    q = search_query.lower()
    filtered_repos = [
        r
        for r in filtered_repos
        if q in str(r.get("name", "")).lower()
        or q in str(r.get("owner", "")).lower()
        or q in str(r.get("full_name", "")).lower()
        or q in str(r.get("description") or "").lower()
    ]
if lang_filter != "All Languages":
    filtered_repos = [r for r in filtered_repos if r.get("language") == lang_filter]
if status_filter == "Active Only":
    filtered_repos = [r for r in filtered_repos if r.get("is_active", True)]
elif status_filter == "Inactive Only":
    filtered_repos = [r for r in filtered_repos if not r.get("is_active", True)]

# Section 2: Repository Cards Grid
render_section_header(f"Tracked Repositories ({len(filtered_repos)})", "Catalog of configured repositories")

if not filtered_repos:
    render_empty_state(
        "No Matching Repositories",
        "Try modifying your filters, or register a new repository under Settings.",
    )
else:
    for repo in filtered_repos:
        repo_id = repo.get("id")
        full_name = repo.get("full_name") or f"{repo.get('owner')}/{repo.get('name')}"
        desc = repo.get("description") or "No description provided."
        stars = repo.get("stargazers_count", 0)
        forks = repo.get("forks_count", 0)
        open_issues = repo.get("open_issues_count", 0)
        lang = repo.get("language") or "N/A"
        is_active = repo.get("is_active", True)
        last_synced = repo.get("last_synced_at") or "Never synced"
        html_url = repo.get("html_url") or f"https://github.com/{full_name}"

        st.markdown(
            f"""
            <div class="gp-panel" style="margin-bottom: 0.75rem;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div>
                        <span style="font-size: 1.15rem; font-weight: 700; color: var(--gp-blue-hover);">
                            <a href="{html_url}" target="_blank" style="color: var(--gp-blue-hover); text-decoration: none;">{full_name}</a>
                        </span>
                        <span style="margin-left: 0.75rem;">
                            {render_status_badge('active' if is_active else 'inactive')}
                        </span>
                        <p style="color: var(--gp-text-secondary); font-size: 0.85rem; margin: 0.35rem 0 0.5rem 0;">{desc}</p>
                    </div>
                </div>
                <div style="display: flex; gap: 1.75rem; font-size: 0.8rem; color: var(--gp-text-main); margin-top: 0.4rem; border-top: 1px solid var(--gp-border); padding-top: 0.6rem; flex-wrap: wrap;">
                    <div><strong>Language:</strong> <span style="color: var(--gp-text-muted);">{lang}</span></div>
                    <div>⭐ <strong>Stars:</strong> <span style="color: var(--gp-text-muted);">{stars:,}</span></div>
                    <div>🍴 <strong>Forks:</strong> <span style="color: var(--gp-text-muted);">{forks:,}</span></div>
                    <div>🐛 <strong>Open Issues:</strong> <span style="color: var(--gp-text-muted);">{open_issues:,}</span></div>
                    <div>🕒 <strong>Last Synced:</strong> <span style="color: var(--gp-text-muted);">{last_synced}</span></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_btn1, col_btn2, _ = st.columns([1.5, 1.5, 6])
        with col_btn1:
            if st.button("⚡ Sync ELT", key=f"sync_repo_{repo_id}"):
                with st.spinner("Dispatching extraction..."):
                    res = cached_api.trigger_pipeline(repo_id)
                    st.toast(f"Pipeline triggered for {full_name}!", icon="🚀")
        with col_btn2:
            if st.button("🔍 Inspect", key=f"inspect_repo_{repo_id}"):
                st.session_state["selected_repo"] = full_name
                st.session_state["drilldown_repo_id"] = repo_id
                st.rerun()

# Section 3: Deep Repository Inspection
render_section_header("Deep Inspection", "Detailed metrics for the currently selected repository")

drilldown_repo = None
selected_name = st.session_state.get("selected_repo")
if selected_name and selected_name != "All Monitored Repositories":
    for r in repos:
        if r.get("full_name") == selected_name:
            drilldown_repo = r
            break
if not drilldown_repo and repos:
    drilldown_repo = repos[0]

if drilldown_repo:
    d_id = drilldown_repo.get("id")
    d_name = drilldown_repo.get("full_name")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_metric_card("Stargazers", f"{drilldown_repo.get('stargazers_count', 0):,}", icon="⭐")
    with c2:
        render_metric_card("Forks", f"{drilldown_repo.get('forks_count', 0):,}", icon="🍴")
    with c3:
        render_metric_card("Open Issues", f"{drilldown_repo.get('open_issues_count', 0):,}", icon="🐛")
    with c4:
        render_metric_card("Primary Language", drilldown_repo.get("language") or "Unknown", icon="💻")

    col_trend, col_recent = st.columns([2, 1])
    with col_trend:
        st.markdown("<h5 style='color: var(--gp-text-main); font-size: 0.95rem; margin-top: 0.75rem; margin-bottom: 0.5rem;'>Commit Ingestion Frequency</h5>", unsafe_allow_html=True)
        repo_commits = cached_api.get_commits(repository_id=d_id, limit=100)
        if repo_commits:
            cdf = pd.DataFrame(repo_commits)
            if "author_date" in cdf.columns and not cdf.empty:
                cdf["date"] = pd.to_datetime(cdf["author_date"], errors="coerce").dt.date
                daily_commits = cdf.groupby("date").size()
                st.plotly_chart(
                    create_commits_bar_chart(
                        [d.strftime("%b %d") for d in daily_commits.index],
                        list(daily_commits.values),
                    ),
                    use_container_width=True,
                )
            else:
                render_empty_state("No Timestamps", "Commit dates not formatted properly.")
        else:
            render_empty_state("No Commits", "Run an ELT extraction to populate commits.")

    with col_recent:
        st.markdown("<h5 style='color: var(--gp-text-main); font-size: 0.95rem; margin-top: 0.75rem; margin-bottom: 0.5rem;'>Recent Pull Requests</h5>", unsafe_allow_html=True)
        repo_prs = cached_api.get_pull_requests(repository_id=d_id, limit=10)
        if repo_prs:
            pr_df = pd.DataFrame(repo_prs)
            disp_pr_cols = [c for c in ["number", "title", "state", "user_login"] if c in pr_df.columns]
            st.dataframe(
                pr_df[disp_pr_cols].head(6),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "number": st.column_config.NumberColumn("PR #", format="#%d"),
                    "title": "Title",
                    "state": "Status",
                    "user_login": "Author",
                },
            )
        else:
            render_empty_state("No Pull Requests", "PR activity will display here.")
