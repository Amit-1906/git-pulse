import streamlit as st
from services.api_client import api_client


def render_sidebar():
    """
    Renders the unified enterprise sidebar with repository scope and backend telemetry.
    """
    with st.sidebar:
        # Brand Emblem
        st.markdown(
            """
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1.5rem; padding-bottom: 1rem; border-bottom: 1px solid #21262d;">
                <div style="width: 36px; height: 36px; border-radius: 8px; background: linear-gradient(135deg, #2f81f7 0%, #8b5cf6 100%); display: flex; align-items: center; justify-content: center; font-size: 1.2rem; box-shadow: 0 0 12px rgba(47, 129, 247, 0.4);">
                    ⚡
                </div>
                <div>
                    <div style="font-size: 1.2rem; font-weight: 700; color: #f0f6fc; letter-spacing: -0.02em;">GitPulse</div>
                    <div style="font-size: 0.75rem; color: #8b949e;">GitHub ELT Platform</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Repository Scope Selector
        st.markdown("<p style='font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #8b949e; margin-bottom: 0.5rem;'>Repository Scope</p>", unsafe_allow_html=True)
        repos = api_client.get_repositories()
        repo_options = ["All Monitored Repositories"] + [r["full_name"] for r in repos]

        selected = st.selectbox(
            "Select Target Repository",
            options=repo_options,
            index=0,
            label_visibility="collapsed",
            key="global_repo_selector",
        )
        st.session_state["selected_repo"] = selected

        st.divider()

        # Pipeline Quick Actions
        st.markdown("<p style='font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #8b949e; margin-bottom: 0.5rem;'>Quick Pipeline Actions</p>", unsafe_allow_html=True)
        if st.button("⚡ Run Full ELT Sync", use_container_width=True, type="primary"):
            st.toast("Triggering ELT extraction pipeline...", icon="🚀")
            target_id = 1
            if selected != "All Monitored Repositories":
                matched = [r for r in repos if r["full_name"] == selected]
                if matched:
                    target_id = matched[0]["id"]
            res = api_client.trigger_pipeline(target_id)
            if res:
                st.success("Pipeline sync initiated successfully!")
            else:
                st.info("Pipeline sync queued (standalone preview mode).")

        st.divider()

        # Backend Health Status
        health = api_client.check_health()
        is_connected = health.get("connected", False)
        status_color = "#3fb950" if is_connected else "#d29922"
        status_text = "API Connected (Healthy)" if is_connected else "Standby Mode"

        st.markdown(
            f"""
            <div style="background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 0.8rem; font-size: 0.75rem;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.4rem;">
                    <span style="color: #8b949e;">Backend Status:</span>
                    <span style="color: {status_color}; font-weight: 600;">● {status_text}</span>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.4rem;">
                    <span style="color: #8b949e;">Dialect:</span>
                    <span style="color: #f0f6fc; font-family: monospace;">PostgreSQL</span>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <span style="color: #8b949e;">Version:</span>
                    <span style="color: #58a6ff; font-family: monospace;">v0.1.0</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

