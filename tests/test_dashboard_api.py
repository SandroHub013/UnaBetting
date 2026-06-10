"""Minimal dashboard API tests (spec checklist): REST endpoints return valid
JSON against a temp DB; non-whitelisted runner commands are rejected."""
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from src.dashboard import config as dash_config
from src.dashboard.server import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "betanalytix.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE decisions (id TEXT, scan_id TEXT, timestamp TEXT, match_str TEXT,
            p1_name TEXT, p2_name TEXT, tournament TEXT, tourney_level TEXT, surface TEXT,
            odds_1 REAL, odds_2 REAL, ml_prob_1 REAL, ml_prob_2 REAL,
            news_adj_prob_1 REAL, news_adj_prob_2 REAL, news_adjustment REAL,
            news_confidence REAL, news_reason TEXT, news_sources TEXT, edge REAL,
            value_side INTEGER, kelly_fraction REAL, suggested_stake REAL,
            exp_game_diff REAL, exp_total_games REAL, market_spread REAL,
            market_total REAL, low_confidence INTEGER);
        CREATE TABLE bets (id TEXT, decision_id TEXT, timestamp TEXT, match_str TEXT,
            side INTEGER, side_name TEXT, odds REAL, model_prob REAL, edge REAL,
            kelly_pct REAL, stake REAL, status TEXT, profit REAL, bankroll_after REAL,
            resolved_at TEXT, notes TEXT, idempotency_key TEXT);
        CREATE TABLE daily_stats (date TEXT, bankroll REAL, total_bets INTEGER,
            won INTEGER, lost INTEGER, pending INTEGER, total_staked REAL,
            total_profit REAL, roi_pct REAL, max_drawdown_pct REAL, win_rate REAL,
            best_bet TEXT, worst_bet TEXT);
        INSERT INTO decisions VALUES ('d1','s1','2026-06-01T10:00:00','A vs B','A','B',
            'ATP Test','M','Clay',1.9,1.9,0.55,0.45,0.55,0.45,0.0,0.5,'','[]',0.03,1,
            0.01,5.0,0.5,22.0,0.5,22.5,0);
        INSERT INTO bets VALUES ('b1','d1','2026-06-01T11:00:00','A vs B',1,'A',1.9,
            0.55,0.03,0.01,5.0,'won',4.5,1004.5,'2026-06-02','', NULL);
    """)
    conn.commit()
    conn.close()
    monkeypatch.setattr(dash_config, "DB_PATH", db)
    return TestClient(app)


def test_overview_returns_metrics(client):
    r = client.get("/api/overview")
    assert r.status_code == 200
    d = r.json()
    assert d["decisions"] == 1
    assert d["won"] == 1
    assert d["bankroll"] == 1004.5
    assert d["win_rate"] == 100.0


def test_bets_and_decisions_return_lists(client):
    assert isinstance(client.get("/api/bets").json(), list)
    assert client.get("/api/bets?status=won").json()[0]["id"] == "b1"
    rows = client.get("/api/decisions?limit=10").json()
    assert rows and rows[0]["match_str"] == "A vs B"


def test_overview_with_missing_db(monkeypatch, tmp_path):
    monkeypatch.setattr(dash_config, "DB_PATH", tmp_path / "missing.db")
    r = TestClient(app).get("/api/overview")
    assert r.status_code == 200
    assert r.json()["decisions"] == 0


def test_runner_rejects_non_whitelisted(client):
    with client.websocket_connect("/ws/run") as ws:
        ws.send_text(json.dumps({"cmd": "rm -rf /"}))
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "error"
        assert "whitelist" in msg["detail"]


def test_config_put_rejects_invalid_yaml(client):
    r = client.put("/api/config", json={"content": "a: [unclosed"})
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_yaml"


def test_file_api_rejects_path_traversal(client):
    assert client.get("/api/file?path=../secrets.txt").status_code == 403
    assert client.get("/api/tree?path=..").status_code == 403
    r = client.put("/api/file", json={"path": "../evil.py", "content": "x"})
    assert r.status_code == 403


def test_file_api_reads_project_file(client):
    r = client.get("/api/file?path=README.md")
    assert r.status_code == 200
    assert len(r.json()["content"]) > 0
    tree = client.get("/api/tree").json()
    names = [i["name"] for i in tree]
    assert "src" in names and ".git" not in names


def test_bet_lifecycle_place_resolve_undo(client):
    r = client.post("/api/bet", json={"match_str": "X vs Y", "side_name": "X",
                                      "odds": 2.0, "stake": 10})
    assert r.status_code == 200
    bet_id = r.json()["bet_id"]
    r = client.post(f"/api/bet/{bet_id}/resolve", json={"won": True})
    assert r.status_code == 200
    assert r.json()["profit"] == 10.0
    r = client.post(f"/api/bet/{bet_id}/undo")
    assert r.status_code == 200
    rows = client.get("/api/bets?status=pending").json()
    assert any(b["id"] == bet_id for b in rows)


def test_bet_rejects_bad_input(client):
    assert client.post("/api/bet", json={"match_str": "", "side_name": "X",
                                         "odds": 2.0, "stake": 10}).status_code == 400
    assert client.post("/api/bet", json={"match_str": "A", "side_name": "X",
                                         "odds": 0.9, "stake": 10}).status_code == 400


def test_file_api_rejects_binary_and_missing(client):
    assert client.get("/api/file?path=models/atp_target_xgboost.pkl").status_code == 415
    r = client.put("/api/file", json={"path": "nonexistent_dir/new.py", "content": "x"})
    assert r.status_code == 404
