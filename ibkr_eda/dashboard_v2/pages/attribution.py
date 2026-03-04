"""Attribution page: holdings contribution, waterfall chart, risk-return scatter."""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

dash.register_page(__name__, path="/attribution", name="Attribution", order=7)

layout = dbc.Container(
    [
        html.H4("Performance Attribution", className="mb-4"),

        dbc.Card(dbc.CardBody([
            html.H6("Holdings Performance Contribution"),
            dbc.Spinner(dcc.Graph(id="holdings-contrib-chart")),
        ]), className="mb-4"),

        dbc.Card(dbc.CardBody([
            html.H6("P&L Attribution Waterfall"),
            dbc.Spinner(dcc.Graph(id="waterfall-chart")),
        ]), className="mb-4"),

        dbc.Card(dbc.CardBody([
            html.H6("Risk-Return Scatter"),
            dbc.Spinner(dcc.Graph(id="risk-return-scatter")),
        ]), className="mb-4"),
    ],
    fluid=True,
)


@callback(
    [
        Output("holdings-contrib-chart", "figure"),
        Output("waterfall-chart", "figure"),
        Output("risk-return-scatter", "figure"),
    ],
    [Input("portfolio-data-loaded", "data"), Input("filter-store", "data")],
)
def update_attribution(data_loaded, filters):
    empty = go.Figure().update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
    if not data_loaded:
        return empty, empty, empty

    try:
        from ibkr_eda.dashboard_v2.data.loader import apply_filters
        from ibkr_eda.dashboard_v2.data.loader import load_stock_trades
        from ibkr_eda.dashboard_v2.data.position_reconstructor import reconstruct_daily_positions
        from ibkr_eda.dashboard_v2.data.price_fetcher import fetch_prices
        from ibkr_eda.dashboard_v2.data.fx_fetcher import fetch_fx_rates
        from ibkr_eda.dashboard_v2.data.portfolio_valuation import (
            compute_asset_returns, compute_asset_weights,
        )
        from ibkr_eda.dashboard_v2.analytics.attribution import (
            compute_holdings_contribution, compute_waterfall, compute_risk_return_scatter,
        )

        trades = apply_filters(load_stock_trades(), filters)
        positions = reconstruct_daily_positions(trades)
        if positions.empty:
            return empty, empty, empty

        start = positions["date"].min().strftime("%Y-%m-%d")
        end = positions["date"].max().strftime("%Y-%m-%d")
        sym_exch = trades.drop_duplicates("symbol")[["symbol", "exchange"]].values.tolist()
        prices = fetch_prices(sym_exch, start, end)
        fx_rates = fetch_fx_rates(trades["currency"].unique().tolist(), start, end)
        asset_rets = compute_asset_returns(positions, prices, fx_rates)
        weights = compute_asset_weights(positions, prices, fx_rates)

        if weights.empty or asset_rets.empty:
            return empty, empty, empty

        # Holdings contribution
        contrib = compute_holdings_contribution(weights, asset_rets)
        contrib = contrib[contrib.abs() > 0.0001]
        colors = ["#00ff88" if v > 0 else "#ff6b6b" for v in contrib.values]
        fig_contrib = go.Figure(go.Bar(
            x=contrib.index, y=contrib.values,
            marker_color=colors,
            text=[f"{v:.2%}" for v in contrib.values],
            textposition="outside",
        ))
        fig_contrib.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis_title="Contribution to Return", yaxis_tickformat=".1%",
            margin=dict(l=50, r=20, t=10, b=80),
            xaxis_tickangle=-45,
        )

        # Waterfall
        wf = compute_waterfall(contrib, top_n=15)
        wf_colors = []
        for m, v in zip(wf["measure"], wf["values"]):
            if m == "total":
                wf_colors.append("#00d4ff")
            elif v >= 0:
                wf_colors.append("#00ff88")
            else:
                wf_colors.append("#ff6b6b")

        fig_wf = go.Figure(go.Waterfall(
            x=wf["labels"], y=wf["values"],
            measure=wf["measure"],
            connector=dict(line=dict(color="#555")),
            increasing=dict(marker=dict(color="#00ff88")),
            decreasing=dict(marker=dict(color="#ff6b6b")),
            totals=dict(marker=dict(color="#00d4ff")),
            text=[f"{v:.2%}" for v in wf["values"]],
            textposition="outside",
        ))
        fig_wf.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis_title="Contribution", yaxis_tickformat=".1%",
            margin=dict(l=50, r=20, t=10, b=80),
            xaxis_tickangle=-45,
        )

        # Risk-Return scatter
        scatter_data = compute_risk_return_scatter(asset_rets)
        if not scatter_data.empty:
            colors_scatter = ["#00ff88" if r > 0 else "#ff6b6b"
                            for r in scatter_data["annual_return"]]
            fig_scatter = go.Figure(go.Scatter(
                x=scatter_data["annual_vol"],
                y=scatter_data["annual_return"],
                mode="markers+text",
                text=scatter_data["symbol"],
                textposition="top center",
                textfont=dict(size=9, color="#ccc"),
                marker=dict(size=10, color=colors_scatter, opacity=0.8),
            ))
            fig_scatter.add_hline(y=0, line_dash="dash", line_color="gray")
            fig_scatter.update_layout(
                template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis_title="Annual Volatility", yaxis_title="Annual Return",
                xaxis_tickformat=".0%", yaxis_tickformat=".0%",
                margin=dict(l=60, r=20, t=10, b=50),
            )
        else:
            fig_scatter = empty

        return fig_contrib, fig_wf, fig_scatter

    except Exception as e:
        empty.add_annotation(text=str(e), showarrow=False)
        return empty, empty, empty
