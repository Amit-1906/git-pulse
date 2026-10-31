"""
Page 9 — Settings & Administration
Manage GitHub authentication tokens, register new repositories, inspect database pools,
and configure ELT pipeline extraction defaults.
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
from services.api_client import api_client

st.set_page_config(
    page_title="GitPulse | Settings",
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
    title="Platform Settings & Administration",
    subtitle="Configure GitHub PAT tokens, register tracked repositories, and inspect storage tiers",
    current_repo=current_repo,
)

# ── 1. GitHub Authentication & API Token ───────────────────────────────────
st.markdown("### 🔑 GitHub Authentication")
gh_status = api_client.get_github_status()
is_auth = gh_status.get("authenticated", False)

col_auth_info, col_auth_form = st.columns([1, 1])

with col_auth_info:
    st.markdown(
        f"""
        <div class="gp-metric-card" style="padding: 1.25rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                <span style="font-weight: 600; color: #f0f6fc;">Connection Status:</span>
                {render_status_pill('active' if is_auth else 'warning')}
            </div>
            <div style="font-size: 0.85rem; color: #8b949e; line-height: 1.6;">
                <div><strong>Token Configured:</strong> <span style="color: {'#3fb950' if gh_status.get('token_configured') else '#d29922'}">{'Yes (Active)' if gh_status.get('token_configured') else 'No (Rate limited to 60 req/h)'}</span></div>
                <div><strong>Active Identity:</strong> <span style="color: #58a6ff;">{gh_status.get('user') or 'Unauthenticated User'}</span></div>
                <div><strong>Masked Token:</strong> <code style="color: #8b949e;">{gh_status.get('token_masked') or 'None'}</code></div>
                <div><strong>Scopes Granted:</strong> <span style="color: #f0f6fc;">{', '.join(gh_status.get('scopes', [])) or 'read:repo, public_repo'}</span></div>
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
                    res = api_client.connect_github(token_input)
                    if res and res.get("authenticated"):
                        st.success("GitHub token verified and saved!")
                        st.rerun()
                    else:
                        st.error("Failed to authenticate token. Please check scopes and expiration.")

st.markdown("---")

# ── 2. Repository Registration ─────────────────────────────────────────────
st.markdown("### 📁 Tracked Repository Registry")
col_reg_form, col_reg_list = st.columns([1, 1.2])

with col_reg_form:
    st.markdown("##### Register New Repository")
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
                    res = api_client.register_repository(repo_name_input.strip())
                    if res:
                        st.success(f"Repository {repo_name_input} registered successfully!")
                        st.rerun()
                    else:
                        st.info("Registration simulated (standalone preview mode).")

with col_reg_list:
    st.markdown("##### Active Repositories")
    repos = api_client.get_repositories()
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
        st.info("No repositories registered.")

st.markdown("---")

# ── 3. Database & Storage Telemetry ────────────────────────────────────────
st.markdown("### 🗄️ Database Architecture & Storage Tiers")
db_status = api_client.get_database_status()
storage = api_client.get_storage_summary()
stats = api_client.get_database_statistics()

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

# Storage Tier Breakdown
tiers = storage.get("tiers", {})
if tiers:
    col_b, col_s, col_o = st.columns(3)
    with col_b:
        b_info = tiers.get("bronze", {})
        st.markdown(
            f"""
            <div style="background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 1rem;">
                <div style="font-weight: 700; color: #d29922; margin-bottom: 0.5rem;">🥉 Bronze Tier (Raw JSONB)</div>
                <div style="font-size: 0.85rem; color: #8b949e;">Tables: {b_info.get('table_count', 0)}</div>
                <div style="font-size: 0.85rem; color: #8b949e;">Payload Records: {b_info.get('total_rows', 0):,}</div>
                <div style="font-size: 0.75rem; color: #6e7681; margin-top: 0.4rem;">{', '.join(b_info.get('tables', []))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_s:
        s_info = tiers.get("silver", {})
        st.markdown(
            f"""
            <div style="background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 1rem;">
                <div style="font-weight: 700; color: #8b949e; margin-bottom: 0.5rem;">🥈 Silver Tier (Clean Entities)</div>
                <div style="font-size: 0.85rem; color: #8b949e;">Tables: {s_info.get('table_count', 0)}</div>
                <div style="font-size: 0.85rem; color: #8b949e;">Normalized Rows: {s_info.get('total_rows', 0):,}</div>
                <div style="font-size: 0.75rem; color: #6e7681; margin-top: 0.4rem;">{', '.join(s_info.get('tables', []))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_o:
        o_info = tiers.get("operational", {})
        st.markdown(
            f"""
            <div style="background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 1rem;">
                <div style="font-weight: 700; color: #58a6ff; margin-bottom: 0.5rem;">⚡ Operational & Audit Tier</div>
                <div style="font-size: 0.85rem; color: #8b949e;">Tables: {o_info.get('table_count', 0)}</div>
                <div style="font-size: 0.85rem; color: #8b949e;">Audit Rows: {o_info.get('total_rows', 0):,}</div>
                <div style="font-size: 0.75rem; color: #6e7681; margin-top: 0.4rem;">{', '.join(o_info.get('tables', []))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
