"""Risk page: rolling metrics, drawdown, Monte Carlo VaR/CVaR."""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

from ibkr_eda.dashboard_v2.components.metric_card import metric_card

dash.register_page(__name__, path="/risk", name="Risk", order=2)

layout = dbc.Container(
    [
        html.H4("Risk Analysis", className="mb-4"),

        # Rolling metrics
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Rolling Sharpe Ratio (63-day)"),
                dbc.Spinner(dcc.Graph(id="rolling-sharpe-chart")),
            ])), md=6),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Rolling Volatility (63-day)"),
                dbc.Spinner(dcc.Graph(id="rolling-vol-chart")),
            ])), md=6),
        ], className="mb-4"),

        # Drawdown
        dbc.Card(dbc.CardBody([
            html.H6("Underwater Chart (Drawdown)"),
            dbc.Spinner(dcc.Graph(id="underwater-chart")),
        ]), className="mb-4"),

        # Top drawdown periods
        dbc.Card(dbc.CardBody([
            html.H6("Top 5 Drawdown Periods"),
            dbc.Spinner(html.Div(id="top-drawdowns-table")),
        ]), className="mb-4"),

        # Monte Carlo
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Monte Carlo Simulation (1-Year Horizon)"),
                dbc.Spinner(dcc.Graph(id="monte-carlo-chart")),
            ])), md=8),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("VaR / CVaR"),
                html.Div(id="mc-var-cards"),
            ])), md=4),
        ], className="mb-4"),
    ],
    fluid=True,
)


@callback(
    [
        Output("rolling-sharpe-chart", "figure"),
        Output("rolling-vol-chart", "figure"),
        Output("underwater-chart", "figure"),
        Output("top-drawdowns-table", "children"),
        Output("monte-carlo-chart", "figure"),
        Output("mc-var-cards", "children"),
    ],
    [Input("portfolio-data-loaded", "data"), Input("filter-store", "data")],
)
def update_risk(data_loaded, filters):
    empty = go.Figure().update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)")
    if not data_loaded:
        return empty, empty, empty, "", empty, ""

    try:
        from ibkr_eda.dashboard_v2.data.loader import apply_filters
        from ibkr_eda.dashboard_v2.data.loader import load_stock_trades
        from ibkr_eda.dashboard_v2.data.position_reconstructor import reconstruct_daily_positions
        from ibkr_eda.dashboard_v2.data.price_fetcher import fetch_prices
        from ibkr_eda.dashboard_v2.data.fx_fetcher import fetch_fx_rates
        from ibkr_eda.dashboard_v2.data.portfolio_valuation import compute_daily_portfolio
        from ibkr_eda.dashboard_v2.analytics.rolling import rolling_sharpe, rolling_volatility
        from ibkr_eda.dashboard_v2.analytics.drawdown import compute_underwater, compute_top_drawdowns
        from ibkr_eda.dashboard_v2.analytics.monte_carlo import simulate

        trades = apply_filters(load_stock_trades(), filters)
        positions = reconstruct_daily_positions(trades)
        if positions.empty:
            return empty, empty, empty, "No data", empty, ""

        start = positions["date"].min().strftime("%Y-%m-%d")
        end = positions["date"].max().strftime("%Y-%m-%d")
        sym_exch = trades.drop_duplicates("symbol")[["symbol", "exchange"]].values.tolist()
        prices = fetch_prices(sym_exch, start, end)
        fx_rates = fetch_fx_rates(trades["currency"].unique().tolist(), start, end)
        portfolio = compute_daily_portfolio(positions, prices, fx_rates)
        port_returns = portfolio["daily_return"].dropna()

        if len(port_returns) < 10:
            return empty, empty, empty, "Insufficient data", empty, ""

        # Rolling Sharpe
        rs = rolling_sharpe(port_returns)
        fig_sharpe = go.Figure(go.Scatter(
            x=rs.index, y=rs.values, mode="lines",
            line=dict(color="#00d4ff", width=1.5),
            fill="tozeroy", fillcolor="rgba(0,212,255,0.1)",
        ))
        fig_sharpe.add_hline(y=0, line_dash="dash", line_color="gray")
        fig_sharpe.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)", yaxis_title="Sharpe Ratio",
            margin=dict(l=50, r=20, t=10, b=40),
        )

        # Rolling Vol
        rv = rolling_volatility(port_returns)
        fig_vol = go.Figure(go.Scatter(
            x=rv.index, y=rv.values, mode="lines",
            line=dict(color="#ffd93d", width=1.5),
            fill="tozeroy", fillcolor="rgba(255,217,61,0.1)",
        ))
        fig_vol.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)", yaxis_title="Annualised Vol",
            yaxis_tickformat=".0%",
            margin=dict(l=50, r=20, t=10, b=40),
        )

        # Underwater
        uw = compute_underwater(port_returns)
        fig_uw = go.Figure(go.Scatter(
            x=uw.index, y=uw.values, mode="lines",
            fill="tozeroy", fillcolor="rgba(255,107,107,0.3)",
            line=dict(color="#ff6b6b", width=1),
        ))
        fig_uw.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)", yaxis_title="Drawdown",
            yaxis_tickformat=".0%",
            margin=dict(l=50, r=20, t=10, b=40),
        )

        # Top drawdowns table
        top_dd = compute_top_drawdowns(port_returns, top_n=5)
        if not top_dd.empty:
            top_dd["depth"] = top_dd["depth"].apply(lambda x: f"{x:.2%}")
            for col in ["start", "trough", "end"]:
                top_dd[col] = top_dd[col].astype(str).str[:10]
            dd_table = dbc.Table.from_dataframe(
                top_dd, striped=True, bordered=True, hover=True, color="dark", size="sm",
            )
        else:
            dd_table = html.P("No drawdown periods found.")

        # Monte Carlo
        mc = simulate(port_returns)
        fig_mc = go.Figure()
        pcts = mc["percentiles"]
        x_range = list(range(len(pcts[50])))

        fig_mc.add_trace(go.Scatter(
            x=x_range, y=pcts[95], mode="lines", name="95th pct",
            line=dict(color="rgba(0,212,255,0.3)"),
        ))
        fig_mc.add_trace(go.Scatter(
            x=x_range, y=pcts[5], mode="lines", name="5th pct",
            fill="tonexty", fillcolor="rgba(0,212,255,0.1)",
            line=dict(color="rgba(0,212,255,0.3)"),
        ))
        fig_mc.add_trace(go.Scatter(
            x=x_range, y=pcts[75], mode="lines", name="75th pct",
            line=dict(color="rgba(0,212,255,0.5)"),
        ))
        fig_mc.add_trace(go.Scatter(
            x=x_range, y=pcts[25], mode="lines", name="25th pct",
            fill="tonexty", fillcolor="rgba(0,212,255,0.15)",
            line=dict(color="rgba(0,212,255,0.5)"),
        ))
        fig_mc.add_trace(go.Scatter(
            x=x_range, y=pcts[50], mode="lines", name="Median",
            line=dict(color="#00d4ff", width=2),
        ))
        fig_mc.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title="Trading Days", yaxis_title="Cumulative Value ($1)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(l=50, r=20, t=30, b=40),
        )

        # VaR cards
        var_cards = html.Div([
            metric_card("VaR (95%)", f"{mc['var_95']:.2%}", "1-Year Horizon", color="warning"),
            html.Br(),
            metric_card("CVaR (95%)", f"{mc['cvar_95']:.2%}", "Expected Shortfall", color="danger"),
            html.Br(),
            metric_card("VaR (99%)", f"{mc['var_99']:.2%}", "1-Year Horizon", color="warning"),
            html.Br(),
            metric_card("CVaR (99%)", f"{mc['cvar_99']:.2%}", "Expected Shortfall", color="danger"),
        ])

        return fig_sharpe, fig_vol, fig_uw, dd_table, fig_mc, var_cards

    except Exception as e:
        empty.add_annotation(text=str(e), showarrow=False)
        return empty, empty, empty, html.P(f"Error: {e}", className="text-danger"), empty, ""
