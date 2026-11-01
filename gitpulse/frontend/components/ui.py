"""
GitPulse Enterprise UI Component Framework
Reference-matched visual components, architecture diagrams, KPI cards, and section layouts.
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
        st.session_state["selected_repo"] = "All Repositories"


def render_page_header(
    title: str,
    subtitle: str,
    icon: str = "⚡",
    scope: Optional[str] = None,
) -> None:
    """Standardized hero header with breadcrumb scope and branding."""
    scope_str = scope or st.session_state.get(
        "selected_repo", "All Repositories"
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


def render_ref_kpi_card(
    label: str,
    value: str,
    delta: Optional[str] = None,
    icon: str = "📊",
    color: str = "blue",
) -> None:
    """Reference-image matched KPI metric card with icon container, large metric, and delta."""
    color_map = {
        "blue": {
            "bg": "rgba(37, 99, 235, 0.22)",
            "border": "rgba(56, 189, 248, 0.4)",
            "shadow": "rgba(37, 99, 235, 0.35)",
        },
        "purple": {
            "bg": "rgba(168, 85, 247, 0.22)",
            "border": "rgba(168, 85, 247, 0.4)",
            "shadow": "rgba(168, 85, 247, 0.35)",
        },
        "rose": {
            "bg": "rgba(244, 63, 94, 0.22)",
            "border": "rgba(244, 63, 94, 0.4)",
            "shadow": "rgba(244, 63, 94, 0.35)",
        },
        "emerald": {
            "bg": "rgba(16, 185, 129, 0.22)",
            "border": "rgba(16, 185, 129, 0.4)",
            "shadow": "rgba(16, 185, 129, 0.35)",
        },
    }
    c_info = color_map.get(color, color_map["blue"])

    delta_html = ""
    if delta is not None:
        delta_html = f'<span class="gp-ref-kpi-delta">↑ {delta}</span>'

    st.markdown(
        f"""
        <div class="gp-ref-kpi-card">
            <div class="gp-ref-kpi-icon-wrap" style="background: {c_info['bg']}; border: 1px solid {c_info['border']}; box-shadow: 0 0 14px {c_info['shadow']};">
                {icon}
            </div>
            <div class="gp-ref-kpi-content">
                <div class="gp-ref-kpi-label">{label}</div>
                <div class="gp-ref-kpi-val-row">
                    <span class="gp-ref-kpi-value">{value}</span>
                    {delta_html}
                </div>
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
    """Standardized KPI card used across secondary dashboards."""
    icon_html = f'<span style="font-size: 1.1rem; opacity: 0.85;">{icon}</span>' if icon else ""
    delta_html = ""
    if delta is not None:
        is_negative = str(delta).startswith("-")
        arrow = "↓" if is_negative else "↑"
        css_cls = "color: var(--gp-rose-text);" if is_negative else "color: var(--gp-emerald-text);"
        delta_html = f"""
        <div style="display: flex; align-items: center; gap: 0.4rem; margin-top: 0.4rem; font-size: 0.775rem;">
            <span style="{css_cls} font-weight: 600;">{arrow} {delta}</span>
            <span style="color: var(--gp-text-muted);">{delta_subtext}</span>
        </div>
        """

    st.markdown(
        f"""
        <div style="background: linear-gradient(145deg, #0d1527 0%, #0f1930 100%); border: 1px solid var(--gp-border); border-radius: var(--gp-radius-md); padding: 1.1rem 1.25rem; border-top: 2px solid var(--gp-cyan);">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.4rem;">
                <span style="font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--gp-text-secondary);">{label}</span>
                {icon_html}
            </div>
            <div style="font-size: 1.85rem; font-weight: 700; color: #ffffff; letter-spacing: -0.03em; line-height: 1.15;">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_system_architecture_banner() -> None:
    """Renders the reference-matched 6-stage System Architecture pipeline banner."""
    st.markdown(
        """
        <div class="gp-architecture-banner">
            <div class="gp-arch-title-row">
                <div class="gp-arch-title">
                    <span style="background: rgba(56, 189, 248, 0.2); border: 1px solid var(--gp-border-cyan); padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.8rem; color: var(--gp-cyan);">System Architecture</span>
                    <span>End-to-End ELT Pipeline for GitHub Data</span>
                </div>
                <div class="gp-arch-steps-flow">
                    <span class="gp-arch-step-indicator">Extract</span> ➔
                    <span class="gp-arch-step-indicator">Load</span> ➔
                    <span class="gp-arch-step-indicator">Transform</span> ➔
                    <span class="gp-arch-step-indicator">Validate</span> ➔
                    <span class="gp-arch-step-indicator">Analyse</span>
                </div>
            </div>
            <div class="gp-pipeline-stages-grid">
                <!-- 1. Data Source -->
                <div class="gp-stage-card gp-stage-card-blue">
                    <span class="gp-stage-num-badge" style="background: #2563eb;">1</span>
                    <div class="gp-stage-title">Data Source</div>
                    <div class="gp-stage-subtitle">GitHub REST API</div>
                    <ul class="gp-stage-points">
                        <li>Repository Meta</li>
                        <li>Commit Logs</li>
                        <li>Issues Backlog</li>
                        <li>Pull Requests</li>
                    </ul>
                    <div class="gp-stage-pill" style="color: #60a5fa;">Public & Private</div>
                </div>

                <!-- 2. Extraction Layer -->
                <div class="gp-stage-card gp-stage-card-teal">
                    <span class="gp-stage-num-badge" style="background: #14b8a6;">2</span>
                    <div class="gp-stage-title">Extraction Layer</div>
                    <div class="gp-stage-subtitle">Python Engine</div>
                    <ul class="gp-stage-points">
                        <li>Automatic Paging</li>
                        <li>Incremental Sync</li>
                        <li>Retry / Backoff</li>
                        <li>Rate-Limit Guard</li>
                    </ul>
                    <div class="gp-stage-pill" style="color: #2dd4bf;">Robust & Scalable</div>
                </div>

                <!-- 3. Raw Data Storage -->
                <div class="gp-stage-card gp-stage-card-violet">
                    <span class="gp-stage-num-badge" style="background: #8b5cf6;">3</span>
                    <div class="gp-stage-title">Raw Storage</div>
                    <div class="gp-stage-subtitle">PostgreSQL Bronze</div>
                    <ul class="gp-stage-points">
                        <li>JSONB Payloads</li>
                        <li>Raw API Storage</li>
                        <li>Extraction Logs</li>
                        <li>Timestamp Hashes</li>
                    </ul>
                    <div class="gp-stage-pill" style="color: #c084fc;">Bronze Tier</div>
                </div>

                <!-- 4. Transformation Layer -->
                <div class="gp-stage-card gp-stage-card-orange">
                    <span class="gp-stage-num-badge" style="background: #f97316;">4</span>
                    <div class="gp-stage-title">Transformation</div>
                    <div class="gp-stage-subtitle">dbt Core Engine</div>
                    <ul class="gp-stage-points">
                        <li>Staging Models</li>
                        <li>Lifecycle Duration</li>
                        <li>Commit Facts</li>
                        <li>Repo Dimensions</li>
                    </ul>
                    <div class="gp-stage-pill" style="color: #fb923c;">Silver / Gold</div>
                </div>

                <!-- 5. Data Quality Validation -->
                <div class="gp-stage-card gp-stage-card-rose">
                    <span class="gp-stage-num-badge" style="background: #f43f5e;">5</span>
                    <div class="gp-stage-title">Data Quality</div>
                    <div class="gp-stage-subtitle">dbt Test Suite</div>
                    <ul class="gp-stage-points">
                        <li>Unique Checks</li>
                        <li>Not-Null Asserts</li>
                        <li>Accepted Values</li>
                        <li>Ref Relationships</li>
                    </ul>
                    <div class="gp-stage-pill" style="color: #fb7185;">Reliable & Trusted</div>
                </div>

                <!-- 6. Analytics & Presentation -->
                <div class="gp-stage-card gp-stage-card-cyan">
                    <span class="gp-stage-num-badge" style="background: #06b6d4;">6</span>
                    <div class="gp-stage-title">Presentation</div>
                    <div class="gp-stage-subtitle">Streamlit + Plotly</div>
                    <ul class="gp-stage-points">
                        <li>Interactive Charts</li>
                        <li>Commit Velocity</li>
                        <li>Contributor Roster</li>
                        <li>PR Merge Analytics</li>
                    </ul>
                    <div class="gp-stage-pill" style="color: #38bdf8;">Actionable Insights</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_tech_stack_footer() -> None:
    """Renders the reference-matched Technology Stack footer bar."""
    st.markdown(
        """
        <div class="gp-tech-stack-bar">
            <div class="gp-tech-badge-title">
                <span>⚡ Technology Stack:</span>
            </div>
            <div class="gp-tech-badges-list">
                <div class="gp-tech-badge-item">🐍 <strong>Python</strong></div>
                <div class="gp-tech-badge-item">🐙 <strong>GitHub REST API</strong></div>
                <div class="gp-tech-badge-item">🐘 <strong>PostgreSQL</strong></div>
                <div class="gp-tech-badge-item">🧱 <strong>dbt Core</strong></div>
                <div class="gp-tech-badge-item">👑 <strong>Streamlit</strong></div>
                <div class="gp-tech-badge-item">📊 <strong>Plotly</strong></div>
                <div class="gp-tech-badge-item">🐳 <strong>Docker</strong></div>
                <div class="gp-tech-badge-item">📦 <strong>Git</strong></div>
            </div>
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
    return f'<span class="gp-badge {cls_name}">{icon} {status.upper()}</span>'


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
