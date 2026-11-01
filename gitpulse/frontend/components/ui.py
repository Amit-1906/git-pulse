"""
GitPulse Enterprise UI Component Framework
Standardizes page layout, typography, section hierarchy, KPI cards, and state badges.
"""
from pathlib import Path
from typing import Optional
import streamlit as st

_CSS_CACHE: Optional[str] = None


def load_design_system() -> None:
    """Loads and injects the global GitPulse design system CSS once."""
    global _CSS_CACHE
    if _CSS_CACHE is None:
        css_file = Path(__file__).parent.parent / "assets" / "style.css"
        if css_file.exists():
            _CSS_CACHE = css_file.read_text(encoding="utf-8")
        else:
            _CSS_CACHE = ""
    if _CSS_CACHE:
        st.markdown(f"<style>{_CSS_CACHE}</style>", unsafe_allow_html=True)


def page_setup(title: str, icon: str = "⚡") -> None:
    """Sets standard page configuration and injects styling."""
    st.set_page_config(
        page_title=f"GitPulse | {title}",
        page_icon=icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    load_design_system()
    if "selected_repo" not in st.session_state:
        st.session_state["selected_repo"] = "All Monitored Repositories"


def render_page_header(
    title: str,
    subtitle: str,
    icon: str = "⚡",
    scope: Optional[str] = None,
) -> None:
    """Standardized hero header with breadcrumb scope and branding."""
    scope_str = scope or st.session_state.get(
        "selected_repo", "All Monitored Repositories"
    )
    st.markdown(
        f"""
        <div class="gp-page-header">
            <div class="gp-page-header-left">
                <div class="gp-page-header-icon">{icon}</div>
                <div>
                    <h1 class="gp-page-header-title">{title}</h1>
                    <p class="gp-page-header-subtitle">{subtitle}</p>
                </div>
            </div>
            <div class="gp-page-header-badge">
                <span>📁 Scope:</span>
                <strong>{scope_str}</strong>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(title: str, subtitle: Optional[str] = None) -> None:
    """Visual section separator with accent bar and metadata label."""
    sub_html = (
        f'<span class="gp-section-subtitle">— {subtitle}</span>' if subtitle else ""
    )
    st.markdown(
        f"""
        <div class="gp-section-header">
            <div class="gp-section-title-wrap">
                <div class="gp-section-accent-bar"></div>
                <h3 class="gp-section-title">{title}</h3>
                {sub_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(
    label: str,
    value: str,
    delta: Optional[str] = None,
    delta_subtext: Optional[str] = "vs prior run",
    icon: Optional[str] = None,
) -> None:
    """Sleek KPI card with subtle gradient highlight and status deltas."""
    icon_html = f'<span class="gp-kpi-icon">{icon}</span>' if icon else ""
    delta_html = ""
    if delta is not None:
        is_negative = str(delta).startswith("-")
        arrow = "↓" if is_negative else "↑"
        css_cls = (
            "gp-kpi-delta-negative" if is_negative else "gp-kpi-delta-positive"
        )
        delta_html = f"""
        <div class="gp-kpi-footer">
            <span class="{css_cls}">{arrow} {delta}</span>
            <span class="gp-kpi-delta-neutral">{delta_subtext}</span>
        </div>
        """

    st.markdown(
        f"""
        <div class="gp-kpi-card">
            <div class="gp-kpi-top">
                <span class="gp-kpi-label">{label}</span>
                {icon_html}
            </div>
            <div class="gp-kpi-value">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_status_badge(status: str) -> str:
    """Returns HTML for inline status badge."""
    val = str(status).strip().lower()
    if val in ("completed", "success", "healthy", "active", "open", "passed"):
        cls_name = "gp-badge-emerald"
        icon = "●"
    elif val in (
        "running",
        "extracting",
        "loading",
        "transforming",
        "in_progress",
    ):
        cls_name = "gp-badge-blue"
        icon = "⚡"
    elif val in ("warning", "pending", "queued", "degraded"):
        cls_name = "gp-badge-amber"
        icon = "▲"
    else:
        cls_name = "gp-badge-rose"
        icon = "✕"
    return (
        f'<span class="gp-badge {cls_name}">{icon} {status.upper()}</span>'
    )


def render_callout(
    text: str, title: Optional[str] = None, icon: str = "📌"
) -> None:
    """Styled banner for methodological caveats, tips or warnings."""
    title_html = (
        f"<strong style='color: var(--gp-text-main); margin-right: 0.35rem;'>{title}:</strong> "
        if title
        else ""
    )
    st.markdown(
        f"""
        <div class="gp-callout">
            <span class="gp-callout-icon">{icon}</span>
            <div>{title_html}{text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state(
    title: str,
    description: str,
    icon: str = "📭",
) -> None:
    """Clean empty state container when query results are zero."""
    st.markdown(
        f"""
        <div class="gp-empty-state">
            <div class="gp-empty-icon">{icon}</div>
            <h4 class="gp-empty-title">{title}</h4>
            <p class="gp-empty-desc">{description}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
