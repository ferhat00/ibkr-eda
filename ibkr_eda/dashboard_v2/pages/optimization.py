"""Optimization page: efficient frontier, optimal portfolios, risk contribution."""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

dash.register_page(__name__, path="/optimization", name="Optimization", order=6)

layout = dbc.Container(
    [
        html.H4("Portfolio Optimization", className="mb-4"),

        dbc.Card(dbc.CardBody([
            html.H6("Efficient Frontier"),
            dbc.Spinner(dcc.Graph(id="efficient-frontier-chart")),
        ]), className="mb-4"),

        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Optimal Portfolio Weights"),
                dbc.Label("Portfolio Type", className="small"),
                dcc.Dropdown(
                    id="opt-portfolio-select",
                    options=[
                        {"label": "Max Sharpe", "value": "Max Sharpe"},
                        {"label": "Min Volatility", "value": "Min Volatility"},
                        {"label": "Risk Parity", "value": "Risk Parity"},
                        {"label": "Max Return", "value": "Max Return"},
                    ],
                    value="Max Sharpe",
                    style={"color": "#000"},
                    className="mb-2",
                ),
                dbc.Spinner(dcc.Graph(id="opt-weights-chart")),
            ])), md=6),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Risk Contribution"),
                dbc.Spinner(dcc.Graph(id="risk-contrib-chart")),
            ])), md=6),
        ], className="mb-4"),

        # Portfolio stats
        dbc.Card(dbc.CardBody([
            html.H6("Optimal Portfolio Statistics"),
            html.Div(id="opt-stats-summary"),
        ]), className="mb-4"),
    ],
    fluid=True,
)


@callback(
    Output("efficient-frontier-chart", "figure"),
    [Input("portfolio-data-loaded", "data"), Input("filter-store", "data")],
)
def update_frontier(data_loaded, filters):
    empty = go.Figure().update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
    if not data_loaded:
        return empty

    try:
        from ibkr_eda.dashboard_v2.data.loader import apply_filters
        from ibkr_eda.dashboard_v2.data.loader import load_stock_trades
        from ibkr_eda.dashboard_v2.data.position_reconstructor import reconstruct_daily_positions
        from ibkr_eda.dashboard_v2.data.price_fetcher import fetch_prices
        from ibkr_eda.dashboard_v2.data.fx_fetcher import fetch_fx_rates
        from ibkr_eda.dashboard_v2.data.portfolio_valuation import compute_asset_returns
        from ibkr_eda.dashboard_v2.analytics.optimization import compute_efficient_frontier

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

        # Filter to assets with enough data
        valid = [c for c in asset_rets.columns if asset_rets[c].dropna().shape[0] >= 60]
        asset_rets = asset_rets[valid].dropna()

        if asset_rets.shape[1] < 2:
            empty.add_annotation(text="Need at least 2 assets with 60+ days of data", showarrow=False)
            return empty

        result = compute_efficient_frontier(asset_rets)
        if "error" in result:
            empty.add_annotation(text=result["error"], showarrow=False)
            return empty

        fig = go.Figure()

        # Frontier line
        if result["frontier"]:
            fig.add_trace(go.Scatter(
                x=[p["risk"] for p in result["frontier"]],
                y=[p["return"] for p in result["frontier"]],
                mode="lines",
                name="Efficient Frontier",
                line=dict(color="#00d4ff", width=2),
            ))

        # Optimal portfolios
        colors = {"Max Sharpe": "#ffd93d", "Min Volatility": "#00ff88",
                  "Risk Parity": "#ff6b6b", "Max Return": "#bb86fc"}
        for name, pdata in result["portfolios"].items():
            fig.add_trace(go.Scatter(
                x=[pdata["annual_vol"]],
                y=[pdata["annual_return"]],
                mode="markers+text",
                name=name,
                marker=dict(size=12, color=colors.get(name, "#888"), symbol="star"),
                text=[name],
                textposition="top center",
                textfont=dict(color=colors.get(name, "#888")),
            ))

        fig.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title="Annual Volatility", yaxis_title="Annual Return",
            xaxis_tickformat=".0%", yaxis_tickformat=".0%",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(l=60, r=20, t=40, b=50),
        )
        return fig

    except Exception as e:
        empty.add_annotation(text=str(e), showarrow=False)
        return empty


@callback(
    [
        Output("opt-weights-chart", "figure"),
        Output("risk-contrib-chart", "figure"),
        Output("opt-stats-summary", "children"),
    ],
    [
        Input("opt-portfolio-select", "value"),
        Input("portfolio-data-loaded", "data"),
        Input("filter-store", "data"),
    ],
)
def update_opt_details(port_type, data_loaded, filters):
    empty = go.Figure().update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
    if not data_loaded:
        return empty, empty, ""

    try:
        from ibkr_eda.dashboard_v2.data.loader import apply_filters
        from ibkr_eda.dashboard_v2.data.loader import load_stock_trades
        from ibkr_eda.dashboard_v2.data.position_reconstructor import reconstruct_daily_positions
        from ibkr_eda.dashboard_v2.data.price_fetcher import fetch_prices
        from ibkr_eda.dashboard_v2.data.fx_fetcher import fetch_fx_rates
        from ibkr_eda.dashboard_v2.data.portfolio_valuation import compute_asset_returns
        from ibkr_eda.dashboard_v2.analytics.optimization import compute_efficient_frontier
        from ibkr_eda.dashboard_v2.analytics.risk_contribution import compute_risk_contribution

        trades = apply_filters(load_stock_trades(), filters)
        positions = reconstruct_daily_positions(trades)
        if positions.empty:
            return empty, empty, "No data"

        start = positions["date"].min().strftime("%Y-%m-%d")
        end = positions["date"].max().strftime("%Y-%m-%d")
        sym_exch = trades.drop_duplicates("symbol")[["symbol", "exchange"]].values.tolist()
        prices = fetch_prices(sym_exch, start, end)
        fx_rates = fetch_fx_rates(trades["currency"].unique().tolist(), start, end)
        asset_rets = compute_asset_returns(positions, prices, fx_rates)

        valid = [c for c in asset_rets.columns if asset_rets[c].dropna().shape[0] >= 60]
        asset_rets = asset_rets[valid].dropna()

        if asset_rets.shape[1] < 2:
            return empty, empty, "Need at least 2 assets"

        result = compute_efficient_frontier(asset_rets)
        if port_type not in result.get("portfolios", {}):
            return empty, empty, f"{port_type} portfolio not available"

        pdata = result["portfolios"][port_type]
        weights = pdata["weights"]

        # Weights bar chart
        sorted_w = dict(sorted(weights.items(), key=lambda x: x[1], reverse=True))
        fig_w = go.Figure(go.Bar(
            x=list(sorted_w.keys()), y=list(sorted_w.values()),
            marker_color="#00d4ff",
            text=[f"{v:.1%}" for v in sorted_w.values()],
            textposition="outside",
        ))
        fig_w.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis_title="Weight", yaxis_tickformat=".0%",
            margin=dict(l=50, r=20, t=10, b=80),
            xaxis_tickangle=-45,
        )

        # Risk contribution
        rc = compute_risk_contribution(asset_rets, weights)
        rc = rc[rc["pct_contribution"].abs() > 0.001].sort_values("pct_contribution", ascending=False)
        fig_rc = go.Figure(go.Bar(
            x=rc["asset"], y=rc["pct_contribution"],
            marker_color="#ff6b6b",
            text=[f"{v:.1%}" for v in rc["pct_contribution"]],
            textposition="outside",
        ))
        fig_rc.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis_title="Risk Contribution", yaxis_tickformat=".0%",
            margin=dict(l=50, r=20, t=10, b=80),
            xaxis_tickangle=-45,
        )

        # Stats summary
        summary = html.Div([
            html.P([html.Strong("Annual Return: "), f"{pdata['annual_return']:.2%}"]),
            html.P([html.Strong("Annual Volatility: "), f"{pdata['annual_vol']:.2%}"]),
            html.P([html.Strong("Sharpe Ratio: "), f"{pdata['sharpe']:.3f}"]),
            html.P([html.Strong("Assets: "), str(len(weights))]),
        ])

        return fig_w, fig_rc, summary

    except Exception as e:
        return empty, empty, html.P(f"Error: {e}", className="text-danger")
