"""Command-line interface for the ETF monitoring agent.

Usage:
    python -m etf_agent add SOXL TQQQ UPRO
    python -m etf_agent remove UPRO
    python -m etf_agent list
    python -m etf_agent scan                 # analyze whole watchlist
    python -m etf_agent scan --ticker SOXL   # analyze one ticker
    python -m etf_agent watch --interval 30  # re-scan every 30 minutes
"""

import argparse
import sys
import time

from . import MAX_WATCHLIST_SIZE
from . import analysis, data, watchlist


def _fmt_pct(x: float) -> str:
    return f"{x * 100:+.1f}%"


def _print_report(results: list[analysis.Analysis]) -> None:
    results = sorted(results, key=lambda a: a.score, reverse=True)
    header = (
        f"{'TICKER':<8}{'PRICE':>10}{'SCORE':>7}  {'SIGNAL':<11}"
        f"{'5Y DD':>8}{'52W DD':>8}{'RSI':>6}{'vs SMA200':>11}"
    )
    print(header)
    print("-" * len(header))
    for a in results:
        print(
            f"{a.ticker:<8}{a.price:>10.2f}{a.score:>7.0f}  {a.recommendation:<11}"
            f"{_fmt_pct(a.drawdown_5y):>8}{_fmt_pct(a.drawdown_52w):>8}"
            f"{a.rsi14:>6.0f}{_fmt_pct(a.vs_sma200):>11}"
        )
    print()
    for a in results:
        if a.edge:
            fwd = ", ".join(f"{k}: {_fmt_pct(v)}" for k, v in a.edge.items())
            print(f"{a.ticker}: at similar scores over the past 5y, "
                  f"median forward return was {fwd}")
    print("\nScores: >=70 STRONG BUY, 55-69 BUY, 40-54 WATCH, 25-39 HOLD, <25 AVOID")
    print("Not financial advice — leveraged ETFs can lose most of their value.")


def cmd_scan(tickers: list[str]) -> int:
    if not tickers:
        print("Watchlist is empty. Add tickers first: python -m etf_agent add SOXL TQQQ")
        return 1
    results, failures = [], []
    for t in tickers:
        try:
            df = data.get_history(t)
            results.append(analysis.analyze(t, df))
        except Exception as e:
            failures.append(f"{t}: {e}")
    if results:
        _print_report(results)
    for f in failures:
        print(f"WARNING — could not analyze {f}", file=sys.stderr)
    return 0 if results else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="etf_agent",
        description=f"Monitor up to {MAX_WATCHLIST_SIZE} leveraged ETFs and "
                    "score buy timing from 5 years of history.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="add ticker(s) to the watchlist")
    p_add.add_argument("tickers", nargs="+")

    p_rm = sub.add_parser("remove", help="remove ticker(s) from the watchlist")
    p_rm.add_argument("tickers", nargs="+")

    sub.add_parser("list", help="show the watchlist")

    p_scan = sub.add_parser("scan", help="analyze the watchlist now")
    p_scan.add_argument("--ticker", help="analyze a single ticker instead")
    p_scan.add_argument("--no-cache", action="store_true",
                        help="force fresh download even if cached today")

    p_watch = sub.add_parser("watch", help="re-scan on an interval (Ctrl-C to stop)")
    p_watch.add_argument("--interval", type=int, default=30,
                         help="minutes between scans (default 30)")

    args = parser.parse_args(argv)

    if args.command == "add":
        try:
            updated = watchlist.add(args.tickers)
        except watchlist.WatchlistError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        print(f"Watchlist ({len(updated)}/{MAX_WATCHLIST_SIZE}): {', '.join(updated)}")
        return 0

    if args.command == "remove":
        updated = watchlist.remove(args.tickers)
        print(f"Watchlist ({len(updated)}/{MAX_WATCHLIST_SIZE}): "
              f"{', '.join(updated) or '(empty)'}")
        return 0

    if args.command == "list":
        tickers = watchlist.load()
        print(f"Watchlist ({len(tickers)}/{MAX_WATCHLIST_SIZE}): "
              f"{', '.join(tickers) or '(empty)'}")
        return 0

    if args.command == "scan":
        if args.no_cache:
            for p in data.CACHE_DIR.glob("*.csv"):
                p.unlink()
        tickers = [args.ticker.upper()] if args.ticker else watchlist.load()
        return cmd_scan(tickers)

    if args.command == "watch":
        print(f"Watching every {args.interval} min — Ctrl-C to stop.")
        while True:
            print(f"\n=== Scan at {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
            cmd_scan(watchlist.load())
            time.sleep(args.interval * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
