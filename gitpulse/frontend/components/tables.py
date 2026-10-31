import streamlit as st
import pandas as pd
from typing import List, Dict, Any


def render_repository_table(repos: List[Dict[str, Any]]):
    """Renders a styled table of tracked GitHub repositories."""
    if not repos:
        st.info("No repositories currently registered.")
        return

    df = pd.DataFrame(repos)
    display_cols = [
        "full_name",
        "stargazers_count",
        "forks_count",
        "open_issues_count",
        "language",
        "is_active",
        "last_synced_at",
    ]
    existing_cols = [c for c in display_cols if c in df.columns]
    
    st.dataframe(
        df[existing_cols],
        column_config={
            "full_name": st.column_config.TextColumn("Repository", help="GitHub repo full name"),
            "stargazers_count": st.column_config.NumberColumn("Stars ⭐", format="%d"),
            "forks_count": st.column_config.NumberColumn("Forks 🍴", format="%d"),
            "open_issues_count": st.column_config.NumberColumn("Open Issues ⚠️", format="%d"),
            "language": st.column_config.TextColumn("Language"),
            "is_active": st.column_config.CheckboxColumn("Active"),
            "last_synced_at": st.column_config.DatetimeColumn("Last Sync", format="YYYY-MM-DD HH:mm"),
        },
        use_container_width=True,
        hide_index=True,
    )

