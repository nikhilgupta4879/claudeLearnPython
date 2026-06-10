"""Leveraged ETF monitoring agent.

Tracks a watchlist of up to 20 tickers, pulls 5 years of price history,
computes mean-reversion / trend indicators tuned for leveraged ETFs, and
produces a buy-timing recommendation for each ticker.
"""

MAX_WATCHLIST_SIZE = 20
HISTORY_YEARS = 5
