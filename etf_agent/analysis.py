"""Indicators and buy-timing scores for leveraged ETFs.

Leveraged ETFs (SOXL, TQQQ, ...) decay in choppy markets and crater in
corrections, so the edge historically comes from buying deep drawdowns in
products whose underlying index has a long-run upward drift — not from
chasing strength. The score below is therefore mean-reversion weighted:

  - drawdown from the 5-year high      (40 pts) — the main signal
  - RSI(14) oversold                   (20 pts)
  - price percentile over 5 years      (20 pts) — cheap vs its own range
  - distance below the 200-day SMA     (20 pts)

Score >= 70 -> STRONG BUY zone, 55-69 -> BUY, 40-54 -> WATCH,
25-39 -> HOLD, < 25 -> AVOID (price near highs; worst entry for LETFs).

`historical_edge` then sanity-checks the signal against the same 5 years:
it finds every past day the score was in today's band and reports the
median forward 3/6/12-month returns, so the recommendation comes with
evidence rather than just a label.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

TRADING_DAYS = {"3m": 63, "6m": 126, "12m": 252}


# ---------------------------------------------------------------- indicators

def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100.0)


def drawdown_from_high(close: pd.Series) -> pd.Series:
    """Fractional drawdown from the running all-time high (0 to -1)."""
    return close / close.cummax() - 1


def sma(close: pd.Series, period: int) -> pd.Series:
    return close.rolling(period, min_periods=1).mean()


def price_percentile(close: pd.Series) -> pd.Series:
    """Rank of each close within all history up to that day (0..1)."""
    return close.expanding().rank(pct=True)


# ------------------------------------------------------------------- scoring

def score_series(close: pd.Series) -> pd.Series:
    """Composite 0-100 buy score for every day in the series."""
    dd = drawdown_from_high(close)
    r = rsi(close)
    pct = price_percentile(close)
    sma200 = sma(close, 200)
    below_sma = close / sma200 - 1  # negative when under the 200d SMA

    # Drawdown: 0 pts at <10% off the high, full 40 pts at >=70% off
    # (leveraged ETFs routinely fall 60-90% in corrections).
    dd_score = ((-dd - 0.10) / 0.60).clip(0, 1) * 40

    # RSI: 0 pts at >=50, full 20 pts at <=20.
    rsi_score = ((50 - r) / 30).clip(0, 1) * 20

    # Percentile: full 20 pts in the cheapest decile of its own history.
    pct_score = ((0.50 - pct) / 0.40).clip(0, 1) * 20

    # 200d SMA: 0 pts at/above the SMA, full 20 pts at >=30% below it.
    sma_score = ((-below_sma) / 0.30).clip(0, 1) * 20

    return (dd_score + rsi_score + pct_score + sma_score).round(1)


def label(score: float) -> str:
    if score >= 70:
        return "STRONG BUY"
    if score >= 55:
        return "BUY"
    if score >= 40:
        return "WATCH"
    if score >= 25:
        return "HOLD"
    return "AVOID"


# ------------------------------------------------------------------ analysis

@dataclass
class Analysis:
    ticker: str
    price: float
    score: float
    recommendation: str
    drawdown_5y: float          # % off the 5-year high (negative)
    drawdown_52w: float         # % off the 52-week high (negative)
    rsi14: float
    pct_5y: float               # price percentile within 5y history (0..1)
    vs_sma200: float            # % above/below 200-day SMA
    edge: dict = field(default_factory=dict)  # median forward returns


def historical_edge(close: pd.Series, today_score: float, band: float = 10.0) -> dict:
    """Median forward returns on past days whose score was within `band`
    points of today's score. Empty dict if there were too few such days."""
    scores = score_series(close)
    mask = (scores - today_score).abs() <= band
    out = {}
    for name, days in TRADING_DAYS.items():
        fwd = close.shift(-days) / close - 1
        sample = fwd[mask].dropna()
        if len(sample) >= 20:
            out[name] = float(sample.median())
    return out


def analyze(ticker: str, df: pd.DataFrame) -> Analysis:
    close = df["Close"].astype(float)
    if len(close) < 60:
        raise ValueError(f"{ticker}: not enough history ({len(close)} days)")

    price = float(close.iloc[-1])
    s = float(score_series(close).iloc[-1])
    dd5y = float(price / close.max() - 1)
    dd52w = float(price / close.iloc[-252:].max() - 1)

    return Analysis(
        ticker=ticker,
        price=price,
        score=s,
        recommendation=label(s),
        drawdown_5y=dd5y,
        drawdown_52w=dd52w,
        rsi14=float(rsi(close).iloc[-1]),
        pct_5y=float(close.rank(pct=True).iloc[-1]),
        vs_sma200=float(price / sma(close, 200).iloc[-1] - 1),
        edge=historical_edge(close, s),
    )
