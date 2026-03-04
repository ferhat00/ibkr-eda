"""Reusable styled DataTable components."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dash_table


DARK_TABLE_STYLE = {
    "style_header": {
        "backgroundColor": "#1a1a2e",
        "color": "#e0e0e0",
        "fontWeight": "bold",
        "border": "1px solid #333",
    },
    "style_cell": {
        "backgroundColor": "#16213e",
        "color": "#e0e0e0",
        "border": "1px solid #333",
        "padding": "8px",
        "textAlign": "right",
        "fontSize": "13px",
    },
    "style_data_conditional": [
        {
            "if": {"row_index": "odd"},
            "backgroundColor": "#1a1a2e",
        },
    ],
}


def styled_table(
    id: str,
    columns: list[dict],
    data: list[dict] | None = None,
    **kwargs,
) -> dash_table.DataTable:
    return dash_table.DataTable(
        id=id,
        columns=columns,
        data=data or [],
        sort_action="native",
        page_size=20,
        **DARK_TABLE_STYLE,
        **kwargs,
    )
