"""Overview page: cumulative returns vs benchmarks, key metrics table."""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

from ibkr_eda.dashboard_v2.components.metric_card import metric_card

dash.register_page(__name__, path="/", name="Overview", order=0)

layout = dbc.Container(
    [
        html.H4("Portfolio Overview", className="mb-4"),

        # KPI cards row
        dbc.Row(id="overview-kpi-cards", className="mb-4"),

        # Cumulative returns chart
        dbc.Card(
            dbc.CardBody([
                html.H6("Cumulative Returns vs Benchmarks"),
                dbc.Spinner(dcc.Graph(id="cumulative-returns-chart")),
            ]),
            className="mb-4",
        ),

        # Key metrics table
        dbc.Card(
            dbc.CardBody([
                html.H6("Key Portfolio Metrics"),
                dbc.Spinner(html.Div(id="metrics-table-container")),
            ]),
            className="mb-4",
        ),
    ],
    fluid=True,
)


@callback(
    [
        Output("overview-kpi-cards", "children"),
        Output("cumulative-returns-chart", "figure"),
        Output("metrics-table-container", "children"),
    ],
    [
        Input("portfolio-data-loaded", "data"),
        Input("filter-store", "data"),
    ],
)
def update_overview(data_loaded, filters):
    if not data_loaded:
        empty_fig = go.Figure()
        empty_fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
        return [], empty_fig, html.P("Loading data...")

    import pandas as pd
    from ibkr_eda.dashboard_v2.data.loader import load_stock_trades
    from ibkr_eda.dashboard_v2.data.position_reconstructor import reconstruct_daily_positions
    from ibkr_eda.dashboard_v2.data.price_fetcher import fetch_prices
    from ibkr_eda.dashboard_v2.data.fx_fetcher import fetch_fx_rates
    from ibkr_eda.dashboard_v2.data.portfolio_valuation import compute_daily_portfolio
    from ibkr_eda.dashboard_v2.data.benchmark import fetch_benchmark_returns
    from ibkr_eda.dashboard_v2.analytics.returns_metrics import (
        compute_metrics_table, compute_cumulative_returns,
    )

    try:
        trades = load_stock_trades()
        trades = _apply_filters(trades, filters)

        positions = reconstruct_daily_positions(trades)
        if positions.empty:
            empty_fig = go.Figure()
            empty_fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
            return [], empty_fig, html.P("No positions found.")

        start = positions["date"].min().strftime("%Y-%m-%d")
        end = positions["date"].max().strftime("%Y-%m-%d")

        sym_exch = trades.drop_duplicates("symbol")[["symbol", "exchange"]].values.tolist()
        prices = fetch_prices(sym_exch, start, end)
        currencies = trades["currency"].unique().tolist()
        fx_rates = fetch_fx_rates(currencies, start, end)

        portfolio = compute_daily_portfolio(positions, prices, fx_rates)
        port_returns = portfolio["daily_return"].dropna()

        bench = fetch_benchmark_returns(["SPY", "ACWI"], start, end)

        # KPI cards
        if len(port_returns) > 0:
            import numpy as np
            total_ret = (1 + port_returns).prod() - 1
            ann_vol = port_returns.std() * np.sqrt(252)
            cum = (1 + port_returns).cumprod()
            max_dd = ((cum - cum.cummax()) / cum.cummax()).min()
            sharpe_val = ((total_ret - 0.045) / ann_vol) if ann_vol > 0 else 0

            cards = [
                dbc.Col(metric_card("Total Return", f"{total_ret:.1%}",
                                   color="success" if total_ret > 0 else "danger"), md=2),
                dbc.Col(metric_card("Annual Volatility", f"{ann_vol:.1%}"), md=2),
                dbc.Col(metric_card("Max Drawdown", f"{max_dd:.1%}", color="danger"), md=2),
                dbc.Col(metric_card("Sharpe Ratio", f"{sharpe_val:.2f}"), md=2),
                dbc.Col(metric_card("Trading Days", str(len(port_returns))), md=2),
                dbc.Col(metric_card("Holdings",
                                   str(positions[positions["date"] == positions["date"].max()]["symbol"].nunique())), md=2),
            ]
        else:
            cards = []

        # Cumulative returns chart
        cum_df = compute_cumulative_returns(port_returns, bench)
        fig = go.Figure()
        colors = {"Portfolio": "#00d4ff", "SPY": "#ff6b6b", "ACWI": "#ffd93d"}
        for col in cum_df.columns:
            fig.add_trace(go.Scatter(
                x=cum_df.index, y=cum_df[col],
                name=col, mode="lines",
                line=dict(color=colors.get(col, "#888"), width=2),
            ))
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            yaxis_title="Cumulative Return",
            xaxis_title="",
            margin=dict(l=50, r=20, t=30, b=40),
        )

        # Metrics table
        metrics_df = compute_metrics_table(port_returns, bench)
        table = dbc.Table.from_dataframe(
            metrics_df.reset_index().rename(columns={"index": "Metric"}),
            striped=True, bordered=True, hover=True, dark=True, size="sm",
        )

        return cards, fig, table

    except Exception as e:
        empty_fig = go.Figure()
        empty_fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
        return [], empty_fig, html.P(f"Error: {e}", className="text-danger")


def _apply_filters(trades, filters):
    """Apply global filters to trade data."""
    if not filters:
        return trades
    if filters.get("start_date"):
        trades = trades[trades["trade_time"] >= filters["start_date"]]
    if filters.get("end_date"):
        trades = trades[trades["trade_time"] <= filters["end_date"]]
    if filters.get("tickers"):
        trades = trades[trades["symbol"].isin(filters["tickers"])]
    if filters.get("countries"):
        trades = trades[trades["country"].isin(filters["countries"])]
    return trades
