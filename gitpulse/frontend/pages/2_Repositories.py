"""
Page 2 — Repository Explorer
Search, inspect, and analyze tracked repositories.
Provides rich metadata cards, commit & issue activity trends, and on-demand ELT sync.
"""
import sys
from pathlib import Path
from datetime import datetime
import streamlit as st
import pandas as pd

frontend_dir = Path(__file__).parent.parent
if str(frontend_dir) not in sys.path:
    sys.path.insert(0, str(frontend_dir))

from components.header import render_header
from components.sidebar import render_sidebar
from components.metrics import render_metric_card, render_status_pill
from components.charts import create_activity_area_chart, create_commits_bar_chart
from services.api_client import api_client

st.set_page_config(
    page_title="GitPulse | Repositories",
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
    title="Repository Explorer",
    subtitle="Inspect metadata, tracked health, and activity velocity across repositories",
    current_repo=current_repo,
)

# ── Fetch Repositories ─────────────────────────────────────────────────────
with st.spinner("Fetching tracked repositories..."):
    repos = api_client.get_repositories()

# ── Search & Filter Controls ───────────────────────────────────────────────
c_search, c_lang, c_status = st.columns([3, 1.5, 1.5])
with c_search:
    search_query = st.text_input("🔍 Search repositories", placeholder="Filter by name, owner, or description...", label_visibility="collapsed")
with c_lang:
    languages = sorted(list({r.get("language") for r in repos if r.get("language")}))
    lang_filter = st.selectbox("Language", ["All Languages"] + languages, label_visibility="collapsed")
with c_status:
    status_filter = st.selectbox("Status", ["All Statuses", "Active Only", "Inactive Only"], label_visibility="collapsed")

# Apply filters
filtered_repos = repos
if search_query:
    q = search_query.lower()
    filtered_repos = [
        r for r in filtered_repos
        if q in r.get("name", "").lower()
        or q in r.get("owner", "").lower()
        or q in r.get("full_name", "").lower()
        or q in (r.get("description") or "").lower()
    ]
if lang_filter != "All Languages":
    filtered_repos = [r for r in filtered_repos if r.get("language") == lang_filter]
if status_filter == "Active Only":
    filtered_repos = [r for r in filtered_repos if r.get("is_active", True)]
elif status_filter == "Inactive Only":
    filtered_repos = [r for r in filtered_repos if not r.get("is_active", True)]

# ── Repositories Grid / Detail View ────────────────────────────────────────
st.markdown(f"#### Monitored Repositories ({len(filtered_repos)})")

if not filtered_repos:
    st.info("No repositories match the specified filters. Try clearing your search or register a new repository in Settings.")
else:
    # Display repository cards
    for idx, repo in enumerate(filtered_repos):
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

        with st.container():
            st.markdown(
                f"""
                <div class="gp-metric-card" style="margin-bottom: 1rem; padding: 1.25rem;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div>
                            <span style="font-size: 1.25rem; font-weight: 700; color: #58a6ff;">
                                <a href="{html_url}" target="_blank" style="color: #58a6ff; text-decoration: none;">{full_name}</a>
                            </span>
                            <span style="margin-left: 0.75rem;">
                                {render_status_pill('active' if is_active else 'inactive')}
                            </span>
                            <p style="color: #8b949e; font-size: 0.875rem; margin: 0.4rem 0 0.75rem 0;">{desc}</p>
                        </div>
                    </div>
                    <div style="display: flex; gap: 1.5rem; font-size: 0.85rem; color: #f0f6fc; margin-top: 0.5rem; border-top: 1px solid #21262d; padding-top: 0.75rem;">
                        <div><strong>Language:</strong> <span style="color: #8b949e;">{lang}</span></div>
                        <div>⭐ <strong>Stars:</strong> <span style="color: #8b949e;">{stars:,}</span></div>
                        <div>🍴 <strong>Forks:</strong> <span style="color: #8b949e;">{forks:,}</span></div>
                        <div>🐛 <strong>Open Issues:</strong> <span style="color: #8b949e;">{open_issues:,}</span></div>
                        <div>🕒 <strong>Last Synced:</strong> <span style="color: #8b949e;">{last_synced}</span></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            col_btn1, col_btn2, col_btn3 = st.columns([1.5, 1.5, 5])
            with col_btn1:
                if st.button(f"⚡ Sync ELT", key=f"sync_btn_{repo_id}"):
                    with st.spinner(f"Triggering sync for {full_name}..."):
                        res = api_client.trigger_pipeline(repo_id)
                        if res:
                            st.success(f"Pipeline triggered for {full_name}!")
                        else:
                            st.info("Sync queued (standalone preview mode).")
            with col_btn2:
                if st.button(f"📊 Drill Down", key=f"drill_btn_{repo_id}"):
                    st.session_state["selected_repo"] = full_name
                    st.session_state["drilldown_repo_id"] = repo_id
                    st.rerun()

    # ── Drill-down Analytics Section ───────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🔍 Deep Repository Inspection")

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
        st.markdown(f"Showing analytical deep-dive for **{d_name}**")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_metric_card("Stargazers", f"{drilldown_repo.get('stargazers_count', 0):,}", icon="⭐")
        with c2:
            render_metric_card("Forks", f"{drilldown_repo.get('forks_count', 0):,}", icon="🍴")
        with c3:
            render_metric_card("Open Issues", f"{drilldown_repo.get('open_issues_count', 0):,}", icon="🐛")
        with c4:
            render_metric_card("Primary Language", drilldown_repo.get("language") or "Unknown", icon="💻")

        # Commits and PRs for this specific repo
        with st.spinner("Fetching repository commits and PRs..."):
            repo_commits = api_client.get_commits(repository_id=d_id, limit=100)
            repo_prs = api_client.get_pull_requests(repository_id=d_id, limit=100)

        col_trend, col_recent = st.columns([2, 1])
        with col_trend:
            st.markdown("##### Commit Timeline")
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
                    st.info("Commit dates not available.")
            else:
                st.info("No commits recorded for this repository. Trigger an ELT extraction to populate data.")

        with col_recent:
            st.markdown("##### Recent PR Activity")
            if repo_prs:
                pr_df = pd.DataFrame(repo_prs)
                disp_pr_cols = [c for c in ["number", "title", "state", "user_login"] if c in pr_df.columns]
                st.dataframe(pr_df[disp_pr_cols].head(5), use_container_width=True, hide_index=True)
            else:
                st.info("No PRs recorded for this repository.")
