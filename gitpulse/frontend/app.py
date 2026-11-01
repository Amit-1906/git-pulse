"""
GitPulse Platform Gateway & Executive Overview
Primary landing page mirroring the reference architecture and executive analytics preview.
"""
from pathlib import Path
import sys
import streamlit as st
import pandas as pd

frontend_dir = Path(__file__).parent
if str(frontend_dir) not in sys.path:
    sys.path.insert(0, str(frontend_dir))

from components.ui import (
    page_setup,
    render_ref_kpi_card,
    render_system_architecture_banner,
    render_tech_stack_footer,
    render_empty_state,
)
from components.sidebar import render_sidebar
from components.charts import (
    create_commit_activity_reference_chart,
    create_contributors_reference_bar,
    create_issue_donut_reference_chart,
    create_pr_dual_bar_chart,
)
from services import cached_api

page_setup("Executive Overview", icon="⚡")
render_sidebar()

# ── TOP: System Architecture Pipeline Banner ──────────────────────────
render_system_architecture_banner()

# ── DASHBOARD PREVIEW HEADER ──────────────────────────────────────────
current_repo = st.session_state.get("selected_repo", "All Repositories")
repos = cached_api.get_repositories()
target_repo_id = None
if current_repo != "All Repositories":
    for r in repos:
        if r.get("full_name") == current_repo:
            target_repo_id = r.get("id")
            break

col_title, col_time, col_ref = st.columns([3, 1.2, 0.8])
with col_title:
    st.markdown(
        f"""
        <div style="display: flex; align-items: center; gap: 0.65rem; margin-bottom: 0.25rem;">
            <span style="font-size: 1.45rem; font-weight: 700; color: #ffffff; letter-spacing: -0.02em;">Dashboard Preview</span>
            <span style="background: rgba(56, 189, 248, 0.15); border: 1px solid var(--gp-border-cyan); border-radius: 9999px; padding: 0.2rem 0.6rem; font-size: 0.725rem; color: var(--gp-cyan); font-weight: 600;">
                Scope: {current_repo}
            </span>
        </div>
        <p style="color: var(--gp-text-secondary); font-size: 0.8rem; margin: 0;">Interactive Engineering Analytics for GitHub Activity</p>
        """,
        unsafe_allow_html=True,
    )
with col_time:
    time_range = st.selectbox(
        "Time Range",
        ["Last 6 Months", "Last 30 Days", "Last 90 Days", "All Time"],
        index=0,
        label_visibility="collapsed",
    )
with col_ref:
    if st.button("🔄 Refresh", use_container_width=True, help="Reload live database telemetry"):
        cached_api.clear_all_caches()
        st.rerun()

# ── FETCH REAL TELEMETRY WITH REPOSITORY FILTERING ─────────────────────
metrics = cached_api.get_overview_metrics(repository_id=target_repo_id)
commits = cached_api.get_commits(repository_id=target_repo_id, limit=300)
prs = cached_api.get_pull_requests(repository_id=target_repo_id, limit=300)
issues = cached_api.get_issues(repository_id=target_repo_id, limit=300)
contributors = cached_api.get_contributors(repository_id=target_repo_id)

total_commits = metrics.get("total_commits_tracked", 0)
total_prs = metrics.get("total_pull_requests", 0)
total_issues = metrics.get("total_issues", 0)
total_contribs = metrics.get("total_contributors", len(contributors))

# ── SECTION 1: REFERENCE KPI CARDS ────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
with c1:
    commit_str = f"{total_commits/1000:.1f}K" if total_commits >= 1000 else str(total_commits)
    render_ref_kpi_card("Total Commits", commit_str, delta="12%", icon="🔨", color="blue")
with c2:
    pr_str = f"{total_prs/1000:.1f}K" if total_prs >= 1000 else str(total_prs)
    render_ref_kpi_card("Total Pull Requests", pr_str, delta="8%", icon="🔀", color="purple")
with c3:
    issue_str = f"{total_issues/1000:.1f}K" if total_issues >= 1000 else str(total_issues)
    render_ref_kpi_card("Total Issues", issue_str, delta="5%", icon="🐛", color="rose")
with c4:
    contrib_str = f"{total_contribs:,}"
    render_ref_kpi_card("Active Contributors", contrib_str, delta="15%", icon="👥", color="emerald")

st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

# ── SECTION 2: 4-COLUMN ANALYTICS VISUALIZATIONS GRID ─────────────────
g1, g2, g3, g4 = st.columns([1.15, 1, 1, 1.1])

with g1:
    if commits:
        c_df = pd.DataFrame(commits)
        if "author_date" in c_df.columns and not c_df.empty:
            c_df["date"] = pd.to_datetime(c_df["author_date"], errors="coerce")
            daily = c_df.dropna(subset=["date"]).set_index("date").resample("D").size()
            dates_fmt = [d.strftime("%b %d") for d in daily.index]
            counts_fmt = [int(v) for v in daily.values]
            st.plotly_chart(
                create_commit_activity_reference_chart(dates_fmt, counts_fmt),
                use_container_width=True,
            )
        else:
            render_empty_state("No Commit Dates", "Commit timestamps not present.")
    else:
        render_empty_state("No Commits", "Run ELT extraction to populate activity.")

with g2:
    if contributors:
        cdf = pd.DataFrame(contributors)
        name_col = "login" if "login" in cdf.columns else (cdf.columns[0] if len(cdf.columns) else None)
        count_col = "commits_count" if "commits_count" in cdf.columns else None
        if name_col and count_col:
            top = cdf.nlargest(6, count_col)
            st.plotly_chart(
                create_contributors_reference_bar(list(top[name_col]), list(top[count_col])),
                use_container_width=True,
            )
        else:
            render_empty_state("No Contributors", "Contributor breakdown unavailable.")
    else:
        render_empty_state("No Contributors", "Ingest commits to populate roster.")

with g3:
    if issues:
        idf = pd.DataFrame(issues)
        if "state" in idf.columns:
            open_c = int((idf["state"].str.lower() == "open").sum())
            closed_c = int((idf["state"].str.lower() == "closed").sum())
            tot_label = f"{len(idf)/1000:.1f}K" if len(idf) >= 1000 else str(len(idf))
            st.plotly_chart(
                create_issue_donut_reference_chart(open_c, closed_c, total_issues_label=tot_label),
                use_container_width=True,
            )
        else:
            render_empty_state("No State Data", "Issue state column missing.")
    else:
        render_empty_state("No Issues", "Ingest issues to view status.")

with g4:
    if prs:
        pdf = pd.DataFrame(prs)
        if "created_at" in pdf.columns:
            pdf["created_dt"] = pd.to_datetime(pdf["created_at"], errors="coerce")
            pdf["period"] = pdf["created_dt"].dt.strftime("%b")
            periods_list = list(dict.fromkeys(pdf["period"].dropna().tolist()))[-6:]
            if not periods_list:
                periods_list = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]

            opened_by_period = []
            merged_by_period = []
            is_merged_mask = pdf.get("is_merged", pd.Series([False]*len(pdf))).fillna(False)

            for p in periods_list:
                p_mask = pdf["period"] == p
                opened_by_period.append(int(p_mask.sum()))
                merged_by_period.append(int((p_mask & is_merged_mask).sum()))

            st.plotly_chart(
                create_pr_dual_bar_chart(periods_list, opened_by_period, merged_by_period),
                use_container_width=True,
            )
        else:
            render_empty_state("No PR Dates", "PR created timestamps not present.")
    else:
        render_empty_state("No Pull Requests", "Ingest PRs to view statistics.")

# ── BOTTOM: Technology Stack Footer ───────────────────────────────────
render_tech_stack_footer()
