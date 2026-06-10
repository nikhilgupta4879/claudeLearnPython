"""Offline tests for alert transitions, formatting, and dispatch."""

import json

import pytest

from etf_agent import alerts
from etf_agent.analysis import Analysis


def make_analysis(ticker="SOXL", score=60.0, rec="BUY", edge=None) -> Analysis:
    return Analysis(
        ticker=ticker, price=25.0, score=score, recommendation=rec,
        drawdown_5y=-0.55, drawdown_52w=-0.40, rsi14=28.0,
        pct_5y=0.12, vs_sma200=-0.22, edge=edge or {},
    )


# -------------------------------------------------------------- transitions

def test_first_buy_signal_alerts(tmp_path):
    state = tmp_path / "state.json"
    crossed = alerts.detect_transitions([make_analysis()], state)
    assert [a.ticker for a in crossed] == ["SOXL"]


def test_no_realert_while_signal_unchanged(tmp_path):
    state = tmp_path / "state.json"
    alerts.detect_transitions([make_analysis()], state)
    assert alerts.detect_transitions([make_analysis()], state) == []


def test_upgrade_to_strong_buy_realerts(tmp_path):
    state = tmp_path / "state.json"
    alerts.detect_transitions([make_analysis(rec="BUY")], state)
    crossed = alerts.detect_transitions(
        [make_analysis(rec="STRONG BUY", score=75)], state
    )
    assert [a.ticker for a in crossed] == ["SOXL"]


def test_downgrade_then_recross_alerts_again(tmp_path):
    state = tmp_path / "state.json"
    alerts.detect_transitions([make_analysis(rec="BUY")], state)
    alerts.detect_transitions([make_analysis(rec="WATCH", score=45)], state)
    crossed = alerts.detect_transitions([make_analysis(rec="BUY")], state)
    assert [a.ticker for a in crossed] == ["SOXL"]


def test_non_buy_signals_never_alert(tmp_path):
    state = tmp_path / "state.json"
    results = [make_analysis(rec=r, score=s)
               for r, s in [("AVOID", 5), ("HOLD", 30), ("WATCH", 45)]]
    assert alerts.detect_transitions(results, state) == []


# ----------------------------------------------------------------- messages

def test_format_alert_contents():
    a = make_analysis(edge={"6m": 0.35})
    subject, body = alerts.format_alert([a])
    assert "SOXL" in subject and "buy territory" in subject
    assert "BUY (score 60)" in body
    assert "$25.00" in body
    assert "-55.0% off 5y high" in body
    assert "6m: +35.0%" in body
    assert "Not financial advice" in body


# ----------------------------------------------------------------- dispatch

def test_dispatch_only_enabled_channels(monkeypatch):
    calls = []
    monkeypatch.setitem(alerts._SENDERS, "email",
                        lambda cfg, s, b: calls.append("email"))
    monkeypatch.setitem(alerts._SENDERS, "webhook",
                        lambda cfg, s, b: calls.append("webhook"))
    monkeypatch.setitem(alerts._SENDERS, "desktop",
                        lambda cfg, s, b: calls.append("desktop"))
    config = {"channels": {
        "email": {"enabled": True},
        "webhook": {"enabled": False},
        "desktop": {"enabled": True},
    }}
    sent, failures = alerts.dispatch("subj", "body", config)
    assert sorted(calls) == ["desktop", "email"]
    assert sorted(sent) == ["desktop", "email"]
    assert failures == []


def test_dispatch_reports_channel_failure(monkeypatch):
    def boom(cfg, s, b):
        raise alerts.AlertError("smtp down")
    monkeypatch.setitem(alerts._SENDERS, "email", boom)
    config = {"channels": {"email": {"enabled": True}}}
    sent, failures = alerts.dispatch("subj", "body", config)
    assert sent == []
    assert failures and "smtp down" in failures[0]


def test_email_requires_password_env(monkeypatch):
    monkeypatch.delenv("ETF_AGENT_SMTP_PASSWORD", raising=False)
    with pytest.raises(alerts.AlertError, match="password"):
        alerts._send_email(
            {"password_env": "ETF_AGENT_SMTP_PASSWORD"}, "s", "b"
        )


# ------------------------------------------------------------------- config

def test_init_config_writes_template_once(tmp_path):
    p = tmp_path / "alerts.json"
    assert alerts.init_config(p) is True
    assert alerts.init_config(p) is False  # never overwrites
    cfg = json.loads(p.read_text())
    assert set(cfg["channels"]) == {"email", "webhook", "desktop"}
    # template must not contain a real secret slot
    assert "password" not in cfg["channels"]["email"]
    assert cfg["channels"]["email"]["password_env"]
