"""Alerting: notify when a ticker crosses into BUY territory.

Alerts fire on *transitions*, not levels: a ticker alerting requires its
signal to move from outside the buy zone into BUY/STRONG BUY (or upgrade
from BUY to STRONG BUY) since the last scan. Last-seen signals are kept in
.alert_state.json so repeated scans stay quiet while nothing changes.

Channels are configured in alerts.json (create with `python -m etf_agent
alerts init`). The SMTP password is never stored in the file — it is read
from the environment variable named by `password_env`.
"""

import json
import os
import shutil
import smtplib
import subprocess
from email.message import EmailMessage
from pathlib import Path

import requests

from .analysis import Analysis

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "alerts.json"
STATE_PATH = ROOT / ".alert_state.json"

BUY_LABELS = ("BUY", "STRONG BUY")

CONFIG_TEMPLATE = {
    "channels": {
        "email": {
            "enabled": False,
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "you@gmail.com",
            "password_env": "ETF_AGENT_SMTP_PASSWORD",
            "from": "you@gmail.com",
            "to": ["you@gmail.com"],
        },
        "webhook": {
            "enabled": False,
            "url": "https://hooks.slack.com/services/XXX/YYY/ZZZ",
        },
        "desktop": {"enabled": True},
    }
}


class AlertError(Exception):
    pass


# ------------------------------------------------------------- config/state

def init_config(path: Path = CONFIG_PATH) -> bool:
    """Write a template config. Returns False if one already exists."""
    if path.exists():
        return False
    with open(path, "w") as f:
        json.dump(CONFIG_TEMPLATE, f, indent=2)
        f.write("\n")
    return True


def load_config(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        return CONFIG_TEMPLATE
    with open(path) as f:
        return json.load(f)


def _load_state(path: Path = STATE_PATH) -> dict:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def _save_state(state: dict, path: Path = STATE_PATH) -> None:
    with open(path, "w") as f:
        json.dump(state, f, indent=2)
        f.write("\n")


# -------------------------------------------------------------- transitions

def _rank(label: str) -> int:
    return BUY_LABELS.index(label) + 1 if label in BUY_LABELS else 0


def detect_transitions(
    results: list[Analysis], state_path: Path = STATE_PATH
) -> list[Analysis]:
    """Return tickers whose signal moved deeper into the buy zone since the
    previous scan, and persist the new signals."""
    state = _load_state(state_path)
    crossed = [
        a for a in results
        if _rank(a.recommendation) > _rank(state.get(a.ticker, "AVOID"))
    ]
    state.update({a.ticker: a.recommendation for a in results})
    _save_state(state, state_path)
    return crossed


# ----------------------------------------------------------------- messages

def format_alert(crossed: list[Analysis]) -> tuple[str, str]:
    """Return (subject, body) describing the buy-zone crossings."""
    names = ", ".join(a.ticker for a in crossed)
    subject = f"ETF agent: {names} crossed into buy territory"
    lines = []
    for a in crossed:
        lines.append(
            f"{a.ticker}: {a.recommendation} (score {a.score:.0f}) at "
            f"${a.price:.2f} — {a.drawdown_5y * 100:+.1f}% off 5y high, "
            f"RSI {a.rsi14:.0f}, {a.vs_sma200 * 100:+.1f}% vs 200d SMA"
        )
        if a.edge:
            fwd = ", ".join(f"{k}: {v * 100:+.1f}%" for k, v in a.edge.items())
            lines.append(f"  median forward return at similar scores: {fwd}")
    lines.append("")
    lines.append("Not financial advice. Verify before acting.")
    return subject, "\n".join(lines)


# ----------------------------------------------------------------- channels

def _send_email(cfg: dict, subject: str, body: str) -> None:
    password = os.environ.get(cfg.get("password_env", "ETF_AGENT_SMTP_PASSWORD"))
    if not password:
        raise AlertError(
            f"SMTP password not set — export {cfg.get('password_env')}"
        )
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["from"]
    msg["To"] = ", ".join(cfg["to"])
    msg.set_content(body)
    with smtplib.SMTP(cfg["smtp_host"], cfg.get("smtp_port", 587), timeout=30) as s:
        s.starttls()
        s.login(cfg["username"], password)
        s.send_message(msg)


def _send_webhook(cfg: dict, subject: str, body: str) -> None:
    text = f"{subject}\n{body}"
    # "text" is what Slack reads, "content" is what Discord reads;
    # each ignores the other's key.
    resp = requests.post(
        cfg["url"], json={"text": text, "content": text[:2000]}, timeout=30
    )
    resp.raise_for_status()


def _send_desktop(cfg: dict, subject: str, body: str) -> None:
    if shutil.which("notify-send"):  # Linux
        subprocess.run(["notify-send", subject, body], check=True, timeout=10)
    elif shutil.which("osascript"):  # macOS
        script = f'display notification "{body[:200]}" with title "{subject}"'
        subprocess.run(["osascript", "-e", script], check=True, timeout=10)
    else:
        raise AlertError("no desktop notifier found (notify-send/osascript)")


_SENDERS = {"email": _send_email, "webhook": _send_webhook, "desktop": _send_desktop}


def dispatch(subject: str, body: str, config: dict) -> tuple[list[str], list[str]]:
    """Send through every enabled channel. Returns (sent, failures)."""
    sent, failures = [], []
    for name, sender in _SENDERS.items():
        cfg = config.get("channels", {}).get(name, {})
        if not cfg.get("enabled"):
            continue
        try:
            sender(cfg, subject, body)
            sent.append(name)
        except Exception as e:
            failures.append(f"{name}: {e}")
    return sent, failures


def run_alerts(results: list[Analysis]) -> tuple[list[str], list[str]]:
    """Detect buy-zone crossings and notify. Returns (sent, failures)."""
    crossed = detect_transitions(results)
    if not crossed:
        return [], []
    subject, body = format_alert(crossed)
    return dispatch(subject, body, load_config())
