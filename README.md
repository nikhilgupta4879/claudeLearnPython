# Leveraged ETF Monitoring Agent

A command-line agent that monitors a watchlist of up to **20 leveraged ETFs**
(SOXL, TQQQ, UPRO, ...), pulls **5 years of daily price history**, and scores
how attractive the current price is as an entry point.

## Why this scoring approach

Leveraged ETFs reset daily, so they decay in sideways markets and fall
60–90% in corrections — buying them near all-time highs is historically the
worst entry. The agent is therefore **mean-reversion weighted**: it rewards
deep drawdowns in products whose underlying index trends up over time.

Composite buy score (0–100):

| Signal | Weight | Full points when |
|---|---|---|
| Drawdown from 5-year high | 40 | ≥70% below the high |
| RSI(14) oversold | 20 | RSI ≤ 20 |
| Price percentile in its own 5y range | 20 | cheapest decile |
| Distance below 200-day SMA | 20 | ≥30% below |

| Score | Signal |
|---|---|
| ≥ 70 | STRONG BUY |
| 55–69 | BUY |
| 40–54 | WATCH |
| 25–39 | HOLD |
| < 25 | AVOID |

Each recommendation also reports the **historical edge**: the median forward
3/6/12-month return on past days when the score was similar to today's, so
you can see whether the signal actually paid off over the last 5 years.

## Setup

```bash
pip install -r requirements.txt
```

Data comes from Yahoo Finance (via `yfinance`), with Stooq as an automatic
fallback. Downloads are cached in `.cache/` for the rest of the day.

## Usage

```bash
# Manage the watchlist (max 20 tickers)
python -m etf_agent add SOXL TQQQ UPRO TECL FNGU
python -m etf_agent remove FNGU
python -m etf_agent list

# Analyze the whole watchlist now
python -m etf_agent scan

# Analyze a single ticker (doesn't need to be on the watchlist)
python -m etf_agent scan --ticker SOXL

# Force fresh data instead of today's cache
python -m etf_agent scan --no-cache

# Keep monitoring: re-scan every 30 minutes until Ctrl-C
# (alerts on by default; --no-alerts to disable)
python -m etf_agent watch --interval 30
```

## Alerts

The agent can notify you the moment a ticker **crosses into BUY territory**
(or upgrades from BUY to STRONG BUY). Alerts fire on transitions, not
levels — last-seen signals are remembered in `.alert_state.json`, so a
ticker that stays in the buy zone won't re-alert on every scan.

```bash
python -m etf_agent alerts init    # writes an alerts.json template
# ... edit alerts.json to enable channels ...
python -m etf_agent alerts test    # send a test notification
python -m etf_agent scan --alerts  # one-off scan with notifications
python -m etf_agent watch          # continuous monitoring, alerts enabled
```

Three channels, each independently enabled in `alerts.json`:

| Channel | Notes |
|---|---|
| `email` | SMTP with STARTTLS (e.g. Gmail with an app password). The password is **not** stored in the file — export it in the env var named by `password_env` (default `ETF_AGENT_SMTP_PASSWORD`). |
| `webhook` | POSTs the alert as JSON; works with Slack and Discord incoming-webhook URLs out of the box. |
| `desktop` | Local pop-up via `notify-send` (Linux) or `osascript` (macOS). |

`alerts.json` and `.alert_state.json` are git-ignored since they contain
personal addresses/state.

For hands-off monitoring, run a scan with alerts from cron, e.g. every
30 minutes on trading days:

```cron
*/30 9-16 * * 1-5  cd /path/to/repo && python -m etf_agent scan --alerts
```

Example output:

```
TICKER       PRICE  SCORE  SIGNAL        5Y DD  52W DD   RSI  vs SMA200
-----------------------------------------------------------------------
SOXL         24.00     96  STRONG BUY   -70.0%  -70.0%     8     -61.4%
TQQQ         95.00     12  AVOID         -3.1%   -3.1%    71      +6.7%

SOXL: at similar scores over the past 5y, median forward return was 3m: +18.2%, 6m: +35.0%, 12m: +61.4%
```

## Running tests

The analytics are covered by offline tests using synthetic price series:

```bash
python -m pytest tests/
```

## Disclaimer

This tool is for educational purposes and is **not financial advice**.
Leveraged ETFs are high-risk instruments that can lose most of their value
and are generally unsuitable for long-term buy-and-hold. Past 5-year
patterns do not guarantee future results.
