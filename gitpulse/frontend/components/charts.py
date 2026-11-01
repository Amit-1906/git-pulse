"""
GitPulse Plotly Chart Library v2.0
Implements dark obsidian design system tokens, crisp margins, and unified tooltips.
"""
from typing import List, Optional
import plotly.graph_objects as go

# Design tokens
_THEME = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(
        color="#94a3b8",
        family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        size=11,
    ),
    margin=dict(l=20, r=20, t=36, b=20),
    xaxis=dict(
        gridcolor="#1f2736",
        zerolinecolor="#1f2736",
        linecolor="#2b364a",
        showline=True,
        tickfont=dict(size=10, color="#94a3b8"),
    ),
    yaxis=dict(
        gridcolor="#1f2736",
        zerolinecolor="#1f2736",
        linecolor="#2b364a",
        showline=True,
        tickfont=dict(size=10, color="#94a3b8"),
    ),
    legend=dict(
        bgcolor="rgba(15,20,30,0.7)",
        bordercolor="#1f2736",
        borderwidth=1,
        font=dict(size=11, color="#f1f5f9"),
    ),
)

_BLUE = "#3b82f6"
_BLUE_LIGHT = "#60a5fa"
_VIOLET = "#8b5cf6"
_GREEN = "#10b981"
_AMBER = "#f59e0b"
_RED = "#ef4444"
_TEAL = "#14b8a6"
_MUTED = "#64748b"


def _layout(**overrides) -> dict:
    base = dict(_THEME)
    base.update(overrides)
    return base


def create_activity_area_chart(
    dates: List[str],
    commits: List[int],
    prs: List[int],
) -> go.Figure:
    """Smooth multi-trace area chart for commit & PR ingestion cadence."""
    if not dates:
        return _empty_figure("No timeline telemetry available")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=commits,
            name="Commits",
            mode="lines",
            line=dict(color=_BLUE_LIGHT, width=2.5, shape="spline"),
            fill="tozeroy",
            fillcolor="rgba(59,130,246,0.12)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=prs,
            name="Pull Requests",
            mode="lines",
            line=dict(color=_VIOLET, width=2.5, shape="spline"),
            fill="tozeroy",
            fillcolor="rgba(139,92,246,0.10)",
        )
    )
    fig.update_layout(
        **_layout(
            hovermode="x unified",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
            ),
        )
    )
    return fig


def create_pr_status_donut(
    open_cnt: int, merged_cnt: int, closed_cnt: int
) -> go.Figure:
    """Modern donut breakdown of PR lifecycle resolution states."""
    total = open_cnt + merged_cnt + closed_cnt
    if total == 0:
        return _empty_figure("No PR data available")

    fig = go.Figure(
        data=[
            go.Pie(
                labels=["Merged", "Open", "Closed (Unmerged)"],
                values=[merged_cnt, open_cnt, closed_cnt],
                hole=0.68,
                marker=dict(
                    colors=[_VIOLET, _BLUE_LIGHT, _MUTED],
                    line=dict(color="#0a0d14", width=2),
                ),
                textinfo="percent",
                hoverinfo="label+value+percent",
            )
        ]
    )
    fig.update_layout(
        **_layout(
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.05,
                xanchor="center",
                x=0.5,
            ),
            margin=dict(l=10, r=10, t=20, b=30),
        )
    )
    return fig


def create_issue_state_donut(open_cnt: int, closed_cnt: int) -> go.Figure:
    """Donut chart for issue state ratio."""
    total = open_cnt + closed_cnt
    if total == 0:
        return _empty_figure("No issue data available")

    fig = go.Figure(
        data=[
            go.Pie(
                labels=["Open Issues", "Resolved / Closed"],
                values=[open_cnt, closed_cnt],
                hole=0.68,
                marker=dict(
                    colors=[_AMBER, _GREEN],
                    line=dict(color="#0a0d14", width=2),
                ),
                textinfo="percent",
                hoverinfo="label+value+percent",
            )
        ]
    )
    fig.update_layout(
        **_layout(
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.05,
                xanchor="center",
                x=0.5,
            ),
            margin=dict(l=10, r=10, t=20, b=30),
        )
    )
    return fig


def create_contributors_leaderboard(
    names: List[str], commits: List[int]
) -> go.Figure:
    """Horizontal bar chart for contributor engagement."""
    if not names:
        return _empty_figure("No contributor metrics available")

    fig = go.Figure(
        go.Bar(
            x=commits,
            y=names,
            orientation="h",
            marker=dict(
                color=commits,
                colorscale=[[0, _BLUE], [1, _VIOLET]],
                line=dict(color="#2b364a", width=0.5),
            ),
        )
    )
    fig.update_layout(
        **_layout(
            yaxis=dict(autorange="reversed", gridcolor="#1f2736"),
            xaxis=dict(title="Attributed Commits", gridcolor="#1f2736"),
            margin=dict(l=80, r=20, t=20, b=20),
        )
    )
    return fig


def create_commits_bar_chart(days: List[str], counts: List[int]) -> go.Figure:
    """Bar chart for daily commit frequency."""
    if not days:
        return _empty_figure("No commit data recorded")

    fig = go.Figure(
        go.Bar(
            x=days,
            y=counts,
            marker_color=_BLUE,
            marker_line=dict(color=_BLUE_LIGHT, width=0.5),
            opacity=0.9,
        )
    )
    fig.update_layout(
        **_layout(
            yaxis=dict(title="Commits", gridcolor="#1f2736"),
            margin=dict(l=30, r=20, t=20, b=30),
        )
    )
    return fig


def create_merge_time_histogram(hours_list: List[float]) -> go.Figure:
    """Histogram of pull request merge durations in hours."""
    if not hours_list:
        return _empty_figure("No merged PR records available")

    fig = go.Figure(
        go.Histogram(
            x=hours_list,
            nbinsx=18,
            marker_color=_VIOLET,
            marker_line=dict(color="#0a0d14", width=0.5),
            opacity=0.88,
        )
    )
    fig.update_layout(
        **_layout(
            xaxis=dict(title="Hours to Merge", gridcolor="#1f2736"),
            yaxis=dict(title="PR Count", gridcolor="#1f2736"),
            margin=dict(l=30, r=20, t=20, b=30),
        )
    )
    return fig


def create_issue_resolution_histogram(days_list: List[float]) -> go.Figure:
    """Histogram of closed issue resolution times in days."""
    if not days_list:
        return _empty_figure("No resolved issues available")

    fig = go.Figure(
        go.Histogram(
            x=days_list,
            nbinsx=16,
            marker_color=_TEAL,
            marker_line=dict(color="#0a0d14", width=0.5),
            opacity=0.88,
        )
    )
    fig.update_layout(
        **_layout(
            xaxis=dict(title="Days to Close", gridcolor="#1f2736"),
            yaxis=dict(title="Closed Count", gridcolor="#1f2736"),
            margin=dict(l=30, r=20, t=20, b=30),
        )
    )
    return fig


def create_daily_activity_line(
    dates: List[str],
    values: List[int],
    name: str = "Velocity",
    color: str = _BLUE_LIGHT,
) -> go.Figure:
    """Single-series smooth line chart."""
    if not dates:
        return _empty_figure("No series data")

    fig = go.Figure(
        go.Scatter(
            x=dates,
            y=values,
            name=name,
            mode="lines+markers",
            line=dict(color=color, width=2.5, shape="spline"),
            marker=dict(size=4, color=color),
            fill="tozeroy",
            fillcolor=f"rgba(96,165,250,0.12)",
        )
    )
    fig.update_layout(
        **_layout(
            hovermode="x unified",
            yaxis=dict(gridcolor="#1f2736"),
            margin=dict(l=30, r=20, t=20, b=30),
        )
    )
    return fig


def create_pr_size_distribution(
    categories: List[str], counts: List[int]
) -> go.Figure:
    """Categorical bar breakdown for PR code size."""
    if not categories:
        return _empty_figure("No size data available")

    colors = [_GREEN, _BLUE_LIGHT, _AMBER, _RED, _MUTED][: len(categories)]
    fig = go.Figure(
        go.Bar(
            x=counts,
            y=categories,
            orientation="h",
            marker_color=colors,
            marker_line=dict(color="#0a0d14", width=0.5),
        )
    )
    fig.update_layout(
        **_layout(
            yaxis=dict(autorange="reversed", gridcolor="#1f2736"),
            xaxis=dict(title="PR Count", gridcolor="#1f2736"),
            margin=dict(l=90, r=20, t=20, b=30),
        )
    )
    return fig


def create_resolution_cohort_bar(
    cohort_names: List[str], counts: List[int]
) -> go.Figure:
    """Bar chart for issue resolution cohorts."""
    if not cohort_names:
        return _empty_figure("No cohort metrics")

    colors = [_GREEN, _BLUE_LIGHT, _AMBER, _RED, _MUTED][: len(cohort_names)]
    fig = go.Figure(
        go.Bar(
            x=cohort_names,
            y=counts,
            marker_color=colors,
            marker_line=dict(color="#0a0d14", width=0.5),
        )
    )
    fig.update_layout(
        **_layout(
            yaxis=dict(title="Issues", gridcolor="#1f2736"),
            margin=dict(l=30, r=20, t=20, b=30),
        )
    )
    return fig


def create_quality_gauge(pass_rate: float) -> go.Figure:
    """Precision gauge meter for dbt Core data assertions."""
    bar_color = (
        _GREEN if pass_rate >= 90 else (_AMBER if pass_rate >= 75 else _RED)
    )
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=pass_rate,
            number=dict(suffix="%", font=dict(color="#f8fafc", size=26)),
            gauge=dict(
                axis=dict(
                    range=[0, 100],
                    tickcolor="#94a3b8",
                    tickfont=dict(color="#94a3b8", size=9),
                ),
                bar=dict(color=bar_color, thickness=0.28),
                bgcolor="rgba(0,0,0,0)",
                borderwidth=1,
                bordercolor="#1f2736",
                steps=[
                    dict(range=[0, 75], color="rgba(239,68,68,0.1)"),
                    dict(range=[75, 90], color="rgba(245,158,11,0.1)"),
                    dict(range=[90, 100], color="rgba(16,185,129,0.1)"),
                ],
            ),
        )
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#f8fafc"),
        margin=dict(l=15, r=15, t=10, b=10),
        height=190,
    )
    return fig


def create_pipeline_latency_chart(
    run_labels: List[str], durations: List[float]
) -> go.Figure:
    """Execution latency curve for recent extraction jobs."""
    if not run_labels:
        return _empty_figure("No execution runs recorded")

    fig = go.Figure(
        go.Scatter(
            x=run_labels,
            y=durations,
            mode="lines+markers",
            line=dict(color=_GREEN, width=2),
            marker=dict(size=5, color=_GREEN),
        )
    )
    fig.update_layout(
        **_layout(
            yaxis=dict(title="Seconds", gridcolor="#1f2736"),
            margin=dict(l=30, r=20, t=20, b=30),
        )
    )
    return fig


def _empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(color="#64748b", size=12),
    )
    fig.update_layout(**_layout(margin=dict(l=10, r=10, t=20, b=20)))
    return fig
