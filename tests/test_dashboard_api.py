"""Minimal dashboard API tests (spec checklist): REST endpoints return valid
JSON against a temp DB; non-whitelisted runner commands are rejected."""
import json
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.dashboard import config as dash_config
from src.dashboard.data_api import _safe_path
from src.dashboard.server import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
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


def test_dashboard_sets_script_restrictions(client):
    r = client.get("/")
    assert r.status_code == 200
    policy = r.headers["content-security-policy"]
    script_policy = next(p for p in policy.split(";") if p.strip().startswith("script-src"))
    assert "'unsafe-inline'" not in script_policy
    assert "'unsafe-eval'" not in script_policy
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"

    graph = client.get("/static/graph3d.html")
    assert graph.status_code == 200
    assert "<script>" not in graph.text
    assert 'src="/static/graph3d.js"' in graph.text


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_dashboard_html_helper_escapes_untrusted_cells():
    helper = Path(__file__).parents[1] / "src" / "dashboard" / "static" / "safe_html.js"
    script = (
        f"const h = require({json.dumps(str(helper))});"
        "const payload = `<img src=x onerror=\"globalThis.pwned=1\">'`;"
        "if (h.tableCell(payload) !== "
        "'&lt;img src=x onerror=&quot;globalThis.pwned=1&quot;&gt;&#39;') process.exit(1);"
        "if (h.tableCell('<button>safe</button>', true) !== '<button>safe</button>') process.exit(2);"
    )
    subprocess.run(["node", "-e", script], check=True)


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


def test_websocket_session_token_authenticates_dashboard_clients(client, monkeypatch):
    monkeypatch.setenv("DASHBOARD_TOKEN", "test secret/&")

    session = client.get("/api/session")
    assert session.status_code == 200
    assert session.json() == {"websocket_token": "test secret/&"}
    assert session.headers["cache-control"] == "no-store"

    for path in ("/ws/run", "/ws/chat", "/ws/term?shell=missing"):
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(path):
                pass
        assert exc.value.code == 4401

    with client.websocket_connect("/ws/run?token=test+secret%2F%26") as ws:
        ws.send_text(json.dumps({"cmd": "not-allowed"}))
        assert json.loads(ws.receive_text())["type"] == "error"

    with client.websocket_connect("/ws/chat?token=test+secret%2F%26"):
        pass

    with client.websocket_connect("/ws/term?shell=missing&token=test+secret%2F%26") as ws:
        assert "missing" in ws.receive_text()


def test_dashboard_frontend_uses_authenticated_websocket_urls():
    source = (dash_config.STATIC_DIR / "app.js").read_text(encoding="utf-8")
    for path in ("/ws/run", "/ws/chat", "/ws/term"):
        assert f"websocketUrl('{path}'" in source
    assert "new WebSocket(`ws://${location.host}" not in source


def test_config_put_rejects_invalid_yaml(client):
    r = client.put("/api/config", json={"content": "a: [unclosed"})
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_yaml"


def test_file_api_rejects_path_traversal(client, tmp_path):
    assert client.get("/api/file?path=../secrets.txt").status_code == 403
    assert client.get(r"/api/file?path=..\secrets.txt").status_code == 403
    assert client.get("/api/tree?path=..").status_code == 403
    assert client.get(f"/api/file?path={tmp_path.as_posix()}").status_code == 403
    r = client.put("/api/file", json={"path": "../evil.py", "content": "x"})
    assert r.status_code == 403


def test_safe_path_rejects_null_byte(tmp_path, monkeypatch):
    monkeypatch.setattr(dash_config, "PROJECT_ROOT", tmp_path)
    with pytest.raises(PermissionError):
        _safe_path("README.md\x00.txt")


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
    # git-tracked binary: exists in every clone, unlike the .pkl training artifacts
    assert client.get("/api/file?path=models/atp_target_pytorch.pt").status_code == 415
    r = client.put("/api/file", json={"path": "nonexistent_dir/new.py", "content": "x"})
    assert r.status_code == 404


def test_file_api_rejects_create_in_existing_dir(client, monkeypatch, tmp_path):
    monkeypatch.setattr(dash_config, "PROJECT_ROOT", tmp_path)
    r = client.put("/api/file", json={"path": "new.py", "content": "x"})
    assert r.status_code == 404
    assert "create" in r.json()["detail"]
    assert not (tmp_path / "new.py").exists()
