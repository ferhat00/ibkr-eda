"""Dash application factory – multi-page portfolio analytics dashboard."""

from __future__ import annotations

import logging
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
from dash import Dash, dcc, html

logger = logging.getLogger(__name__)

_PAGES_DIR = str(Path(__file__).parent / "pages")


def create_app(csv_path: str | None = None) -> Dash:
    """Create and configure the Dash application."""
    app = Dash(
        __name__,
        use_pages=True,
        pages_folder=_PAGES_DIR,
        external_stylesheets=[dbc.themes.CYBORG, dbc.icons.FONT_AWESOME],
        suppress_callback_exceptions=True,
        title="IBKR Portfolio Analytics",
        update_title="Loading...",
    )

    # Store the CSV path for data loading
    app.server.config["CSV_PATH"] = csv_path

    from ibkr_eda.dashboard_v2.components.navbar import create_navbar
    from ibkr_eda.dashboard_v2.components.filters import create_filter_sidebar

    app.layout = dbc.Container(
        [
            # Global data stores
            dcc.Store(id="filter-store", data={}, storage_type="session"),
            dcc.Store(id="portfolio-data-loaded", data=False),

            # Navbar
            create_navbar(),

            # Main content with sidebar
            dbc.Row(
                [
                    # Filter sidebar
                    dbc.Col(
                        create_filter_sidebar(),
                        width=2,
                        className="bg-dark p-3",
                        style={"minHeight": "calc(100vh - 56px)", "overflowY": "auto"},
                    ),
                    # Page content
                    dbc.Col(
                        [
                            dbc.Spinner(
                                dash.page_container,
                                color="primary",
                                spinner_style={"width": "3rem", "height": "3rem"},
                            ),
                        ],
                        width=10,
                        className="p-4",
                    ),
                ],
                className="g-0",
            ),
        ],
        fluid=True,
        className="px-0",
    )

    # Register filter callbacks
    from ibkr_eda.dashboard_v2.components.filters import register_filter_callbacks
    register_filter_callbacks(app)

    return app
