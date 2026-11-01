"""
GitPulse Enterprise Navigation Sidebar
Implements grouped navigation: WORKSPACE, EXPLORATION, OPERATIONS
with repository scoping and live connection status indicators.
"""
from typing import Optional
import streamlit as st
try:
    from services import cached_api
except (ModuleNotFoundError, ImportError):
    from gitpulse.frontend.services import cached_api


def render_sidebar():
    """Renders the reference-styled enterprise navigation sidebar."""
    with st.sidebar:
        # ── TOP: Brand & Logo ──────────────────────────────────────────
        st.markdown(
            """
            <div class="gp-sidebar-brand">
                <div class="gp-brand-icon-wrap">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
                    </svg>
                </div>
                <div>
                    <div class="gp-brand-title">GitPulse</div>
                    <div class="gp-brand-subtitle">GitHub ELT Analytics</div>
                </div>
                <div class="gp-brand-live-pill">LIVE</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── SECTION 1: WORKSPACE ───────────────────────────────────────
        st.markdown(
            '<div class="gp-nav-section-title">WORKSPACE</div>',
            unsafe_allow_html=True,
        )
        st.page_link("pages/1_Overview.py", label="Overview", icon="📊", use_container_width=True)
        st.page_link("pages/2_Repositories.py", label="Repositories", icon="📁", use_container_width=True)
        st.page_link("pages/3_Contributors.py", label="Contributors", icon="👥", use_container_width=True)

        # ── SECTION 2: EXPLORATION ────────────────────────────────────
        st.markdown(
            '<div class="gp-nav-section-title">EXPLORATION</div>',
            unsafe_allow_html=True,
        )
        st.page_link("pages/4_Commits_Explorer.py", label="Commits Explorer", icon="🔨", use_container_width=True)
        st.page_link("pages/5_Pull_Request_Analytics.py", label="Pull Request Analytics", icon="🔀", use_container_width=True)
        st.page_link("pages/6_Issues_Analytics.py", label="Issues Analytics", icon="🐛", use_container_width=True)

        # ── SECTION 3: OPERATIONS ─────────────────────────────────────
        st.markdown(
            '<div class="gp-nav-section-title">OPERATIONS</div>',
            unsafe_allow_html=True,
        )
        st.page_link("pages/7_Pipeline_Monitor.py", label="Pipeline Monitor", icon="⚡", use_container_width=True)
        st.page_link("pages/8_Data_Quality.py", label="Data Quality", icon="🧪", use_container_width=True)
        st.page_link("pages/9_Settings.py", label="Settings", icon="⚙️", use_container_width=True)

        st.markdown('<div class="gp-sidebar-divider"></div>', unsafe_allow_html=True)

        # ── BOTTOM: Scope & Status ────────────────────────────────────
        st.markdown(
            '<div class="gp-nav-section-title">TARGET REPOSITORY</div>',
            unsafe_allow_html=True,
        )
        repos = cached_api.get_repositories()
        repo_options = ["All Repositories"] + [
            r["full_name"] for r in repos if "full_name" in r
        ]

        curr_selected = st.session_state.get("selected_repo", "All Repositories")
        # Migrate old session label if present
        if curr_selected == "All Monitored Repositories":
            curr_selected = "All Repositories"
            st.session_state["selected_repo"] = "All Repositories"

        default_idx = (
            repo_options.index(curr_selected)
            if curr_selected in repo_options
            else 0
        )

        selected = st.selectbox(
            "Target Repository",
            options=repo_options,
            index=default_idx,
            label_visibility="collapsed",
            key="global_repo_selector",
        )
        if selected != st.session_state.get("selected_repo"):
            st.session_state["selected_repo"] = selected
            st.rerun()

        # Quick Actions Row
        col_sync, col_ref = st.columns([2, 1])
        with col_sync:
            if st.button("⚡ Sync ELT", use_container_width=True, type="primary", key="sb_sync_btn"):
                target_id = 1
                if selected != "All Repositories":
                    matched = [r for r in repos if r.get("full_name") == selected]
                    if matched:
                        target_id = matched[0]["id"]
                with st.spinner("Dispatching sync..."):
                    cached_api.trigger_pipeline(target_id)
                    st.toast("Pipeline execution initiated!", icon="🚀")
                    st.rerun()

        with col_ref:
            if st.button("🔄", use_container_width=True, help="Refresh cached telemetry", key="sb_ref_btn"):
                cached_api.clear_all_caches()
                st.rerun()

        # System Health Card
        health = cached_api.check_health()
        gh_status = cached_api.get_github_status()
        is_backend_ok = health.get("connected", False)
        is_gh_ok = gh_status.get("authenticated", False) or gh_status.get("token_configured", False)

        db_color = "#10b981" if is_backend_ok else "#f59e0b"
        db_text = "PostgreSQL: Connected" if is_backend_ok else "PostgreSQL: Standby"

        gh_color = "#10b981" if is_gh_ok else "#38bdf8"
        gh_text = "GitHub API: Connected" if is_gh_ok else "GitHub API: Public Tier"

        st.markdown(
            f"""
            <div class="gp-sidebar-status-card">
                <div class="gp-status-row">
                    <span class="gp-status-dot" style="background-color: {db_color};"></span>
                    <span class="gp-status-text">{db_text}</span>
                </div>
                <div class="gp-status-row">
                    <span class="gp-status-dot" style="background-color: {gh_color};"></span>
                    <span class="gp-status-text">{gh_text}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
