"""Correlation page: interactive heatmap and rolling correlation."""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
from dash import Input, Output, callback, dcc, html

dash.register_page(__name__, path="/correlation", name="Correlation", order=3)

layout = dbc.Container(
    [
        html.H4("Correlation Analysis", className="mb-4"),

        dbc.Card(dbc.CardBody([
            html.H6("Asset Correlation Heatmap"),
            dbc.Spinner(dcc.Graph(id="correlation-heatmap")),
        ]), className="mb-4"),

        dbc.Card(dbc.CardBody([
            html.H6("Rolling Correlation (63-day)"),
            dbc.Label("Select pair", className="small"),
            dcc.Dropdown(id="rolling-corr-pair", style={"color": "#000"}, className="mb-2"),
            dbc.Spinner(dcc.Graph(id="rolling-corr-chart")),
        ]), className="mb-4"),
    ],
    fluid=True,
)


@callback(
    [
        Output("correlation-heatmap", "figure"),
        Output("rolling-corr-pair", "options"),
        Output("rolling-corr-pair", "value"),
    ],
    [Input("portfolio-data-loaded", "data"), Input("filter-store", "data")],
)
def update_correlation(data_loaded, filters):
    empty = go.Figure().update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
    if not data_loaded:
        return empty, [], None

    try:
        from ibkr_eda.dashboard_v2.data.loader import apply_filters
        from ibkr_eda.dashboard_v2.data.loader import load_stock_trades
        from ibkr_eda.dashboard_v2.data.position_reconstructor import reconstruct_daily_positions
        from ibkr_eda.dashboard_v2.data.price_fetcher import fetch_prices
        from ibkr_eda.dashboard_v2.data.fx_fetcher import fetch_fx_rates
        from ibkr_eda.dashboard_v2.data.portfolio_valuation import compute_asset_returns
        from ibkr_eda.dashboard_v2.analytics.correlation import (
            compute_correlation_matrix, compute_rolling_correlation,
        )

        trades = apply_filters(load_stock_trades(), filters)
        positions = reconstruct_daily_positions(trades)
        if positions.empty:
            return empty, [], None

        start = positions["date"].min().strftime("%Y-%m-%d")
        end = positions["date"].max().strftime("%Y-%m-%d")
        sym_exch = trades.drop_duplicates("symbol")[["symbol", "exchange"]].values.tolist()
        prices = fetch_prices(sym_exch, start, end)
        fx_rates = fetch_fx_rates(trades["currency"].unique().tolist(), start, end)
        asset_rets = compute_asset_returns(positions, prices, fx_rates)

        # Filter to assets with enough data
        valid = [c for c in asset_rets.columns if asset_rets[c].dropna().shape[0] >= 30]
        asset_rets = asset_rets[valid]

        if asset_rets.shape[1] < 2:
            return empty, [], None

        # Heatmap
        corr = compute_correlation_matrix(asset_rets)
        fig_heatmap = go.Figure(go.Heatmap(
            z=corr.values,
            x=corr.columns,
            y=corr.index,
            colorscale="RdBu_r",
            zmid=0,
            text=corr.round(2).values,
            texttemplate="%{text}",
            textfont={"size": 9},
        ))
        fig_heatmap.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=80, r=20, t=10, b=80),
            height=500,
        )

        # Rolling correlation pairs
        rolling = compute_rolling_correlation(asset_rets)
        pair_options = [{"label": k, "value": k} for k in rolling.keys()]
        default_pair = pair_options[0]["value"] if pair_options else None

        return fig_heatmap, pair_options, default_pair

    except Exception as e:
        return empty, [], None


@callback(
    Output("rolling-corr-chart", "figure"),
    [
        Input("rolling-corr-pair", "value"),
        Input("portfolio-data-loaded", "data"),
        Input("filter-store", "data"),
    ],
)
def update_rolling_corr(pair, data_loaded, filters):
    empty = go.Figure().update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
    if not data_loaded or not pair:
        return empty

    try:
        from ibkr_eda.dashboard_v2.data.loader import apply_filters
        from ibkr_eda.dashboard_v2.data.loader import load_stock_trades
        from ibkr_eda.dashboard_v2.data.position_reconstructor import reconstruct_daily_positions
        from ibkr_eda.dashboard_v2.data.price_fetcher import fetch_prices
        from ibkr_eda.dashboard_v2.data.fx_fetcher import fetch_fx_rates
        from ibkr_eda.dashboard_v2.data.portfolio_valuation import compute_asset_returns
        from ibkr_eda.dashboard_v2.analytics.correlation import compute_rolling_correlation

        trades = apply_filters(load_stock_trades(), filters)
        positions = reconstruct_daily_positions(trades)
        if positions.empty:
            return empty

        start = positions["date"].min().strftime("%Y-%m-%d")
        end = positions["date"].max().strftime("%Y-%m-%d")
        sym_exch = trades.drop_duplicates("symbol")[["symbol", "exchange"]].values.tolist()
        prices = fetch_prices(sym_exch, start, end)
        fx_rates = fetch_fx_rates(trades["currency"].unique().tolist(), start, end)
        asset_rets = compute_asset_returns(positions, prices, fx_rates)

        rolling = compute_rolling_correlation(asset_rets)
        if pair not in rolling:
            return empty

        series = rolling[pair].dropna()
        fig = go.Figure(go.Scatter(
            x=series.index, y=series.values, mode="lines",
            line=dict(color="#00d4ff", width=1.5),
        ))
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis_title="Correlation", yaxis_range=[-1, 1],
            margin=dict(l=50, r=20, t=10, b=40),
        )
        return fig

    except Exception:
        return empty
