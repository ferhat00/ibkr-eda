"""Allocation page: sector treemap, geographic exposure, currency breakdown."""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

dash.register_page(__name__, path="/allocation", name="Allocation", order=1)

layout = dbc.Container(
    [
        html.H4("Allocation Analysis", className="mb-4"),
        dbc.Row(
            [
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H6("Sector Allocation"),
                    dbc.Spinner(dcc.Graph(id="sector-treemap")),
                ])), md=6),
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H6("Industry Allocation"),
                    dbc.Spinner(dcc.Graph(id="industry-treemap")),
                ])), md=6),
            ],
            className="mb-4",
        ),
        dbc.Row(
            [
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H6("Geographic Exposure"),
                    dbc.Spinner(dcc.Graph(id="geo-chart")),
                ])), md=6),
                dbc.Col(dbc.Card(dbc.CardBody([
                    html.H6("Currency Exposure (USD-converted)"),
                    dbc.Spinner(dcc.Graph(id="currency-chart")),
                ])), md=6),
            ],
            className="mb-4",
        ),
    ],
    fluid=True,
)


@callback(
    [
        Output("sector-treemap", "figure"),
        Output("industry-treemap", "figure"),
        Output("geo-chart", "figure"),
        Output("currency-chart", "figure"),
    ],
    [Input("portfolio-data-loaded", "data"), Input("filter-store", "data")],
)
def update_allocation(data_loaded, filters):
    empty = go.Figure().update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
    if not data_loaded:
        return empty, empty, empty, empty

    try:
        import pandas as pd
        import numpy as np
        from ibkr_eda.dashboard_v2.data.loader import load_stock_trades, apply_filters
        from ibkr_eda.dashboard_v2.data.position_reconstructor import reconstruct_daily_positions
        from ibkr_eda.dashboard_v2.data.price_fetcher import fetch_prices, fetch_sector_info
        from ibkr_eda.dashboard_v2.data.fx_fetcher import fetch_fx_rates
        from ibkr_eda.dashboard_v2.data.portfolio_valuation import compute_asset_weights

        trades = apply_filters(load_stock_trades(), filters)
        positions = reconstruct_daily_positions(trades)

        if positions.empty:
            return empty, empty, empty, empty

        start = positions["date"].min().strftime("%Y-%m-%d")
        end = positions["date"].max().strftime("%Y-%m-%d")

        sym_exch = trades.drop_duplicates("symbol")[["symbol", "exchange"]].values.tolist()
        prices = fetch_prices(sym_exch, start, end)
        currencies = trades["currency"].unique().tolist()
        fx_rates = fetch_fx_rates(currencies, start, end)
        sector_info = fetch_sector_info(sym_exch)

        # Get latest weights
        weights = compute_asset_weights(positions, prices, fx_rates)
        if weights.empty:
            return empty, empty, empty, empty

        latest = weights.iloc[-1]
        latest = latest[latest > 0.001]

        # Sector allocation
        sector_data = []
        industry_data = []
        for sym, w in latest.items():
            info = sector_info.get(sym, {})
            sector_data.append({"symbol": sym, "sector": info.get("sector", "Unknown"), "weight": w})
            industry_data.append({"symbol": sym, "industry": info.get("industry", "Unknown"), "weight": w})

        sector_df = pd.DataFrame(sector_data)
        fig_sector = px.treemap(
            sector_df, path=["sector", "symbol"], values="weight",
            color="sector",
        )
        fig_sector.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                                margin=dict(l=10, r=10, t=10, b=10))

        industry_df = pd.DataFrame(industry_data)
        fig_industry = px.treemap(
            industry_df, path=["industry", "symbol"], values="weight",
            color="industry",
        )
        fig_industry.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                                  margin=dict(l=10, r=10, t=10, b=10))

        # Geographic exposure
        sym_to_country = {sym: sector_info.get(sym, {}).get("country", "Unknown") for sym in latest.index}
        geo_df = pd.DataFrame([
            {"country": sym_to_country.get(s, "Unknown"), "weight": w}
            for s, w in latest.items()
        ])
        geo_agg = geo_df.groupby("country")["weight"].sum().sort_values(ascending=True)
        fig_geo = go.Figure(go.Bar(
            x=geo_agg.values, y=geo_agg.index,
            orientation="h",
            marker_color="#00d4ff",
        ))
        fig_geo.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title="Weight", yaxis_title="",
            margin=dict(l=100, r=20, t=10, b=40),
        )

        # Currency exposure
        sym_to_ccy = dict(zip(
            trades.drop_duplicates("symbol")["symbol"],
            trades.drop_duplicates("symbol")["currency"],
        ))
        ccy_df = pd.DataFrame([
            {"currency": sym_to_ccy.get(s, "USD"), "weight": w}
            for s, w in latest.items()
        ])
        ccy_agg = ccy_df.groupby("currency")["weight"].sum()
        fig_ccy = go.Figure(go.Pie(
            labels=ccy_agg.index, values=ccy_agg.values,
            hole=0.4,
            marker=dict(colors=px.colors.qualitative.Set2),
        ))
        fig_ccy.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=10, b=10),
        )

        return fig_sector, fig_industry, fig_geo, fig_ccy

    except Exception as e:
        empty.add_annotation(text=str(e), showarrow=False)
        return empty, empty, empty, empty
