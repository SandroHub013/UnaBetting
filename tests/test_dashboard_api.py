"""Minimal dashboard API tests (spec checklist): REST endpoints return valid
JSON against a temp DB; non-whitelisted runner commands are rejected."""
import json
import shutil
import socket
import sqlite3
import subprocess
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.dashboard import config as dash_config, data_api as dash_data_api
from src.dashboard.data_api import (
    _PublicHTTPConnection,
    _PublicHTTPSConnection,
    _PublicOnlyRedirectHandler,
    _UnsafeBrowseURL,
    _create_public_connection,
    _safe_path,
    _validate_public_http_url,
)
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


def test_overview_uses_most_recent_resolution_for_bankroll(client):
    with sqlite3.connect(dash_config.DB_PATH) as conn:
        conn.execute(
            "INSERT INTO bets (id, timestamp, status, bankroll_after, resolved_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("placed-later", "2026-06-03T09:00:00", "lost", 990.0,
             "2026-06-03T10:00:00"),
        )
        conn.execute(
            "INSERT INTO bets (id, timestamp, status, bankroll_after, resolved_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("resolved-later", "2026-06-02T09:00:00", "won", 1010.0,
             "2026-06-04T10:00:00"),
        )

    r = client.get("/api/overview")

    assert r.status_code == 200
    assert r.json()["bankroll"] == 1010.0


def test_dashboard_sets_script_restrictions(client):
    r = client.get("/")
    assert r.status_code == 200
    policy = r.headers["content-security-policy"]
    script_policy = next(p for p in policy.split(";") if p.strip().startswith("script-src"))
    assert "'unsafe-inline'" not in script_policy
    assert "'unsafe-eval'" not in script_policy
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["cross-origin-resource-policy"] == "same-origin"

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


def test_dashboard_rejects_cross_origin_browser_requests(client):
    foreign = {"origin": "https://attacker.example"}

    session = client.get("/api/session", headers=foreign)
    assert session.status_code == 403
    assert session.json()["error"] == "forbidden"
    assert client.get(
        "/api/session", headers={"sec-fetch-site": "cross-site"}
    ).status_code == 403

    bet = client.post(
        "/api/bet",
        headers=foreign,
        json={"match_str": "X vs Y", "side_name": "X", "odds": 2.0, "stake": 10},
    )
    assert bet.status_code == 403
    assert len(client.get("/api/bets").json()) == 1

    for path in ("/ws/run", "/ws/chat", "/ws/term?shell=missing"):
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(path, headers=foreign):
                pass
        assert exc.value.code == 4403


def test_dashboard_allows_its_loopback_browser_origin(client):
    local = {
        "origin": f"http://localhost:{dash_config.PORT}",
        "sec-fetch-site": "same-origin",
    }
    assert client.get("/api/session", headers=local).status_code == 200

    with client.websocket_connect("/ws/run", headers=local) as ws:
        ws.send_text(json.dumps({"cmd": "not-allowed"}))
        assert json.loads(ws.receive_text())["type"] == "error"


def test_dashboard_frontend_uses_authenticated_websocket_urls():
    source = (dash_config.STATIC_DIR / "app.js").read_text(encoding="utf-8")
    for path in ("/ws/run", "/ws/chat", "/ws/term"):
        assert f"websocketUrl('{path}'" in source
    assert "new WebSocket(`ws://${location.host}" not in source


def test_config_put_rejects_invalid_yaml(client):
    r = client.put("/api/config", json={"content": "a: [unclosed"})
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_yaml"


@pytest.mark.parametrize("content", ["[]\n", "42\n", "{}\n"])
def test_config_put_rejects_yaml_without_required_shape(monkeypatch, tmp_path, content):
    original = dash_config.CONFIG_YAML.read_text(encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(dash_config, "CONFIG_YAML", config_path)

    r = TestClient(app).put("/api/config", json={"content": content})

    assert r.status_code == 400
    assert r.json()["error"] == "invalid_config"
    assert config_path.read_text(encoding="utf-8") == original
    assert not config_path.with_suffix(".yaml.bak").exists()


def test_config_put_rejects_wrong_core_field_type(monkeypatch, tmp_path):
    original = dash_config.CONFIG_YAML.read_text(encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(dash_config, "CONFIG_YAML", config_path)
    edited = yaml.safe_load(original)
    edited["model"]["validation_years"] = 2024

    r = TestClient(app).put(
        "/api/config", json={"content": yaml.safe_dump(edited, sort_keys=False)})

    assert r.status_code == 400
    assert r.json()["error"] == "invalid_config"
    assert "model.validation_years" in r.json()["detail"]
    assert config_path.read_text(encoding="utf-8") == original


def test_config_put_atomically_saves_valid_config_with_backup(monkeypatch, tmp_path):
    original = dash_config.CONFIG_YAML.read_text(encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(dash_config, "CONFIG_YAML", config_path)
    edited = yaml.safe_load(original)
    edited["betting"]["initial_bankroll"] = 1250
    content = yaml.safe_dump(edited, sort_keys=False)

    r = TestClient(app).put("/api/config", json={"content": content})

    assert r.status_code == 200
    assert r.json()["saved"] is True
    assert config_path.read_text(encoding="utf-8") == content
    assert config_path.with_suffix(".yaml.bak").read_text(encoding="utf-8") == original
    assert not list(tmp_path.glob(".config.yaml.*.tmp"))


def test_config_put_preserves_original_when_atomic_replace_fails(monkeypatch, tmp_path):
    original = dash_config.CONFIG_YAML.read_text(encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(dash_config, "CONFIG_YAML", config_path)
    edited = yaml.safe_load(original)
    edited["betting"]["initial_bankroll"] = 1250

    def fail_replace(source, destination):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(dash_data_api.os, "replace", fail_replace)
    r = TestClient(app).put(
        "/api/config", json={"content": yaml.safe_dump(edited, sort_keys=False)})

    assert r.status_code == 500
    assert r.json()["error"] == "config_write_error"
    assert config_path.read_text(encoding="utf-8") == original
    assert config_path.with_suffix(".yaml.bak").read_text(encoding="utf-8") == original
    assert not list(tmp_path.glob(".config.yaml.*.tmp"))


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


def test_browser_rejects_private_network_targets(client, monkeypatch):
    def private_dns(host, port, type=0):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.10", port))]

    monkeypatch.setattr(socket, "getaddrinfo", private_dns)

    for url in (
        "http://127.0.0.1:8765/api/overview",
        "http://[::1]/",
        "http://169.254.169.254/latest/meta-data/",
        "http://dashboard.internal/",
        "http://user:pass@example.com/",
        "file:///etc/passwd",
    ):
        r = client.get("/api/browse", params={"url": url})
        assert r.status_code == 400
        assert r.json()["error"] == "unsafe_url"


def test_browser_rejects_mixed_public_private_dns(monkeypatch):
    def mixed_dns(host, port, type=0):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", port)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", mixed_dns)

    with pytest.raises(_UnsafeBrowseURL):
        _validate_public_http_url("https://example.com/")


def test_browser_allows_global_dns_targets(monkeypatch):
    def public_dns(host, port, type=0):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:2800:220:1:248:1893:25c8:1946", port, 0, 0)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", public_dns)

    assert (_validate_public_http_url("https://example.com/path")
            == "https://example.com/path")


def test_browser_redirects_revalidate_destinations(monkeypatch):
    def private_dns(host, port, type=0):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]

    monkeypatch.setattr(socket, "getaddrinfo", private_dns)
    handler = _PublicOnlyRedirectHandler()

    with pytest.raises(_UnsafeBrowseURL):
        handler.redirect_request(
            None, None, 302, "Found", {}, "http://internal.example/admin")


def test_browser_connections_use_validated_socket_factory():
    assert (_PublicHTTPConnection("example.com")._create_connection
            is _create_public_connection)
    assert (_PublicHTTPSConnection("example.com")._create_connection
            is _create_public_connection)


def test_browser_connection_rejects_dns_rebinding(monkeypatch):
    answers = iter([
        [(socket.AF_INET, socket.SOCK_STREAM, 6, "",
          ("93.184.216.34", 443))],
        [(socket.AF_INET, socket.SOCK_STREAM, 6, "",
          ("127.0.0.1", 443))],
    ])
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: next(answers))

    _validate_public_http_url("https://example.com/")
    with pytest.raises(_UnsafeBrowseURL):
        _create_public_connection(("example.com", 443))


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
