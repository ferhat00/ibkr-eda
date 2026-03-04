"""Calendar page: monthly return heatmap and day-of-week box plot."""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
from dash import Input, Output, callback, dcc, html

dash.register_page(__name__, path="/calendar", name="Calendar", order=4)

layout = dbc.Container(
    [
        html.H4("Calendar Returns", className="mb-4"),

        dbc.Card(dbc.CardBody([
            html.H6("Monthly Returns Heatmap"),
            dbc.Spinner(dcc.Graph(id="monthly-heatmap")),
        ]), className="mb-4"),

        dbc.Card(dbc.CardBody([
            html.H6("Returns by Day of Week"),
            dbc.Spinner(dcc.Graph(id="weekday-boxplot")),
        ]), className="mb-4"),
    ],
    fluid=True,
)


@callback(
    [Output("monthly-heatmap", "figure"), Output("weekday-boxplot", "figure")],
    [Input("portfolio-data-loaded", "data"), Input("filter-store", "data")],
)
def update_calendar(data_loaded, filters):
    empty = go.Figure().update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
    if not data_loaded:
        return empty, empty

    try:
        from ibkr_eda.dashboard_v2.pages.overview import _apply_filters
        from ibkr_eda.dashboard_v2.data.loader import load_stock_trades
        from ibkr_eda.dashboard_v2.data.position_reconstructor import reconstruct_daily_positions
        from ibkr_eda.dashboard_v2.data.price_fetcher import fetch_prices
        from ibkr_eda.dashboard_v2.data.fx_fetcher import fetch_fx_rates
        from ibkr_eda.dashboard_v2.data.portfolio_valuation import compute_daily_portfolio
        from ibkr_eda.dashboard_v2.analytics.calendar_returns import (
            monthly_returns, weekly_returns_by_day,
        )

        trades = _apply_filters(load_stock_trades(), filters)
        positions = reconstruct_daily_positions(trades)
        if positions.empty:
            return empty, empty

        start = positions["date"].min().strftime("%Y-%m-%d")
        end = positions["date"].max().strftime("%Y-%m-%d")
        sym_exch = trades.drop_duplicates("symbol")[["symbol", "exchange"]].values.tolist()
        prices = fetch_prices(sym_exch, start, end)
        fx_rates = fetch_fx_rates(trades["currency"].unique().tolist(), start, end)
        portfolio = compute_daily_portfolio(positions, prices, fx_rates)
        port_returns = portfolio["daily_return"].dropna()

        # Monthly heatmap
        monthly = monthly_returns(port_returns)
        month_cols = [c for c in monthly.columns if c != "YTD"]

        # Build heatmap with text annotations
        z_vals = monthly[month_cols].values
        text_vals = [[f"{v:.1%}" if not (v != v) else "" for v in row] for row in z_vals]

        fig_heatmap = go.Figure(go.Heatmap(
            z=z_vals,
            x=month_cols,
            y=[str(y) for y in monthly.index],
            colorscale="RdYlGn",
            zmid=0,
            text=text_vals,
            texttemplate="%{text}",
            textfont={"size": 11},
        ))
        fig_heatmap.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=60, r=20, t=10, b=40),
            yaxis=dict(autorange="reversed"),
        )

        # Day of week box plot
        weekly = weekly_returns_by_day(port_returns)
        fig_box = px.box(
            weekly, x="day_name", y="return",
            color="day_name",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_box.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            xaxis_title="", yaxis_title="Daily Return",
            yaxis_tickformat=".1%",
            margin=dict(l=50, r=20, t=10, b=40),
        )

        return fig_heatmap, fig_box

    except Exception as e:
        empty.add_annotation(text=str(e), showarrow=False)
        return empty, empty
