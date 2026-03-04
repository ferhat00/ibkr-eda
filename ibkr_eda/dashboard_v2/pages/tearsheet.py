"""Tearsheet page: pyfolio-style performance analysis in Plotly."""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

dash.register_page(__name__, path="/tearsheet", name="Tearsheet", order=8)

layout = dbc.Container(
    [
        html.H4("Performance Tearsheet", className="mb-4"),

        # Performance stats table
        dbc.Card(dbc.CardBody([
            html.H6("Performance Statistics (pyfolio)"),
            dbc.Spinner(html.Div(id="tearsheet-perf-stats")),
        ]), className="mb-4"),

        # Drawdown table
        dbc.Card(dbc.CardBody([
            html.H6("Top 10 Drawdown Periods"),
            dbc.Spinner(html.Div(id="tearsheet-dd-table")),
        ]), className="mb-4"),

        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Annual Returns"),
                dbc.Spinner(dcc.Graph(id="tearsheet-annual-chart")),
            ])), md=6),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Monthly Returns Distribution"),
                dbc.Spinner(dcc.Graph(id="tearsheet-monthly-dist")),
            ])), md=6),
        ], className="mb-4"),
    ],
    fluid=True,
)


@callback(
    [
        Output("tearsheet-perf-stats", "children"),
        Output("tearsheet-dd-table", "children"),
        Output("tearsheet-annual-chart", "figure"),
        Output("tearsheet-monthly-dist", "figure"),
    ],
    [Input("portfolio-data-loaded", "data"), Input("filter-store", "data")],
)
def update_tearsheet(data_loaded, filters):
    empty = go.Figure().update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
    if not data_loaded:
        return "", "", empty, empty

    try:
        import pandas as pd
        from ibkr_eda.dashboard_v2.pages.overview import _apply_filters
        from ibkr_eda.dashboard_v2.data.loader import load_stock_trades
        from ibkr_eda.dashboard_v2.data.position_reconstructor import reconstruct_daily_positions
        from ibkr_eda.dashboard_v2.data.price_fetcher import fetch_prices
        from ibkr_eda.dashboard_v2.data.fx_fetcher import fetch_fx_rates
        from ibkr_eda.dashboard_v2.data.portfolio_valuation import compute_daily_portfolio
        from ibkr_eda.dashboard_v2.data.benchmark import fetch_benchmark_returns
        from ibkr_eda.dashboard_v2.analytics.pyfolio_bridge import compute_tearsheet_stats

        trades = _apply_filters(load_stock_trades(), filters)
        positions = reconstruct_daily_positions(trades)
        if positions.empty:
            return "No data", "", empty, empty

        start = positions["date"].min().strftime("%Y-%m-%d")
        end = positions["date"].max().strftime("%Y-%m-%d")
        sym_exch = trades.drop_duplicates("symbol")[["symbol", "exchange"]].values.tolist()
        prices = fetch_prices(sym_exch, start, end)
        fx_rates = fetch_fx_rates(trades["currency"].unique().tolist(), start, end)
        portfolio = compute_daily_portfolio(positions, prices, fx_rates)
        port_returns = portfolio["daily_return"].dropna()

        bench = fetch_benchmark_returns(["SPY"], start, end)
        bench_rets = bench["SPY"] if "SPY" in bench.columns else None

        stats = compute_tearsheet_stats(port_returns, bench_rets)

        if "error" in stats:
            return html.P(stats["error"], className="text-warning"), "", empty, empty

        # Perf stats table
        if stats.get("perf_stats"):
            perf_df = pd.DataFrame(
                list(stats["perf_stats"].items()),
                columns=["Metric", "Value"],
            )
            perf_table = dbc.Table.from_dataframe(
                perf_df, striped=True, bordered=True, hover=True, dark=True, size="sm",
            )
        else:
            perf_table = html.P("pyfolio stats unavailable")

        # Drawdown table
        if stats.get("drawdown_table"):
            dd_df = pd.DataFrame(stats["drawdown_table"])
            dd_table = dbc.Table.from_dataframe(
                dd_df, striped=True, bordered=True, hover=True, dark=True, size="sm",
            )
        else:
            dd_table = html.P("No drawdown data")

        # Annual returns bar chart
        fig_annual = empty
        if stats.get("annual_returns"):
            years = list(stats["annual_returns"].keys())
            vals = list(stats["annual_returns"].values())
            colors = ["#00ff88" if v > 0 else "#ff6b6b" for v in vals]
            fig_annual = go.Figure(go.Bar(
                x=[str(y) for y in years], y=vals,
                marker_color=colors,
                text=[f"{v:.1%}" for v in vals],
                textposition="outside",
            ))
            fig_annual.update_layout(
                template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis_tickformat=".0%", yaxis_title="Return",
                margin=dict(l=50, r=20, t=10, b=40),
            )

        # Monthly returns distribution
        fig_monthly = empty
        if stats.get("monthly_returns"):
            m_vals = list(stats["monthly_returns"].values())
            fig_monthly = go.Figure(go.Histogram(
                x=m_vals, nbinsx=20,
                marker_color="#00d4ff",
            ))
            fig_monthly.update_layout(
                template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis_title="Monthly Return", yaxis_title="Count",
                xaxis_tickformat=".0%",
                margin=dict(l=50, r=20, t=10, b=40),
            )

        return perf_table, dd_table, fig_annual, fig_monthly

    except Exception as e:
        return html.P(f"Error: {e}", className="text-danger"), "", empty, empty
