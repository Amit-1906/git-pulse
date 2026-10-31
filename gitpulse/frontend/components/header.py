import streamlit as st


def render_header(title: str, subtitle: str, current_repo: str = "All Repositories"):
    """
    Renders the standardized GitPulse enterprise header banner.
    """
    repo_badge = f"""
    <div style="display: flex; align-items: center; gap: 0.5rem; background: rgba(47, 129, 247, 0.1); border: 1px solid rgba(88, 166, 255, 0.3); padding: 0.4rem 0.8rem; border-radius: 8px;">
        <span style="color: #58a6ff; font-size: 0.85rem;">📁 Scope:</span>
        <span style="color: #f0f6fc; font-weight: 600; font-size: 0.85rem;">{current_repo}</span>
    </div>
    """

    st.markdown(
        f"""
        <div class="gp-header-container">
            <div class="gp-header-title-group">
                <h1>{title}</h1>
                <p>{subtitle}</p>
            </div>
            <div>
                {repo_badge}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

