"""Watchlist management: add/remove/list tickers, persisted to JSON."""

import json
import re
from pathlib import Path

from . import MAX_WATCHLIST_SIZE

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "watchlist.json"

_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


class WatchlistError(Exception):
    pass


def load(path: Path = DEFAULT_PATH) -> list[str]:
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)
    return list(data.get("tickers", []))


def save(tickers: list[str], path: Path = DEFAULT_PATH) -> None:
    with open(path, "w") as f:
        json.dump({"tickers": tickers}, f, indent=2)
        f.write("\n")


def normalize(ticker: str) -> str:
    ticker = ticker.strip().upper()
    if not _TICKER_RE.match(ticker):
        raise WatchlistError(f"Invalid ticker symbol: {ticker!r}")
    return ticker


def add(tickers: list[str], path: Path = DEFAULT_PATH) -> list[str]:
    """Add one or more tickers. Returns the updated watchlist."""
    current = load(path)
    for raw in tickers:
        t = normalize(raw)
        if t in current:
            continue
        if len(current) >= MAX_WATCHLIST_SIZE:
            raise WatchlistError(
                f"Watchlist is full ({MAX_WATCHLIST_SIZE} tickers). "
                f"Remove one before adding {t}."
            )
        current.append(t)
    save(current, path)
    return current


def remove(tickers: list[str], path: Path = DEFAULT_PATH) -> list[str]:
    current = load(path)
    for raw in tickers:
        t = normalize(raw)
        if t in current:
            current.remove(t)
    save(current, path)
    return current
