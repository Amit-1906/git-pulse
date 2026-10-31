import streamlit as st
from typing import Optional


def render_metric_card(
    label: str,
    value: str,
    delta: Optional[str] = None,
    delta_subtext: Optional[str] = "vs previous window",
    icon: Optional[str] = None,
):
    """
    Renders a custom GitPulse metric card with dark obsidian backdrop and electric blue/violet glow.
    """
    delta_html = ""
    if delta:
        delta_color = "#3fb950" if not delta.startswith("-") else "#f85149"
        arrow = "↑" if not delta.startswith("-") else "↓"
        delta_html = f"""
        <div class="gp-metric-delta-row">
            <span style="color: {delta_color}; font-weight: 600;">{arrow} {delta}</span>
            <span class="gp-metric-delta-neutral">{delta_subtext}</span>
        </div>
        """

    icon_html = f"<span style='font-size: 1.1rem; margin-right: 0.4rem;'>{icon}</span>" if icon else ""

    html = f"""
    <div class="gp-metric-card">
        <div class="gp-metric-label">{icon_html}{label}</div>
        <div class="gp-metric-value">{value}</div>
        {delta_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_status_pill(status_val: str) -> str:
    """Returns HTML for an enterprise status pill."""
    status_lower = status_val.lower()
    if status_lower in ("completed", "active", "healthy", "open"):
        return f'<span class="gp-badge gp-badge-success">● {status_val.upper()}</span>'
    elif status_lower in ("running", "processing", "extract", "load"):
        return f'<span class="gp-badge gp-badge-running">⚡ {status_val.upper()}</span>'
    elif status_lower in ("warning", "pending", "degraded"):
        return f'<span class="gp-badge gp-badge-warning">▲ {status_val.upper()}</span>'
    else:
        return f'<span class="gp-badge gp-badge-danger">✕ {status_val.upper()}</span>'

