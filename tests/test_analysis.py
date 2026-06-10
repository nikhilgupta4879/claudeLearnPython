"""Offline tests using synthetic price series (no network needed)."""

import numpy as np
import pandas as pd
import pytest

from etf_agent import analysis, watchlist


def make_df(closes) -> pd.DataFrame:
    closes = pd.Series(closes, dtype=float)
    idx = pd.bdate_range("2021-01-04", periods=len(closes))
    closes.index = idx
    return pd.DataFrame({
        "Open": closes, "High": closes * 1.01,
        "Low": closes * 0.99, "Close": closes,
        "Volume": 1_000_000,
    })


def crashed_series(n=1260):
    """Rises for 4 years, then loses 70% — a classic LETF crash."""
    rise = np.linspace(10, 100, n - 120)
    crash = np.linspace(100, 30, 120)
    return np.concatenate([rise, crash])


def melt_up_series(n=1260):
    """Monotonic rise to all-time highs."""
    return np.linspace(10, 100, n)


def test_deep_drawdown_scores_high():
    df = make_df(crashed_series())
    a = analysis.analyze("CRASH", df)
    assert a.score >= 55, f"expected BUY-zone score, got {a.score}"
    assert a.recommendation in ("BUY", "STRONG BUY")
    assert a.drawdown_5y == pytest.approx(-0.70, abs=0.02)


def test_all_time_high_scores_low():
    df = make_df(melt_up_series())
    a = analysis.analyze("MELT", df)
    assert a.score < 25, f"expected AVOID-zone score, got {a.score}"
    assert a.recommendation == "AVOID"
    assert a.drawdown_5y == pytest.approx(0.0, abs=0.01)


def test_score_bounds():
    for series in (crashed_series(), melt_up_series()):
        scores = analysis.score_series(make_df(series)["Close"])
        assert scores.between(0, 100).all()


def test_rsi_range_and_direction():
    falling = analysis.rsi(pd.Series(np.linspace(100, 50, 100))).iloc[-1]
    rising = analysis.rsi(pd.Series(np.linspace(50, 100, 100))).iloc[-1]
    assert 0 <= falling < 10
    assert 90 < rising <= 100


def test_drawdown_from_high():
    dd = analysis.drawdown_from_high(pd.Series([10.0, 20.0, 10.0]))
    assert dd.iloc[-1] == pytest.approx(-0.5)


def test_historical_edge_keys():
    close = make_df(crashed_series())["Close"]
    today = float(analysis.score_series(close).iloc[-1])
    edge = analysis.historical_edge(close, today)
    assert set(edge) <= {"3m", "6m", "12m"}
    for v in edge.values():
        assert isinstance(v, float)


def test_insufficient_history_raises():
    with pytest.raises(ValueError):
        analysis.analyze("X", make_df(np.linspace(10, 20, 30)))


# ----------------------------------------------------------------- watchlist

def test_watchlist_add_remove(tmp_path):
    p = tmp_path / "wl.json"
    assert watchlist.add(["soxl", "TQQQ"], p) == ["SOXL", "TQQQ"]
    assert watchlist.add(["SOXL"], p) == ["SOXL", "TQQQ"]  # no duplicates
    assert watchlist.remove(["tqqq"], p) == ["SOXL"]
    assert watchlist.load(p) == ["SOXL"]


def test_watchlist_max_20(tmp_path):
    p = tmp_path / "wl.json"
    watchlist.add([f"T{i}" for i in range(20)], p)
    with pytest.raises(watchlist.WatchlistError, match="full"):
        watchlist.add(["ONEMORE"], p)


def test_watchlist_rejects_garbage(tmp_path):
    with pytest.raises(watchlist.WatchlistError):
        watchlist.add(["not a ticker!"], tmp_path / "wl.json")
