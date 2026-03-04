"""Reusable KPI metric card component."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import html


def metric_card(title: str, value: str, subtitle: str = "", color: str = "primary") -> dbc.Card:
    return dbc.Card(
        dbc.CardBody(
            [
                html.P(title, className="text-muted mb-1 small"),
                html.H4(value, className=f"text-{color} mb-0"),
                html.Small(subtitle, className="text-muted") if subtitle else None,
            ],
            className="p-3",
        ),
        className="h-100",
    )
