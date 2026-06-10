"""Price history fetching with local caching.

Primary source: Yahoo Finance via yfinance.
Fallback: Stooq daily CSV (no API key needed).
Downloads are cached under .cache/ so repeated scans on the same day
don't re-hit the network.
"""

import io
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

from . import HISTORY_YEARS

CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"


class DataError(Exception):
    pass


def _cache_path(ticker: str) -> Path:
    return CACHE_DIR / f"{ticker}_{date.today().isoformat()}.csv"


def _from_cache(ticker: str) -> pd.DataFrame | None:
    p = _cache_path(ticker)
    if p.exists():
        df = pd.read_csv(p, index_col=0, parse_dates=True)
        if not df.empty:
            return df
    return None


def _to_cache(ticker: str, df: pd.DataFrame) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    df.to_csv(_cache_path(ticker))


def _fetch_yahoo(ticker: str, years: int) -> pd.DataFrame:
    import yfinance as yf

    df = yf.download(
        ticker,
        period=f"{years}y",
        interval="1d",
        auto_adjust=True,
        progress=False,
    )
    if df is None or df.empty:
        raise DataError(f"Yahoo returned no data for {ticker}")
    # yfinance returns MultiIndex columns for single tickers in newer versions
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    return df


def _fetch_stooq(ticker: str, years: int) -> pd.DataFrame:
    start = date.today() - timedelta(days=int(years * 365.25))
    url = (
        f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d"
        f"&d1={start.strftime('%Y%m%d')}&d2={date.today().strftime('%Y%m%d')}"
    )
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text), parse_dates=["Date"], index_col="Date")
    if df.empty or "Close" not in df.columns:
        raise DataError(f"Stooq returned no data for {ticker}")
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna()


def get_history(ticker: str, years: int = HISTORY_YEARS, use_cache: bool = True) -> pd.DataFrame:
    """Return ~`years` of daily OHLCV for `ticker`, newest row last."""
    if use_cache:
        cached = _from_cache(ticker)
        if cached is not None:
            return cached

    errors = []
    for fetch in (_fetch_yahoo, _fetch_stooq):
        try:
            df = fetch(ticker, years)
            _to_cache(ticker, df)
            return df
        except Exception as e:  # try next source
            errors.append(f"{fetch.__name__}: {e}")
            time.sleep(1)

    raise DataError(f"All data sources failed for {ticker}: {'; '.join(errors)}")


def get_latest_price(ticker: str) -> float:
    """Most recent daily close (today's intraday price if market is open)."""
    df = get_history(ticker)
    return float(df["Close"].iloc[-1])
