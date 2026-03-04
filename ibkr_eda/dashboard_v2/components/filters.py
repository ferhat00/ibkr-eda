"""Global filter sidebar shared across all pages."""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html


def create_filter_sidebar() -> html.Div:
    return html.Div(
        [
            html.H6("Filters", className="text-uppercase text-muted mb-3"),

            # Date range
            dbc.Label("Date Range", className="small"),
            dcc.DatePickerRange(
                id="filter-date-range",
                display_format="YYYY-MM-DD",
                className="mb-3 w-100",
            ),

            # Ticker multi-select
            dbc.Label("Tickers", className="small"),
            dcc.Dropdown(
                id="filter-tickers",
                multi=True,
                placeholder="All tickers",
                className="mb-3",
                style={"color": "#000"},
            ),

            # Country multi-select
            dbc.Label("Country", className="small"),
            dcc.Dropdown(
                id="filter-countries",
                multi=True,
                placeholder="All countries",
                className="mb-3",
                style={"color": "#000"},
            ),

            # Security type
            dbc.Label("Security Type", className="small"),
            dcc.Dropdown(
                id="filter-sec-types",
                multi=True,
                placeholder="All types",
                className="mb-3",
                style={"color": "#000"},
            ),

            # Apply button
            dbc.Button(
                [html.I(className="fas fa-filter me-2"), "Apply Filters"],
                id="btn-apply-filters",
                color="primary",
                className="w-100 mb-3",
            ),

            html.Hr(),

            # Cache refresh
            dbc.Button(
                [html.I(className="fas fa-sync me-2"), "Refresh Data"],
                id="btn-refresh-data",
                color="secondary",
                outline=True,
                size="sm",
                className="w-100 mb-2",
            ),

            # Status indicator
            html.Div(id="data-status", className="small text-muted mt-2"),
        ],
    )


def register_filter_callbacks(app):
    """Register callbacks for filter management and data loading."""
    from ibkr_eda.dashboard_v2.data.loader import load_stock_trades

    @app.callback(
        [
            Output("filter-tickers", "options"),
            Output("filter-countries", "options"),
            Output("filter-sec-types", "options"),
            Output("filter-date-range", "min_date_allowed"),
            Output("filter-date-range", "max_date_allowed"),
            Output("filter-date-range", "start_date"),
            Output("filter-date-range", "end_date"),
            Output("data-status", "children"),
            Output("portfolio-data-loaded", "data"),
        ],
        [Input("btn-refresh-data", "n_clicks")],
        prevent_initial_call=False,
    )
    def load_initial_data(n_clicks):
        """Load trade data and populate filter options."""
        try:
            csv_path = app.server.config.get("CSV_PATH")
            from ibkr_eda.dashboard_v2.data.loader import load_trades
            df = load_trades(csv_path)
            stk = df[df["sec_type"] == "STK"]

            tickers = sorted(stk["symbol"].unique())
            countries = sorted(stk["country"].unique())
            sec_types = sorted(df["sec_type"].unique())

            date_min = df["trade_time"].min().strftime("%Y-%m-%d")
            date_max = df["trade_time"].max().strftime("%Y-%m-%d")

            status = f"Loaded {len(df)} trades ({len(stk)} STK, {len(tickers)} symbols)"
            return (
                [{"label": t, "value": t} for t in tickers],
                [{"label": c, "value": c} for c in countries],
                [{"label": s, "value": s} for s in sec_types],
                date_min, date_max, date_min, date_max,
                status,
                True,
            )
        except Exception as e:
            return ([], [], [], None, None, None, None, f"Error: {e}", False)

    @app.callback(
        Output("filter-store", "data"),
        Input("btn-apply-filters", "n_clicks"),
        [
            State("filter-date-range", "start_date"),
            State("filter-date-range", "end_date"),
            State("filter-tickers", "value"),
            State("filter-countries", "value"),
            State("filter-sec-types", "value"),
        ],
        prevent_initial_call=True,
    )
    def apply_filters(n_clicks, start_date, end_date, tickers, countries, sec_types):
        return {
            "start_date": start_date,
            "end_date": end_date,
            "tickers": tickers or [],
            "countries": countries or [],
            "sec_types": sec_types or [],
        }
