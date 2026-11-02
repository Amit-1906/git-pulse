"""
GitPulse Reference-Matched Plotly Chart Library v3.0
Implements exact color palettes, spline curves, donut center text, and dual-bar grouped charts from reference.
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
    margin=dict(l=24, r=20, t=32, b=24),
    xaxis=dict(
        gridcolor="#1e293b",
        zerolinecolor="#1e293b",
        linecolor="#2e3e58",
        showline=True,
        tickfont=dict(size=10, color="#94a3b8"),
    ),
    yaxis=dict(
        gridcolor="#1e293b",
        zerolinecolor="#1e293b",
        linecolor="#2e3e58",
        showline=True,
        tickfont=dict(size=10, color="#94a3b8"),
    ),
    legend=dict(
        bgcolor="rgba(11,19,41,0.75)",
        bordercolor="#1e293b",
        borderwidth=1,
        font=dict(size=10, color="#f8fafc"),
    ),
)

_CYAN = "#38bdf8"
_BLUE = "#2563eb"
_BLUE_LIGHT = "#60a5fa"
_VIOLET = "#8b5cf6"
_PURPLE = "#a855f7"
_GREEN = "#10b981"
_AMBER = "#f59e0b"
_ROSE = "#f43f5e"
_MUTED = "#64748b"


def _layout(**overrides) -> dict:
    base = dict(_THEME)
    base.update(overrides)
    return base


def create_commit_activity_reference_chart(
    dates: List[str],
    commits: List[int],
) -> go.Figure:
    """Reference-matched Commit Activity Over Time line/area chart with cyan/blue gradient."""
    if not dates:
        return _empty_figure("No commit history available")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=commits,
            name="Commits",
            mode="lines+markers",
            line=dict(color=_CYAN, width=2.5, shape="spline"),
            marker=dict(size=5, color=_CYAN, line=dict(color="#ffffff", width=1)),
            fill="tozeroy",
            fillcolor="rgba(37, 99, 235, 0.25)",
        )
    )
    fig.update_layout(
        **_layout(
            title=dict(text="Commit Activity Over Time", font=dict(color="#f8fafc", size=12)),
            hovermode="x unified",
            showlegend=False,
            margin=dict(l=30, r=20, t=30, b=30),
        )
    )
    return fig


def create_contributors_reference_bar(
    names: List[str],
    commits: List[int],
) -> go.Figure:
    """Reference-matched Top Contributors horizontal bar chart with rainbow-like pastel palette."""
    if not names:
        return _empty_figure("No contributor metrics available")

    colors = [
        "#38bdf8",  # Cyan
        "#60a5fa",  # Sky
        "#818cf8",  # Indigo
        "#a855f7",  # Purple
        "#fbbf24",  # Amber
        "#f97316",  # Orange
        "#34d399",  # Emerald
        "#f43f5e",  # Rose
    ][: len(names)]

    fig = go.Figure(
        go.Bar(
            x=commits,
            y=names,
            orientation="h",
            marker=dict(
                color=colors,
                line=dict(color="#1e293b", width=0.5),
            ),
            text=[f"{v:,}" for v in commits],
            textposition="auto",
            textfont=dict(color="#f8fafc", size=10),
        )
    )
    fig.update_layout(
        **_layout(
            title=dict(text="Top Contributors", font=dict(color="#f8fafc", size=12)),
            yaxis=dict(autorange="reversed", gridcolor="#1e293b"),
            xaxis=dict(title="", gridcolor="#1e293b"),
            margin=dict(l=70, r=20, t=30, b=20),
        )
    )
    return fig


def create_issue_donut_reference_chart(
    open_cnt: int,
    closed_cnt: int,
    total_issues_label: str = "1.8K",
) -> go.Figure:
    """Reference-matched Issue Status Distribution donut chart with center text."""
    total = open_cnt + closed_cnt
    if total == 0:
        return _empty_figure("No issue metrics available")

    # If all issues are closed or open, provide structured segmentation
    labels = ["Open", "Closed"]
    values = [open_cnt, closed_cnt]
    colors = [_CYAN, _GREEN]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.68,
                marker=dict(
                    colors=colors,
                    line=dict(color="#070c18", width=2.5),
                ),
                textinfo="percent",
                hoverinfo="label+value+percent",
            )
        ]
    )
    fig.add_annotation(
        text=f"<b>{total_issues_label}</b><br><span style='font-size:10px; color:#94a3b8;'>Issues</span>",
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(color="#ffffff", size=14),
    )
    fig.update_layout(
        **_layout(
            title=dict(text="Issue Status Distribution", font=dict(color="#f8fafc", size=12)),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.08,
                xanchor="center",
                x=0.5,
            ),
            margin=dict(l=15, r=15, t=30, b=30),
        )
    )
    return fig


def create_pr_dual_bar_chart(
    periods: List[str],
    opened_counts: List[int],
    merged_counts: List[int],
) -> go.Figure:
    """Reference-matched Pull Request Statistics dual-column bar chart (Opened in Purple, Merged in Cyan)."""
    if not periods:
        return _empty_figure("No PR volume records")

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=periods,
            y=opened_counts,
            name="Opened",
            marker=dict(color=_PURPLE, line=dict(color="#1e293b", width=0.5)),
        )
    )
    fig.add_trace(
        go.Bar(
            x=periods,
            y=merged_counts,
            name="Merged",
            marker=dict(color=_CYAN, line=dict(color="#1e293b", width=0.5)),
        )
    )
    fig.update_layout(
        **_layout(
            title=dict(text="Pull Request Statistics", font=dict(color="#f8fafc", size=12)),
            barmode="group",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
            ),
            margin=dict(l=25, r=15, t=30, b=25),
        )
    )
    return fig


# ── Secondary Charts ───────────────────────────────────────────────
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
            line=dict(color=_CYAN, width=2.5, shape="spline"),
            fill="tozeroy",
            fillcolor="rgba(56,189,248,0.12)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=prs,
            name="Pull Requests",
            mode="lines",
            line=dict(color=_PURPLE, width=2.5, shape="spline"),
            fill="tozeroy",
            fillcolor="rgba(168,85,247,0.10)",
        )
    )
    fig.update_layout(
        **_layout(
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
    )
    return fig


def create_pr_status_donut(
    open_cnt: int, merged_cnt: int, closed_cnt: int
) -> go.Figure:
    """Donut breakdown of PR lifecycle resolution states."""
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
                    colors=[_PURPLE, _CYAN, _MUTED],
                    line=dict(color="#070c18", width=2),
                ),
                textinfo="percent",
                hoverinfo="label+value+percent",
            )
        ]
    )
    fig.update_layout(
        **_layout(
            showlegend=True,
            legend=dict(orientation="h", yanchor="top", y=-0.05, xanchor="center", x=0.5),
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
                    line=dict(color="#070c18", width=2),
                ),
                textinfo="percent",
                hoverinfo="label+value+percent",
            )
        ]
    )
    fig.update_layout(
        **_layout(
            showlegend=True,
            legend=dict(orientation="h", yanchor="top", y=-0.05, xanchor="center", x=0.5),
            margin=dict(l=10, r=10, t=20, b=30),
        )
    )
    return fig


def create_contributors_leaderboard(
    names: List[str], commits: List[int]
) -> go.Figure:
    return create_contributors_reference_bar(names, commits)


def create_commits_bar_chart(days: List[str], counts: List[int]) -> go.Figure:
    """Bar chart for daily commit frequency."""
    if not days:
        return _empty_figure("No commit data recorded")

    fig = go.Figure(
        go.Bar(
            x=days,
            y=counts,
            marker_color=_BLUE,
            marker_line=dict(color=_CYAN, width=0.5),
            opacity=0.9,
        )
    )
    fig.update_layout(**_layout(yaxis=dict(title="Commits", gridcolor="#1e293b")))
    return fig


def create_merge_time_histogram(hours_list: List[float]) -> go.Figure:
    """Histogram of pull request merge durations in hours."""
    if not hours_list:
        return _empty_figure("No merged PR records available")

    fig = go.Figure(
        go.Histogram(
            x=hours_list,
            nbinsx=18,
            marker_color=_PURPLE,
            marker_line=dict(color="#070c18", width=0.5),
            opacity=0.88,
        )
    )
    fig.update_layout(
        **_layout(
            xaxis=dict(title="Hours to Merge", gridcolor="#1e293b"),
            yaxis=dict(title="PR Count", gridcolor="#1e293b"),
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
            marker_color=_CYAN,
            marker_line=dict(color="#070c18", width=0.5),
            opacity=0.88,
        )
    )
    fig.update_layout(
        **_layout(
            xaxis=dict(title="Days to Close", gridcolor="#1e293b"),
            yaxis=dict(title="Closed Count", gridcolor="#1e293b"),
        )
    )
    return fig


def create_daily_activity_line(
    dates: List[str],
    values: List[int],
    name: str = "Velocity",
    color: str = _CYAN,
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
            fillcolor="rgba(56,189,248,0.12)",
        )
    )
    fig.update_layout(**_layout(hovermode="x unified", yaxis=dict(gridcolor="#1e293b")))
    return fig


def create_pr_size_distribution(
    categories: List[str], counts: List[int]
) -> go.Figure:
    """Categorical bar breakdown for PR code size."""
    if not categories:
        return _empty_figure("No size data available")

    colors = [_GREEN, _CYAN, _AMBER, _ROSE, _MUTED][: len(categories)]
    fig = go.Figure(
        go.Bar(
            x=counts,
            y=categories,
            orientation="h",
            marker_color=colors,
            marker_line=dict(color="#070c18", width=0.5),
        )
    )
    fig.update_layout(
        **_layout(
            yaxis=dict(autorange="reversed", gridcolor="#1e293b"),
            xaxis=dict(title="PR Count", gridcolor="#1e293b"),
        )
    )
    return fig


def create_resolution_cohort_bar(
    cohort_names: List[str], counts: List[int]
) -> go.Figure:
    """Bar chart for issue resolution cohorts."""
    if not cohort_names:
        return _empty_figure("No cohort metrics")

    colors = [_GREEN, _CYAN, _AMBER, _ROSE, _MUTED][: len(cohort_names)]
    fig = go.Figure(
        go.Bar(
            x=cohort_names,
            y=counts,
            marker_color=colors,
            marker_line=dict(color="#070c18", width=0.5),
        )
    )
    fig.update_layout(**_layout(yaxis=dict(title="Issues", gridcolor="#1e293b")))
    return fig


def create_quality_gauge(pass_rate: float) -> go.Figure:
    """Precision gauge meter for dbt Core data assertions."""
    bar_color = (
        _GREEN if pass_rate >= 90 else (_AMBER if pass_rate >= 75 else _ROSE)
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
                bordercolor="#1e293b",
                steps=[
                    dict(range=[0, 75], color="rgba(244,63,94,0.1)"),
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
    fig.update_layout(**_layout(yaxis=dict(title="Seconds", gridcolor="#1e293b")))
    return fig


def create_repository_issue_distribution_chart(
    repo_names: List[str],
    open_counts: List[int],
    closed_counts: List[int],
) -> go.Figure:
    """Grouped bar chart showing open vs closed issue volume per repository."""
    if not repo_names:
        return _empty_figure("No repository issue telemetry available")

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=repo_names,
            y=open_counts,
            name="Open Issues",
            marker=dict(color=_ROSE, line=dict(color="#070c18", width=0.5)),
        )
    )
    fig.add_trace(
        go.Bar(
            x=repo_names,
            y=closed_counts,
            name="Closed Issues",
            marker=dict(color=_CYAN, line=dict(color="#070c18", width=0.5)),
        )
    )
    fig.update_layout(
        **_layout(
            barmode="group",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(title="Issue Count", gridcolor="#1e293b"),
            xaxis=dict(gridcolor="#1e293b"),
        )
    )
    return fig


def create_issue_label_distribution_chart(
    labels: List[str],
    counts: List[int],
) -> go.Figure:
    """Horizontal bar chart showing issue volume broken down by labels/categories."""
    if not labels:
        return _empty_figure("No labeled issue categories available")

    # Distinct vibrant palette for label categories
    palette = [_AMBER, _CYAN, _PURPLE, _ROSE, _BLUE, _GREEN, "#38bdf8", "#fb7185", "#34d399", "#a78bfa"]
    bar_colors = [palette[i % len(palette)] for i in range(len(labels))]

    fig = go.Figure(
        go.Bar(
            x=counts,
            y=labels,
            orientation="h",
            marker=dict(color=bar_colors, line=dict(color="#070c18", width=0.5)),
            text=counts,
            textposition="auto",
        )
    )
    fig.update_layout(
        **_layout(
            yaxis=dict(autorange="reversed", gridcolor="#1e293b"),
            xaxis=dict(title="Issues Count", gridcolor="#1e293b"),
            margin=dict(l=10, r=20, t=10, b=30),
        )
    )
    return fig


def create_issue_velocity_chart(
    periods: List[str],
    opened_counts: List[int],
    closed_counts: List[int],
) -> go.Figure:
    """Dual-series timeline tracking issue creation vs resolution velocity."""
    if not periods:
        return _empty_figure("No timeline velocity data")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=periods,
            y=opened_counts,
            name="Issues Created",
            mode="lines+markers",
            line=dict(color=_ROSE, width=2.5, shape="spline"),
            marker=dict(size=4, color=_ROSE),
            fill="tozeroy",
            fillcolor="rgba(244,63,94,0.10)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=periods,
            y=closed_counts,
            name="Issues Resolved",
            mode="lines+markers",
            line=dict(color=_CYAN, width=2.5, shape="spline"),
            marker=dict(size=4, color=_CYAN),
            fill="tozeroy",
            fillcolor="rgba(56,189,248,0.10)",
        )
    )
    fig.update_layout(
        **_layout(
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(title="Issues per Interval", gridcolor="#1e293b"),
            xaxis=dict(gridcolor="#1e293b"),
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
