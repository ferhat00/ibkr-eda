"""Fama-French factor model exposure analysis."""

from __future__ import annotations

import io
import logging
import zipfile

import numpy as np
import pandas as pd
import requests
import statsmodels.api as sm

from ibkr_eda.dashboard_v2.data import cache

logger = logging.getLogger(__name__)

FF3_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_daily_CSV.zip"
FF5_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"


def download_ff_factors(start: str, end: str, n_factors: int = 3) -> pd.DataFrame:
    """Download Fama-French daily factors from Ken French's data library.

    Parameters
    ----------
    n_factors : 3 or 5

    Returns
    -------
    DataFrame indexed by date with columns: Mkt-RF, SMB, HML[, RMW, CMA], RF
    All values are decimal returns (divided by 100 from source).
    """
    ck = cache.cache_key("ff", str(n_factors), start, end)
    cached = cache.load_parquet(ck)
    if cached is not None:
        return cached

    url = FF5_URL if n_factors == 5 else FF3_URL
    logger.info("Downloading Fama-French %d-factor data ...", n_factors)

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        csv_name = zf.namelist()[0]
        with zf.open(csv_name) as f:
            raw = f.read().decode("utf-8")

    # Find the daily data section (skip header lines)
    lines = raw.split("\n")
    data_start = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and stripped[0].isdigit() and len(stripped.split(",")[0].strip()) == 8:
            data_start = i
            break

    if data_start is None:
        raise ValueError("Could not parse Fama-French CSV")

    # Read until we hit a blank line or non-numeric start
    data_lines = []
    for line in lines[data_start:]:
        stripped = line.strip()
        if not stripped or not stripped[0].isdigit():
            break
        data_lines.append(stripped)

    df = pd.read_csv(
        io.StringIO("\n".join(data_lines)),
        header=None,
    )

    # Column names depend on 3 or 5 factor
    if n_factors == 5:
        df.columns = ["date", "Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"]
    else:
        df.columns = ["date", "Mkt-RF", "SMB", "HML", "RF"]

    df["date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m%d")
    df = df.set_index("date")
    df.index = df.index.tz_localize("UTC")

    # Convert from percentage to decimal
    df = df / 100

    # Filter to date range
    df = df.loc[start:end]

    cache.save_parquet(ck, df)
    return df


def compute_factor_exposure(
    portfolio_returns: pd.Series,
    ff_factors: pd.DataFrame,
) -> dict:
    """OLS regression of portfolio excess returns on FF factors.

    Returns
    -------
    dict with keys: alpha, alpha_pvalue, betas, t_stats, r_squared,
    adj_r_squared.
    """
    # Align dates
    aligned = pd.concat([portfolio_returns, ff_factors], axis=1).dropna()
    if len(aligned) < 30:
        return {"error": "Insufficient data for factor regression"}

    y = aligned.iloc[:, 0] - aligned["RF"]  # excess returns
    factor_cols = [c for c in ff_factors.columns if c != "RF"]
    X = sm.add_constant(aligned[factor_cols])

    model = sm.OLS(y, X).fit()

    betas = {col: float(model.params[col]) for col in factor_cols}
    t_stats = {col: float(model.tvalues[col]) for col in factor_cols}

    return {
        "alpha": float(model.params["const"]),
        "alpha_annualised": float(model.params["const"] * 252),
        "alpha_pvalue": float(model.pvalues["const"]),
        "betas": betas,
        "t_stats": t_stats,
        "r_squared": float(model.rsquared),
        "adj_r_squared": float(model.rsquared_adj),
        "n_observations": int(model.nobs),
    }
