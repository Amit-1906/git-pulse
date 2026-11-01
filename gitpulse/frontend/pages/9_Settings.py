"""
Page 9 — Settings & Administration
Manage GitHub authentication tokens, register new repositories, inspect database pools,
and configure ELT pipeline extraction defaults.
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
from services import cached_api

page_setup("Settings", icon="⚙️")
render_sidebar()

# Page Header
render_page_header(
    title="Settings & Administration",
    subtitle="Configure GitHub PAT tokens, register tracked repositories, and inspect storage tiers",
    icon="⚙️",
)

# Section 1: GitHub Authentication
render_section_header("GitHub Authentication & Identity", "Personal Access Token (PAT) credential management")
gh_status = cached_api.get_github_status()
is_auth = gh_status.get("authenticated", False)

col_auth_info, col_auth_form = st.columns([1, 1.2])

with col_auth_info:
    st.markdown(
        f"""
        <div class="gp-panel">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                <span style="font-weight: 600; color: var(--gp-text-main);">Connection Status:</span>
                {render_status_badge('active' if is_auth else 'warning')}
            </div>
            <div style="font-size: 0.825rem; color: var(--gp-text-secondary); line-height: 1.6;">
                <div><strong>Token Configured:</strong> <span style="color: {'var(--gp-emerald-text)' if gh_status.get('token_configured') else 'var(--gp-amber-text)'}">{'Active' if gh_status.get('token_configured') else 'Unset (Public Quota: 60 req/h)'}</span></div>
                <div><strong>Identity:</strong> <span style="color: var(--gp-blue-hover);">{gh_status.get('user') or 'Unauthenticated User'}</span></div>
                <div><strong>Masked Token:</strong> <code>{gh_status.get('token_masked') or 'None'}</code></div>
                <div><strong>Scopes:</strong> <span style="color: var(--gp-text-main);">{', '.join(gh_status.get('scopes', [])) or 'read:repo, public_repo'}</span></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_auth_form:
    with st.form("github_token_form"):
        token_input = st.text_input(
            "Personal Access Token (PAT)",
            type="password",
            placeholder="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            help="Create a token at GitHub -> Settings -> Developer Settings -> Personal Access Tokens",
        )
        submit_token = st.form_submit_button("💾 Save & Verify Token", type="primary", use_container_width=True)

        if submit_token:
            if not token_input:
                st.warning("Please provide a valid GitHub token.")
            else:
                with st.spinner("Validating token against GitHub API..."):
                    res = cached_api.connect_github(token_input)
                    if res and res.get("authenticated"):
                        st.success("GitHub token verified and saved!")
                        st.rerun()
                    else:
                        st.error("Failed to authenticate token. Please check scopes and expiration.")

# Section 2: Repository Registration
render_section_header("Repository Registry", "Manage repositories actively tracked by the extraction engine")
col_reg_form, col_reg_list = st.columns([1, 1.4])

with col_reg_form:
    st.markdown("<h5 style='color: var(--gp-text-main); font-size: 0.95rem; margin-bottom: 0.5rem;'>Register New Codebase</h5>", unsafe_allow_html=True)
    with st.form("register_repo_form"):
        repo_name_input = st.text_input(
            "Repository Full Name",
            placeholder="owner/repo (e.g. tiangolo/fastapi)",
            help="Target repository identifier in GitHub format",
        )
        fetch_initial = st.checkbox("Fetch initial metadata on registration", value=True)
        submit_repo = st.form_submit_button("➕ Track Repository", type="primary", use_container_width=True)

        if submit_repo:
            if "/" not in repo_name_input or len(repo_name_input.strip().split("/")) != 2:
                st.error("Format must be owner/repository (e.g. facebook/react)")
            else:
                with st.spinner(f"Registering {repo_name_input}..."):
                    res = cached_api.register_repository(repo_name_input.strip())
                    if res:
                        st.success(f"Repository {repo_name_input} registered successfully!")
                        st.rerun()
                    else:
                        st.info("Registration simulated.")

with col_reg_list:
    st.markdown("<h5 style='color: var(--gp-text-main); font-size: 0.95rem; margin-bottom: 0.5rem;'>Active Repositories</h5>", unsafe_allow_html=True)
    repos = cached_api.get_repositories()
    if repos:
        rdf = pd.DataFrame(repos)
        cols = [c for c in ["full_name", "language", "stargazers_count", "is_active"] if c in rdf.columns]
        st.dataframe(
            rdf[cols],
            column_config={
                "full_name": "Repository",
                "language": "Language",
                "stargazers_count": st.column_config.NumberColumn("Stars", format="%d"),
                "is_active": "Active",
            },
            use_container_width=True,
            hide_index=True,
        )
    else:
        render_empty_state("No Repositories", "Register a repository to begin monitoring.")

# Section 3: Database & Storage Tiers
render_section_header("Database Architecture & Storage Tiers", "Relational storage status, table row counts, and data tier allocation")
db_status = cached_api.get_database_status()
storage = cached_api.get_storage_summary()
stats = cached_api.get_database_statistics()

c1, c2, c3, c4 = st.columns(4)
with c1:
    conn_val = "Connected" if db_status.get("connected") else "Standby Mode"
    render_metric_card("DB Connection", conn_val, icon="🔌")
with c2:
    render_metric_card("Engine Dialect", db_status.get("dialect", "postgresql").upper(), icon="🐘")
with c3:
    render_metric_card("Total Table Rows", f"{stats.get('total_records', 0):,}", icon="📊")
with c4:
    render_metric_card("Bronze Payloads", f"{stats.get('bronze_records', 0):,}", icon="🥉")

# Storage Tier Breakdown Cards
tiers = storage.get("tiers", {})
if tiers:
    col_b, col_s, col_o = st.columns(3)
    with col_b:
        b_info = tiers.get("bronze", {})
        st.markdown(
            f"""
            <div class="gp-panel" style="border-top: 3px solid #f59e0b;">
                <div style="font-weight: 700; color: #f59e0b; margin-bottom: 0.4rem;">🥉 Bronze Tier (Raw JSONB)</div>
                <div style="font-size: 0.825rem; color: var(--gp-text-secondary);">Tables: <strong>{b_info.get('table_count', 0)}</strong></div>
                <div style="font-size: 0.825rem; color: var(--gp-text-secondary);">Raw Payloads: <strong>{b_info.get('total_rows', 0):,}</strong></div>
                <div style="font-size: 0.75rem; color: var(--gp-text-muted); margin-top: 0.4rem;">{', '.join(b_info.get('tables', []))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_s:
        s_info = tiers.get("silver", {})
        st.markdown(
            f"""
            <div class="gp-panel" style="border-top: 3px solid #8b5cf6;">
                <div style="font-weight: 700; color: #8b5cf6; margin-bottom: 0.4rem;">🥈 Silver Tier (Clean Entities)</div>
                <div style="font-size: 0.825rem; color: var(--gp-text-secondary);">Tables: <strong>{s_info.get('table_count', 0)}</strong></div>
                <div style="font-size: 0.825rem; color: var(--gp-text-secondary);">Normalized Rows: <strong>{s_info.get('total_rows', 0):,}</strong></div>
                <div style="font-size: 0.75rem; color: var(--gp-text-muted); margin-top: 0.4rem;">{', '.join(s_info.get('tables', []))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_o:
        o_info = tiers.get("operational", {})
        st.markdown(
            f"""
            <div class="gp-panel" style="border-top: 3px solid #3b82f6;">
                <div style="font-weight: 700; color: #60a5fa; margin-bottom: 0.4rem;">⚡ Operational & Audit Tier</div>
                <div style="font-size: 0.825rem; color: var(--gp-text-secondary);">Tables: <strong>{o_info.get('table_count', 0)}</strong></div>
                <div style="font-size: 0.825rem; color: var(--gp-text-secondary);">Audit Records: <strong>{o_info.get('total_rows', 0):,}</strong></div>
                <div style="font-size: 0.75rem; color: var(--gp-text-muted); margin-top: 0.4rem;">{', '.join(o_info.get('tables', []))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
