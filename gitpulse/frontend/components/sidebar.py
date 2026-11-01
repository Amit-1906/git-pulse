"""
GitPulse Enterprise Sidebar Navigation & Scope Control
Uses cached queries to eliminate latency on page navigation.
"""
import streamlit as st
from services import cached_api


def render_sidebar():
    """Renders persistent enterprise sidebar with repository scope and telemetry."""
    with st.sidebar:
        # Brand Emblem
        st.markdown(
            """
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1.25rem; padding-bottom: 0.85rem; border-bottom: 1px solid var(--gp-border);">
                <div style="width: 38px; height: 38px; border-radius: 8px; background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%); display: flex; align-items: center; justify-content: center; font-size: 1.25rem; box-shadow: 0 0 16px rgba(37, 99, 235, 0.4);">
                    ⚡
                </div>
                <div>
                    <div style="font-size: 1.15rem; font-weight: 700; color: #f8fafc; letter-spacing: -0.02em;">GitPulse</div>
                    <div style="font-size: 0.75rem; color: #94a3b8;">GitHub ELT Analytics</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Repository Scope
        st.markdown(
            "<p style='font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--gp-text-muted); margin-bottom: 0.35rem;'>Target Repository</p>",
            unsafe_allow_html=True,
        )
        repos = cached_api.get_repositories()
        repo_options = ["All Monitored Repositories"] + [
            r["full_name"] for r in repos if "full_name" in r
        ]

        # Sync selector with session state
        curr_selected = st.session_state.get(
            "selected_repo", "All Monitored Repositories"
        )
        default_idx = (
            repo_options.index(curr_selected)
            if curr_selected in repo_options
            else 0
        )

        selected = st.selectbox(
            "Select Target Repository",
            options=repo_options,
            index=default_idx,
            label_visibility="collapsed",
            key="global_repo_selector",
        )
        st.session_state["selected_repo"] = selected

        st.divider()

        # Quick Actions
        st.markdown(
            "<p style='font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--gp-text-muted); margin-bottom: 0.4rem;'>Orchestration</p>",
            unsafe_allow_html=True,
        )
        col_sync, col_ref = st.columns([2, 1])
        with col_sync:
            if st.button(
                "⚡ Sync ELT",
                use_container_width=True,
                type="primary",
                key="sb_sync_btn",
            ):
                target_id = 1
                if selected != "All Monitored Repositories":
                    matched = [r for r in repos if r.get("full_name") == selected]
                    if matched:
                        target_id = matched[0]["id"]
                with st.spinner("Dispatching sync..."):
                    res = cached_api.trigger_pipeline(target_id)
                    if res:
                        st.toast("Pipeline execution initiated!", icon="🚀")
                    else:
                        st.toast("Pipeline run registered.", icon="⚡")
        with col_ref:
            if st.button(
                "🔄",
                use_container_width=True,
                help="Refresh cached data across all pages",
                key="sb_ref_btn",
            ):
                cached_api.clear_all_caches()
                st.rerun()

        st.divider()

        # Backend Health Telemetry
        health = cached_api.check_health()
        is_connected = health.get("connected", False)
        status_color = "#10b981" if is_connected else "#f59e0b"
        status_text = (
            "Connected (Healthy)" if is_connected else "Standby Mode"
        )

        st.markdown(
            f"""
            <div style="background: var(--gp-surface-elevated); border: 1px solid var(--gp-border); border-radius: 8px; padding: 0.85rem; font-size: 0.775rem;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.4rem;">
                    <span style="color: var(--gp-text-secondary);">Backend:</span>
                    <span style="color: {status_color}; font-weight: 600;">● {status_text}</span>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.4rem;">
                    <span style="color: var(--gp-text-secondary);">Storage Engine:</span>
                    <span style="color: var(--gp-text-main); font-family: monospace;">PostgreSQL</span>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <span style="color: var(--gp-text-secondary);">Release:</span>
                    <span style="color: var(--gp-blue-hover); font-family: monospace;">v1.0.0</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
