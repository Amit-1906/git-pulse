"""
GitPulse Chart Library
All Plotly charts use the GitPulse dark design system tokens.
"""
import plotly.graph_objects as go
from typing import List, Optional

# ---------------------------------------------------------------------------
# Shared theme layout applied to every chart
# ---------------------------------------------------------------------------
_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#8b949e", family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif", size=12),
    margin=dict(l=24, r=24, t=40, b=24),
    xaxis=dict(gridcolor="#21262d", zerolinecolor="#21262d", linecolor="#30363d", showline=True),
    yaxis=dict(gridcolor="#21262d", zerolinecolor="#21262d", linecolor="#30363d", showline=True),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="#21262d", borderwidth=1),
)

_BLUE = "#2f81f7"
_BLUE_LIGHT = "#58a6ff"
_VIOLET = "#8b5cf6"
_GREEN = "#3fb950"
_AMBER = "#d29922"
_RED = "#f85149"
_TEAL = "#39d353"
_MUTED = "#6e7681"


def _layout(**overrides) -> dict:
    """Return merged theme layout with caller overrides."""
    base = dict(_THEME)
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Overview charts
# ---------------------------------------------------------------------------
def create_activity_area_chart(
    dates: List[str],
    commits: List[int],
    prs: List[int],
) -> go.Figure:
    """Dual-area chart: commit & PR velocity over time."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=commits, name="Commits", mode="lines",
        line=dict(color=_BLUE_LIGHT, width=2),
        fill="tozeroy", fillcolor="rgba(88,166,255,0.12)",
    ))
    fig.add_trace(go.Scatter(
        x=dates, y=prs, name="Pull Requests", mode="lines",
        line=dict(color=_VIOLET, width=2),
        fill="tozeroy", fillcolor="rgba(139,92,246,0.10)",
    ))
    fig.update_layout(**_layout(
        title="Repository Activity Velocity",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    bgcolor="rgba(0,0,0,0)"),
    ))
    return fig


def create_pr_status_donut(open_cnt: int, merged_cnt: int, closed_cnt: int) -> go.Figure:
    """Donut chart for PR state distribution."""
    total = open_cnt + merged_cnt + closed_cnt
    if total == 0:
        return _empty_figure("No PR data available")
    fig = go.Figure(data=[go.Pie(
        labels=["Merged", "Open", "Closed (unmerged)"],
        values=[merged_cnt, open_cnt, closed_cnt],
        hole=0.62,
        marker=dict(colors=[_VIOLET, _BLUE_LIGHT, _MUTED], line=dict(color="#0d1117", width=2)),
        textinfo="label+percent",
        hoverinfo="label+value",
    )])
    fig.update_layout(**_layout(title="Pull Request State Distribution", showlegend=False))
    return fig


def create_issue_state_donut(open_cnt: int, closed_cnt: int) -> go.Figure:
    """Donut chart for issue open/closed distribution."""
    total = open_cnt + closed_cnt
    if total == 0:
        return _empty_figure("No issue data available")
    fig = go.Figure(data=[go.Pie(
        labels=["Open", "Closed"],
        values=[open_cnt, closed_cnt],
        hole=0.62,
        marker=dict(colors=[_AMBER, _GREEN], line=dict(color="#0d1117", width=2)),
        textinfo="label+percent",
        hoverinfo="label+value",
    )])
    fig.update_layout(**_layout(title="Issue State Distribution", showlegend=False))
    return fig


def create_contributors_leaderboard(names: List[str], commits: List[int]) -> go.Figure:
    """Horizontal bar leaderboard for contributors."""
    if not names:
        return _empty_figure("No contributor data")
    fig = go.Figure(go.Bar(
        x=commits, y=names, orientation="h",
        marker=dict(
            color=commits,
            colorscale=[[0, _BLUE], [1, _VIOLET]],
            line=dict(color=_BLUE_LIGHT, width=0.5),
        ),
    ))
    fig.update_layout(**_layout(
        title="Top Contributors — Commit Volume",
        yaxis=dict(autorange="reversed", gridcolor="#21262d"),
        xaxis_title="Commits",
    ))
    return fig


def create_commits_bar_chart(days: List[str], counts: List[int]) -> go.Figure:
    """Bar chart: commit frequency."""
    fig = go.Figure(go.Bar(
        x=days, y=counts,
        marker_color=_BLUE,
        marker_line=dict(color=_BLUE_LIGHT, width=0.5),
        opacity=0.85,
    ))
    fig.update_layout(**_layout(title="Commit Frequency"))
    return fig


def create_repo_comparison_bar(
    repo_names: List[str],
    values: List[int],
    title: str = "Repository Comparison",
    color: str = _BLUE,
) -> go.Figure:
    """Vertical bar: compare repos by a metric."""
    if not repo_names:
        return _empty_figure("No repository data")
    fig = go.Figure(go.Bar(
        x=repo_names, y=values,
        marker_color=color,
        marker_line=dict(color=_BLUE_LIGHT, width=0.5),
        opacity=0.85,
    ))
    fig.update_layout(**_layout(title=title))
    return fig


def create_pipeline_latency_chart(run_ids: List[str], durations: List[float]) -> go.Figure:
    fig = go.Figure(go.Scatter(
        x=run_ids, y=durations,
        mode="lines+markers",
        line=dict(color=_GREEN, width=2),
        marker=dict(size=6, color="#238636"),
    ))
    fig.update_layout(**_layout(title="Pipeline Execution Duration (s)", yaxis_title="Duration (s)"))
    return fig


# ---------------------------------------------------------------------------
# PR / Issue analytics
# ---------------------------------------------------------------------------
def create_merge_time_histogram(hours_list: List[float]) -> go.Figure:
    """Histogram of merge-time durations in hours."""
    if not hours_list:
        return _empty_figure("No merge-time data")
    fig = go.Figure(go.Histogram(
        x=hours_list,
        nbinsx=20,
        marker_color=_VIOLET,
        marker_line=dict(color="#0d1117", width=0.5),
        opacity=0.85,
        name="Merge Time",
    ))
    fig.update_layout(**_layout(title="Merge Time Distribution", xaxis_title="Hours", yaxis_title="PR Count"))
    return fig


def create_issue_resolution_histogram(days_list: List[float]) -> go.Figure:
    """Histogram of issue resolution times in days."""
    if not days_list:
        return _empty_figure("No resolution data for closed issues")
    fig = go.Figure(go.Histogram(
        x=days_list,
        nbinsx=20,
        marker_color=_TEAL,
        marker_line=dict(color="#0d1117", width=0.5),
        opacity=0.85,
        name="Resolution Time",
    ))
    fig.update_layout(**_layout(title="Issue Resolution Time Distribution", xaxis_title="Days", yaxis_title="Issue Count"))
    return fig


def create_daily_activity_line(
    dates: List[str],
    values: List[int],
    name: str = "Activity",
    color: str = _BLUE_LIGHT,
) -> go.Figure:
    """Single-series area/line chart for daily activity."""
    if not dates:
        return _empty_figure("No activity data")
    fig = go.Figure(go.Scatter(
        x=dates, y=values, name=name, mode="lines",
        line=dict(color=color, width=2),
        fill="tozeroy", fillcolor=f"rgba({_hex_to_rgb(color)},0.12)",
    ))
    fig.update_layout(**_layout(title=f"{name} Over Time", hovermode="x unified"))
    return fig


def create_pr_size_distribution(categories: List[str], counts: List[int]) -> go.Figure:
    """Horizontal bar: PR size categories."""
    if not categories:
        return _empty_figure("No PR size data")
    colors = [_GREEN, _BLUE_LIGHT, _AMBER, _RED, "#6e7681"][:len(categories)]
    fig = go.Figure(go.Bar(
        x=counts, y=categories, orientation="h",
        marker_color=colors,
        marker_line=dict(color="#0d1117", width=0.5),
        opacity=0.85,
    ))
    fig.update_layout(**_layout(title="PR Size Distribution", yaxis=dict(autorange="reversed", gridcolor="#21262d")))
    return fig


def create_quality_gauge(pass_rate: float) -> go.Figure:
    """Gauge chart for dbt data quality pass rate."""
    color = _GREEN if pass_rate >= 90 else (_AMBER if pass_rate >= 70 else _RED)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pass_rate,
        number=dict(suffix="%", font=dict(color="#f0f6fc", size=28)),
        gauge=dict(
            axis=dict(range=[0, 100], tickcolor="#8b949e", tickfont=dict(color="#8b949e")),
            bar=dict(color=color, thickness=0.25),
            bgcolor="rgba(0,0,0,0)",
            borderwidth=1,
            bordercolor="#30363d",
            steps=[
                dict(range=[0, 70], color="rgba(248,81,73,0.08)"),
                dict(range=[70, 90], color="rgba(210,153,34,0.08)"),
                dict(range=[90, 100], color="rgba(63,185,80,0.08)"),
            ],
        ),
        title=dict(text="Data Quality Pass Rate", font=dict(color="#8b949e", size=13)),
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#f0f6fc"),
        margin=dict(l=24, r=24, t=40, b=24),
        height=220,
    )
    return fig


def create_resolution_cohort_bar(cohort_names: List[str], counts: List[int]) -> go.Figure:
    """Bar chart for issue resolution cohorts."""
    if not cohort_names:
        return _empty_figure("No cohort data")
    fig = go.Figure(go.Bar(
        x=cohort_names, y=counts,
        marker_color=[_GREEN, _BLUE_LIGHT, _AMBER, _RED, _MUTED][:len(cohort_names)],
        marker_line=dict(color="#0d1117", width=0.5),
        opacity=0.85,
    ))
    fig.update_layout(**_layout(title="Issue Resolution Cohorts"))
    return fig


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
def _empty_figure(message: str = "No data available") -> go.Figure:
    """Return a blank chart with a centred message."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(color="#6e7681", size=14),
    )
    fig.update_layout(**_layout())
    return fig


def _hex_to_rgb(hex_color: str) -> str:
    """Convert #rrggbb to 'r,g,b' string for rgba() usage."""
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"{r},{g},{b}"
    return "88,166,255"
