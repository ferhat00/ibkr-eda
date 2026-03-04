"""Top navigation bar with page links."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import html


def create_navbar() -> dbc.Navbar:
    return dbc.Navbar(
        dbc.Container(
            [
                dbc.NavbarBrand(
                    [html.I(className="fas fa-chart-line me-2"), "IBKR Portfolio Analytics"],
                    className="fw-bold",
                ),
                dbc.Nav(
                    [
                        dbc.NavLink("Overview", href="/", active="exact"),
                        dbc.NavLink("Allocation", href="/allocation"),
                        dbc.NavLink("Risk", href="/risk"),
                        dbc.NavLink("Correlation", href="/correlation"),
                        dbc.NavLink("Calendar", href="/calendar"),
                        dbc.NavLink("Factors", href="/factors"),
                        dbc.NavLink("Optimization", href="/optimization"),
                        dbc.NavLink("Attribution", href="/attribution"),
                        dbc.NavLink("Tearsheet", href="/tearsheet"),
                        dbc.NavLink("Health", href="/health"),
                    ],
                    navbar=True,
                    className="ms-auto",
                ),
            ],
            fluid=True,
        ),
        color="dark",
        dark=True,
        sticky="top",
        className="mb-0",
    )
