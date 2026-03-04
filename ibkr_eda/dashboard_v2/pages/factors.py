"""Factors page: Fama-French factor exposure analysis."""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

from ibkr_eda.dashboard_v2.components.metric_card import metric_card

dash.register_page(__name__, path="/factors", name="Factors", order=5)

layout = dbc.Container(
    [
        html.H4("Factor Exposure Analysis", className="mb-4"),

        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Factor Model"),
                dbc.RadioItems(
                    id="ff-model-select",
                    options=[
                        {"label": "3-Factor (Mkt, SMB, HML)", "value": 3},
                        {"label": "5-Factor (+ RMW, CMA)", "value": 5},
                    ],
                    value=3,
                    inline=True,
                    className="mb-3",
                ),
            ])), md=12),
        ], className="mb-3"),

        # Stats cards
        dbc.Row(id="factor-stats-cards", className="mb-4"),

        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Factor Betas"),
                dbc.Spinner(dcc.Graph(id="factor-betas-chart")),
            ])), md=6),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Factor T-Statistics"),
                dbc.Spinner(dcc.Graph(id="factor-tstats-chart")),
            ])), md=6),
        ], className="mb-4"),

        # Regression details
        dbc.Card(dbc.CardBody([
            html.H6("Regression Summary"),
            html.Div(id="factor-regression-summary"),
        ]), className="mb-4"),
    ],
    fluid=True,
)


@callback(
    [
        Output("factor-stats-cards", "children"),
        Output("factor-betas-chart", "figure"),
        Output("factor-tstats-chart", "figure"),
        Output("factor-regression-summary", "children"),
    ],
    [
        Input("portfolio-data-loaded", "data"),
        Input("filter-store", "data"),
        Input("ff-model-select", "value"),
    ],
)
def update_factors(data_loaded, filters, n_factors):
    empty = go.Figure().update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
    if not data_loaded:
        return [], empty, empty, ""

    try:
        from ibkr_eda.dashboard_v2.data.loader import apply_filters
        from ibkr_eda.dashboard_v2.data.loader import load_stock_trades
        from ibkr_eda.dashboard_v2.data.position_reconstructor import reconstruct_daily_positions
        from ibkr_eda.dashboard_v2.data.price_fetcher import fetch_prices
        from ibkr_eda.dashboard_v2.data.fx_fetcher import fetch_fx_rates
        from ibkr_eda.dashboard_v2.data.portfolio_valuation import compute_daily_portfolio
        from ibkr_eda.dashboard_v2.analytics.fama_french import (
            download_ff_factors, compute_factor_exposure,
        )

        trades = apply_filters(load_stock_trades(), filters)
        positions = reconstruct_daily_positions(trades)
        if positions.empty:
            return [], empty, empty, "No data"

        start = positions["date"].min().strftime("%Y-%m-%d")
        end = positions["date"].max().strftime("%Y-%m-%d")
        sym_exch = trades.drop_duplicates("symbol")[["symbol", "exchange"]].values.tolist()
        prices = fetch_prices(sym_exch, start, end)
        fx_rates = fetch_fx_rates(trades["currency"].unique().tolist(), start, end)
        portfolio = compute_daily_portfolio(positions, prices, fx_rates)
        port_returns = portfolio["daily_return"].dropna()

        ff = download_ff_factors(start, end, n_factors=n_factors)
        result = compute_factor_exposure(port_returns, ff)

        if "error" in result:
            return [], empty, empty, html.P(result["error"], className="text-warning")

        # Stats cards
        cards = [
            dbc.Col(metric_card("Alpha (annual)", f"{result['alpha_annualised']:.2%}",
                               f"p={result['alpha_pvalue']:.4f}"), md=3),
            dbc.Col(metric_card("R²", f"{result['r_squared']:.3f}"), md=3),
            dbc.Col(metric_card("Adj R²", f"{result['adj_r_squared']:.3f}"), md=3),
            dbc.Col(metric_card("Observations", str(result['n_observations'])), md=3),
        ]

        # Betas bar chart
        betas = result["betas"]
        colors = ["#00d4ff" if v >= 0 else "#ff6b6b" for v in betas.values()]
        fig_betas = go.Figure(go.Bar(
            x=list(betas.keys()), y=list(betas.values()),
            marker_color=colors,
            text=[f"{v:.3f}" for v in betas.values()],
            textposition="outside",
        ))
        fig_betas.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis_title="Beta", margin=dict(l=50, r=20, t=30, b=40),
        )

        # T-stats bar chart
        tstats = result["t_stats"]
        t_colors = ["#00d4ff" if abs(v) >= 2 else "#888" for v in tstats.values()]
        fig_tstats = go.Figure(go.Bar(
            x=list(tstats.keys()), y=list(tstats.values()),
            marker_color=t_colors,
            text=[f"{v:.2f}" for v in tstats.values()],
            textposition="outside",
        ))
        fig_tstats.add_hline(y=2, line_dash="dash", line_color="green",
                            annotation_text="Significant (t=2)")
        fig_tstats.add_hline(y=-2, line_dash="dash", line_color="green")
        fig_tstats.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis_title="T-Statistic", margin=dict(l=50, r=20, t=30, b=40),
        )

        # Summary
        summary = html.Div([
            html.P([
                html.Strong("Interpretation: "),
                f"The {n_factors}-factor model explains {result['r_squared']:.1%} of portfolio return variance. ",
                f"Alpha is {result['alpha_annualised']:.2%} annualised ",
                f"({'significant' if result['alpha_pvalue'] < 0.05 else 'not significant'} at 5% level).",
            ]),
        ])

        return cards, fig_betas, fig_tstats, summary

    except Exception as e:
        return [], empty, empty, html.P(f"Error: {e}", className="text-danger")
