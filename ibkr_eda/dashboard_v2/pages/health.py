"""Health check page: portfolio health alerts and risk monitoring."""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

dash.register_page(__name__, path="/health", name="Health", order=9)

layout = dbc.Container(
    [
        html.H4("Portfolio Health Check", className="mb-4"),

        # Overall health score
        dbc.Card(dbc.CardBody([
            html.H6("Health Score"),
            dbc.Spinner(html.Div(id="health-score")),
        ]), className="mb-4"),

        # Risk alerts
        dbc.Card(dbc.CardBody([
            html.H6("Risk Alerts"),
            dbc.Spinner(html.Div(id="risk-alerts")),
        ]), className="mb-4"),

        # Detailed checks
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Concentration Analysis"),
                dbc.Spinner(dcc.Graph(id="concentration-chart")),
            ])), md=6),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Drawdown Monitor"),
                dbc.Spinner(dcc.Graph(id="dd-monitor-chart")),
            ])), md=6),
        ], className="mb-4"),
    ],
    fluid=True,
)


@callback(
    [
        Output("health-score", "children"),
        Output("risk-alerts", "children"),
        Output("concentration-chart", "figure"),
        Output("dd-monitor-chart", "figure"),
    ],
    [Input("portfolio-data-loaded", "data"), Input("filter-store", "data")],
)
def update_health(data_loaded, filters):
    empty = go.Figure().update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
    if not data_loaded:
        return "", "", empty, empty

    try:
        import numpy as np
        import pandas as pd
        from ibkr_eda.dashboard_v2.data.loader import apply_filters
        from ibkr_eda.dashboard_v2.data.loader import load_stock_trades
        from ibkr_eda.dashboard_v2.data.position_reconstructor import reconstruct_daily_positions
        from ibkr_eda.dashboard_v2.data.price_fetcher import fetch_prices
        from ibkr_eda.dashboard_v2.data.fx_fetcher import fetch_fx_rates
        from ibkr_eda.dashboard_v2.data.portfolio_valuation import (
            compute_daily_portfolio, compute_asset_weights,
        )
        from ibkr_eda.dashboard_v2.analytics.drawdown import compute_underwater

        trades = apply_filters(load_stock_trades(), filters)
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
        weights = compute_asset_weights(positions, prices, fx_rates)

        if weights.empty:
            return "No data", "", empty, empty

        latest_w = weights.iloc[-1]
        latest_w = latest_w[latest_w > 0.001]

        # Health checks
        alerts = []
        score = 100

        # 1. Concentration risk (HHI)
        hhi = (latest_w ** 2).sum()
        if hhi > 0.25:
            alerts.append(("danger", "High concentration risk",
                         f"HHI = {hhi:.3f} (>0.25). Portfolio is highly concentrated."))
            score -= 20
        elif hhi > 0.15:
            alerts.append(("warning", "Moderate concentration",
                         f"HHI = {hhi:.3f}. Consider diversifying."))
            score -= 10

        # 2. Single position > 20%
        max_pos = latest_w.max()
        max_sym = latest_w.idxmax()
        if max_pos > 0.20:
            alerts.append(("danger", f"Large position: {max_sym}",
                         f"{max_sym} is {max_pos:.1%} of portfolio. Consider trimming."))
            score -= 15

        # 3. Current drawdown
        if len(port_returns) > 10:
            uw = compute_underwater(port_returns)
            current_dd = uw.iloc[-1]
            if current_dd < -0.20:
                alerts.append(("danger", "Severe drawdown",
                             f"Currently in {current_dd:.1%} drawdown."))
                score -= 20
            elif current_dd < -0.10:
                alerts.append(("warning", "Drawdown alert",
                             f"Currently in {current_dd:.1%} drawdown."))
                score -= 10

        # 4. Volatility check
        if len(port_returns) > 20:
            recent_vol = port_returns.tail(20).std() * np.sqrt(252)
            long_vol = port_returns.std() * np.sqrt(252)
            if recent_vol > long_vol * 1.5:
                alerts.append(("warning", "Elevated volatility",
                             f"Recent vol ({recent_vol:.1%}) is 50%+ above average ({long_vol:.1%})."))
                score -= 10

        # 5. Number of holdings
        n_holdings = len(latest_w)
        if n_holdings < 5:
            alerts.append(("warning", "Low diversification",
                         f"Only {n_holdings} holdings. Consider adding more positions."))
            score -= 10
        elif n_holdings > 30:
            alerts.append(("info", "Many holdings",
                         f"{n_holdings} positions. Consider consolidating."))

        # 6. Win rate check
        if len(port_returns) > 30:
            win_rate = (port_returns > 0).mean()
            if win_rate < 0.45:
                alerts.append(("warning", "Low win rate",
                             f"Daily win rate is {win_rate:.1%}."))
                score -= 5

        score = max(0, min(100, score))

        # Health score display
        if score >= 80:
            score_color = "success"
            score_text = "Healthy"
        elif score >= 60:
            score_color = "warning"
            score_text = "Caution"
        else:
            score_color = "danger"
            score_text = "At Risk"

        score_display = dbc.Row([
            dbc.Col(html.Div([
                html.H1(f"{score}", className=f"text-{score_color} display-3 fw-bold"),
                html.H5(score_text, className=f"text-{score_color}"),
            ], className="text-center"), md=3),
            dbc.Col(html.Div([
                dbc.Progress(
                    value=score, max=100, color=score_color,
                    className="mb-2", style={"height": "30px"},
                ),
                html.P(f"{len(alerts)} alert(s) detected", className="text-muted"),
            ]), md=9),
        ])

        # Alerts display
        alert_items = []
        if not alerts:
            alert_items.append(dbc.Alert("No risk alerts. Portfolio looks healthy!",
                                        color="success"))
        for color, title, detail in alerts:
            alert_items.append(dbc.Alert([
                html.Strong(f"{title}: "), detail
            ], color=color, className="py-2"))

        # Concentration pie chart
        top_w = latest_w.sort_values(ascending=False).head(10)
        if len(latest_w) > 10:
            other = latest_w.sort_values(ascending=False).iloc[10:].sum()
            top_w["Other"] = other
        fig_conc = go.Figure(go.Pie(
            labels=top_w.index, values=top_w.values,
            hole=0.4,
        ))
        fig_conc.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=10, b=10),
        )

        # Drawdown monitor
        if len(port_returns) > 10:
            uw = compute_underwater(port_returns)
            fig_dd = go.Figure(go.Scatter(
                x=uw.index, y=uw.values, mode="lines",
                fill="tozeroy", fillcolor="rgba(255,107,107,0.3)",
                line=dict(color="#ff6b6b", width=1),
            ))
            # Add threshold lines
            fig_dd.add_hline(y=-0.10, line_dash="dash", line_color="yellow",
                           annotation_text="-10%")
            fig_dd.add_hline(y=-0.20, line_dash="dash", line_color="red",
                           annotation_text="-20%")
            fig_dd.update_layout(
                template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis_title="Drawdown", yaxis_tickformat=".0%",
                margin=dict(l=50, r=20, t=10, b=40),
            )
        else:
            fig_dd = empty

        return score_display, html.Div(alert_items), fig_conc, fig_dd

    except Exception as e:
        return (
            html.P(f"Error: {e}", className="text-danger"), "",
            empty, empty,
        )
