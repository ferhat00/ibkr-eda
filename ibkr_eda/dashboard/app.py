"""Flask application factory and API routes for the trade dashboard."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, render_template, request

from ibkr_eda.dashboard import data_loader, metrics

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


def _apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Apply query-string filters to the DataFrame."""
    args = request.args

    start = args.get("start_date")
    if start:
        df = df[df["trade_time"].dt.normalize() >= pd.Timestamp(start, tz="UTC")]

    end = args.get("end_date")
    if end:
        df = df[df["trade_time"].dt.normalize() <= pd.Timestamp(end, tz="UTC")]

    for param, col in [
        ("exchange", "exchange"),
        ("sec_type", "sec_type"),
        ("currency", "currency"),
        ("country", "country"),
        ("side", "side"),
    ]:
        vals = args.get(param)
        if vals:
            val_list = [v.strip() for v in vals.split(",") if v.strip()]
            if val_list:
                df = df[df[col].isin(val_list)]

    symbol = args.get("symbol")
    if symbol:
        df = df[df["symbol"].str.contains(symbol, case=False, na=False)]

    return df


def _require_data():
    """Get DataFrame or return error response."""
    df = data_loader.get_df()
    if df is None:
        return None, (jsonify({"error": "no_data", "message": "No data loaded. Click Reload."}), 503)
    return df, None


def create_app(data_source: str = "csv", csv_path: str | None = None) -> Flask:
    """Create and configure the Flask dashboard application."""
    app = Flask(
        __name__,
        template_folder=str(TEMPLATE_DIR),
        static_folder=str(STATIC_DIR),
    )
    app.config["DATA_SOURCE"] = data_source
    app.config["CSV_PATH"] = csv_path

    # --- Page routes ---

    @app.route("/")
    def index():
        return render_template("index.html")

    # --- API routes ---

    @app.route("/api/status")
    def api_status():
        status = data_loader.get_status()
        if not status["loaded"]:
            # Auto-load on first access
            try:
                if app.config["DATA_SOURCE"] == "live":
                    data_loader.load_from_flex()
                else:
                    data_loader.load_from_csv(app.config["CSV_PATH"])
                status = data_loader.get_status()
            except Exception as e:
                logger.exception("Auto-load failed")
                status["error"] = str(e)
        return jsonify(status)

    @app.route("/api/reload", methods=["POST"])
    def api_reload():
        body = request.get_json(silent=True) or {}
        source = body.get("source", "csv")
        try:
            if source == "live":
                df = data_loader.load_from_flex()
            else:
                df = data_loader.load_from_csv(body.get("csv_path"))
            return jsonify({"ok": True, "message": f"Loaded {len(df)} rows from {source}."})
        except Exception as e:
            logger.exception("Reload failed")
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.route("/api/summary")
    def api_summary():
        df, err = _require_data()
        if err:
            return err
        return jsonify(metrics.compute_summary(_apply_filters(df)))

    @app.route("/api/charts/cumulative-pnl")
    def api_cumulative_pnl():
        df, err = _require_data()
        if err:
            return err
        return jsonify(metrics.compute_cumulative_pnl(_apply_filters(df)))

    @app.route("/api/charts/pnl-distribution")
    def api_pnl_distribution():
        df, err = _require_data()
        if err:
            return err
        return jsonify(metrics.compute_pnl_distribution(_apply_filters(df)))

    @app.route("/api/charts/symbol-breakdown")
    def api_symbol_breakdown():
        df, err = _require_data()
        if err:
            return err
        top_n = request.args.get("top_n", 25, type=int)
        return jsonify(metrics.compute_symbol_breakdown(_apply_filters(df), top_n))

    @app.route("/api/charts/time-patterns")
    def api_time_patterns():
        df, err = _require_data()
        if err:
            return err
        return jsonify(metrics.compute_time_patterns(_apply_filters(df)))

    @app.route("/api/charts/commission")
    def api_commission():
        df, err = _require_data()
        if err:
            return err
        return jsonify(metrics.compute_commission_analysis(_apply_filters(df)))

    @app.route("/api/charts/market-breakdown")
    def api_market_breakdown():
        df, err = _require_data()
        if err:
            return err
        return jsonify(metrics.compute_market_breakdown(_apply_filters(df)))

    @app.route("/api/trades")
    def api_trades():
        df, err = _require_data()
        if err:
            return err
        filtered = _apply_filters(df)
        page = request.args.get("page", 1, type=int)
        page_size = request.args.get("page_size", 50, type=int)
        sort_by = request.args.get("sort_by", "trade_time")
        sort_dir = request.args.get("sort_dir", "desc")
        return jsonify(metrics.compute_trade_table(filtered, page, page_size, sort_by, sort_dir))

    return app
