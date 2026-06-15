"""REST API: read-only data cockpit + config editor (the only writing endpoint)."""
import http.client
import ipaddress
import json
import math
import os
import shutil
import socket
import sqlite3
import tempfile
import urllib.request
from pathlib import Path, PureWindowsPath
from urllib.parse import urlsplit

import yaml
from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse, JSONResponse

from . import chat, config

router = APIRouter(prefix="/api")

MEDIA_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
    ".bmp": "image/bmp", ".ico": "image/x-icon",
    ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime",
    ".mkv": "video/x-matroska", ".m4v": "video/mp4",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg", ".m4a": "audio/mp4",
    ".pdf": "application/pdf",
}


class _UnsafeBrowseURL(ValueError):
    """Raised when the agentic browser target can reach a non-public network."""


def _err(status, error, detail=""):
    return JSONResponse({"error": error, "detail": str(detail)}, status_code=status)


_REQUIRED_CONFIG_FIELDS = {
    ("data", "sackmann"): dict,
    ("data", "tennis_data_co_uk", "base_url"): str,
    ("data", "tennis_data_co_uk", "atp_start_year"): int,
    ("data", "tennis_data_co_uk", "wta_start_year"): int,
    ("data", "odds_api", "regions"): str,
    ("data", "odds_api", "markets"): str,
    ("paths", "raw_data"): str,
    ("paths", "processed_data"): str,
    ("paths", "features"): str,
    ("paths", "models"): str,
    ("paths", "reports"): str,
    ("features", "elo", "k_factor"): (int, float),
    ("features", "elo", "k_factor_grand_slam"): (int, float),
    ("features", "elo", "initial_rating"): (int, float),
    ("features", "elo", "surface_weight"): (int, float),
    ("model", "test_start_year"): int,
    ("model", "validation_years"): list,
    ("model", "xgboost"): dict,
    ("model", "lightgbm"): dict,
    ("model", "neural_network"): dict,
    ("agent", "openrouter", "model"): str,
    ("agent", "openrouter", "system_prompt"): str,
}


def _validate_config(value):
    """Reject valid YAML that cannot satisfy the project's config contract."""
    if not isinstance(value, dict):
        raise ValueError("config root must be a YAML mapping")

    for path, expected_type in _REQUIRED_CONFIG_FIELDS.items():
        current = value
        dotted = ".".join(path)
        for key in path:
            if not isinstance(current, dict) or key not in current:
                raise ValueError(f"missing required config field: {dotted}")
            current = current[key]
        if isinstance(current, bool) or not isinstance(current, expected_type):
            names = (expected_type.__name__ if isinstance(expected_type, type)
                     else " or ".join(t.__name__ for t in expected_type))
            raise ValueError(f"config field {dotted} must be {names}")
        if isinstance(current, str) and not current.strip():
            raise ValueError(f"config field {dotted} must not be empty")
    return value


def _write_config_atomically(path, content):
    """Write a validated config without exposing a truncated active file."""
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        shutil.copystat(path, tmp)
        backup = path.with_suffix(".yaml.bak")
        shutil.copy2(path, backup)
        os.replace(tmp, path)
        return backup
    finally:
        tmp.unlink(missing_ok=True)


def _save_config_content(content):
    """Validate and persist config content for every dashboard write path."""
    if not isinstance(content, str) or not content.strip():
        return _err(400, "bad_request", "campo 'content' mancante o vuoto")
    try:
        _validate_config(yaml.safe_load(content))
    except yaml.YAMLError as e:
        return _err(400, "invalid_yaml", e)
    except ValueError as e:
        return _err(400, "invalid_config", e)
    try:
        backup = _write_config_atomically(config.CONFIG_YAML, content)
        return {"saved": True, "backup": str(backup)}
    except OSError as e:
        return _err(500, "config_write_error", e)


@router.get("/session")
def session():
    """Return browser-only session data needed by the static dashboard client."""
    return JSONResponse(
        {"websocket_token": config.auth_token()},
        headers={"Cache-Control": "no-store"},
    )


def _ro_conn():
    """Read-only sqlite connection; raises if the DB file is missing."""
    uri = f"file:{config.DB_PATH.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _rows(conn, sql, params=()):
    return [dict(r) for r in conn.execute(sql, params)]


@router.get("/overview")
def overview():
    out = {"bankroll": None, "bets_open": 0, "bets_closed": 0, "won": 0, "lost": 0,
           "total_profit": 0.0, "roi_pct": None, "win_rate": None, "max_drawdown_pct": None,
           "decisions": 0, "last_scan": None}
    if not config.DB_PATH.exists():
        return out
    try:
        with _ro_conn() as conn:
            out["decisions"] = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
            last = conn.execute("SELECT MAX(timestamp) FROM decisions").fetchone()[0]
            out["last_scan"] = last
            out["bets_open"] = conn.execute(
                "SELECT COUNT(*) FROM bets WHERE status='pending'").fetchone()[0]
            out["bets_closed"] = conn.execute(
                "SELECT COUNT(*) FROM bets WHERE status!='pending'").fetchone()[0]
            out["won"] = conn.execute("SELECT COUNT(*) FROM bets WHERE status='won'").fetchone()[0]
            out["lost"] = conn.execute("SELECT COUNT(*) FROM bets WHERE status='lost'").fetchone()[0]
            profit = conn.execute("SELECT SUM(profit) FROM bets WHERE profit IS NOT NULL").fetchone()[0]
            out["total_profit"] = round(profit or 0.0, 2)
            bank = conn.execute(
                "SELECT bankroll_after FROM bets WHERE bankroll_after IS NOT NULL "
                "ORDER BY resolved_at DESC, timestamp DESC LIMIT 1").fetchone()
            out["bankroll"] = round(bank[0], 2) if bank else None
            staked = conn.execute("SELECT SUM(stake) FROM bets WHERE status!='pending'").fetchone()[0]
            if staked:
                out["roi_pct"] = round(100.0 * out["total_profit"] / staked, 2)
            settled = out["won"] + out["lost"]
            if settled:
                out["win_rate"] = round(100.0 * out["won"] / settled, 1)
            dd = conn.execute("SELECT MAX(max_drawdown_pct) FROM daily_stats").fetchone()[0]
            out["max_drawdown_pct"] = dd
    except sqlite3.Error as e:
        return _err(500, "db_error", e)
    return out


@router.get("/decisions")
def decisions(limit: int = 50):
    if not config.DB_PATH.exists():
        return []
    try:
        with _ro_conn() as conn:
            rows = _rows(conn,
                         "SELECT id, timestamp, match_str, tournament, surface, odds_1, odds_2, "
                         "ml_prob_1, ml_prob_2, news_adj_prob_1, news_adj_prob_2, edge, value_side, "
                         "kelly_fraction, suggested_stake, news_reason, low_confidence "
                         "FROM decisions ORDER BY timestamp DESC LIMIT ?", (max(1, min(limit, 500)),))
        return rows
    except sqlite3.Error as e:
        return _err(500, "db_error", e)


@router.get("/bets")
def bets(status: str = ""):
    if not config.DB_PATH.exists():
        return []
    try:
        with _ro_conn() as conn:
            if status:
                return _rows(conn, "SELECT * FROM bets WHERE status=? ORDER BY timestamp DESC", (status,))
            return _rows(conn, "SELECT * FROM bets ORDER BY timestamp DESC")
    except sqlite3.Error as e:
        return _err(500, "db_error", e)


def _portfolio():
    import sys
    sys.path.insert(0, str(config.PROJECT_ROOT))
    from src.betting.portfolio import BetAnalytix
    return BetAnalytix(db_path=config.DB_PATH)


def _text_field(body, name, *, required=False):
    value = body.get(name)
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{name} must not be empty")
    return value


def _finite_number(body, name, *, default=None):
    value = body.get(name, default)
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a finite number") from None
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    return number


def _bet_side(body):
    value = body.get("side", 0)
    if isinstance(value, bool):
        raise ValueError("side must be 0, 1, or 2")
    if isinstance(value, int):
        side = value
    elif isinstance(value, str) and value.strip() in {"0", "1", "2"}:
        side = int(value)
    else:
        raise ValueError("side must be 0, 1, or 2")
    if side not in {0, 1, 2}:
        raise ValueError("side must be 0, 1, or 2")
    return side


@router.post("/bet")
async def place_bet(request: Request):
    """Register a manually placed bet (Bet-Analytix style tracking)."""
    try:
        b = await request.json()
        if not isinstance(b, dict):
            raise ValueError("request body must be a JSON object")
        match_str = _text_field(b, "match_str", required=True)
        side_name = _text_field(b, "side_name", required=True)
        decision_id = _text_field(b, "decision_id")
        notes = _text_field(b, "notes")
        odds = _finite_number(b, "odds")
        stake = _finite_number(b, "stake")
        model_prob = _finite_number(b, "model_prob", default=0)
        edge = _finite_number(b, "edge", default=0)
        kelly_pct = _finite_number(b, "kelly_pct", default=0)
        side = _bet_side(b)
        if odds <= 1.0 or stake <= 0:
            raise ValueError("odds must be greater than 1 and stake must be positive")
        if not 0 <= model_prob <= 1:
            raise ValueError("model_prob must be between 0 and 1")
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        return _err(400, "bad_request", e)
    db = _portfolio()
    try:
        bet_id = db.place_bet(
            decision_id=decision_id, side=side,
            side_name=side_name, odds=odds,
            model_prob=model_prob, edge=edge,
            kelly_pct=kelly_pct, stake=stake,
            match_str=match_str, notes=notes)
        return {"bet_id": bet_id}
    except Exception as e:
        return _err(500, "db_error", e)
    finally:
        db.close()


@router.post("/bet/{bet_id}/resolve")
async def resolve_bet(bet_id: str, request: Request):
    try:
        body = await request.json()
        if not isinstance(body, dict) or type(body.get("won")) is not bool:
            raise ValueError("won must be a JSON boolean")
        won = body["won"]
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        return _err(400, "bad_request", e)
    db = _portfolio()
    try:
        return db.resolve_bet(bet_id, won)
    except ValueError as e:
        return _err(404, "not_found", e)
    except Exception as e:
        return _err(500, "db_error", e)
    finally:
        db.close()


@router.post("/bet/{bet_id}/undo")
async def undo_bet(bet_id: str):
    db = _portfolio()
    try:
        db.undo_resolve(bet_id)
        return {"bet_id": bet_id, "status": "pending"}
    except Exception as e:
        return _err(500, "db_error", e)
    finally:
        db.close()


@router.get("/clv")
def clv():
    """CLV series: reuses src.betting.signals.compute_clv on the signals log +
    odds history. Needs weeks of snapshots to be meaningful."""
    import pandas as pd
    if not (config.SIGNALS_LOG.exists() and config.ODDS_HISTORY.exists()):
        return {"rows": [], "mean_clv": None,
                "note": "signals_log.csv / odds_history.csv mancanti — serve accumulo snapshot"}
    try:
        from src.betting.signals import compute_clv
        signals_df = pd.read_csv(config.SIGNALS_LOG)
        odds_df = pd.read_csv(config.ODDS_HISTORY)
        rows = compute_clv(signals_df, odds_df)
        if hasattr(rows, "to_dict"):
            rows = rows.to_dict(orient="records")
        rows = [r for r in rows if isinstance(r, dict)]
        vals = [r["clv"] for r in rows if r.get("clv") is not None]
        mean = round(sum(vals) / len(vals), 4) if vals else None
        clean = []
        for r in rows:
            clean.append({k: (None if (isinstance(v, float) and v != v) else v)
                          for k, v in r.items()})
        return {"rows": clean, "mean_clv": mean,
                "note": "CLV affidabile solo con settimane di snapshot accumulati"}
    except Exception as e:  # CSV malformato, colonne mancanti, import error
        return _err(500, "clv_error", e)


@router.get("/odds")
def odds(match: str = ""):
    """Latest multi-book snapshot. No ?match= -> list of matches in the latest
    snapshot; with ?match= ('P1 vs P2') -> per-book h2h prices."""
    import pandas as pd
    if not config.ODDS_HISTORY.exists():
        return {"matches": [], "rows": [], "snapshot_ts": None}
    try:
        df = pd.read_csv(config.ODDS_HISTORY)
        if df.empty:
            return {"matches": [], "rows": [], "snapshot_ts": None}
        last_ts = df["snapshot_ts"].max()
        snap = df[(df["snapshot_ts"] == last_ts) & (df["market"] == "h2h") &
                  df["bookmaker"].isin(config.ALLOWED_BOOKMAKERS)].copy()
        snap["match"] = snap["p1"] + " vs " + snap["p2"]
        if not match:
            return {"matches": sorted(snap["match"].unique().tolist()),
                    "rows": [], "snapshot_ts": last_ts}
        rows = snap[snap["match"] == match][["bookmaker", "price_1", "price_2", "p1", "p2"]]
        return {"matches": [], "snapshot_ts": last_ts,
                "rows": json.loads(rows.to_json(orient="records"))}
    except Exception as e:
        return _err(500, "odds_error", e)


def _safe_path(rel: str):
    """Resolve a path relative to the project root; reject traversal outside it."""
    if not isinstance(rel, str) or "\x00" in rel:
        raise PermissionError("path fuori dal progetto")
    if PureWindowsPath(rel).drive:
        raise PermissionError(f"path fuori dal progetto: {rel}")
    rel = rel.replace("\\", "/")
    root = config.PROJECT_ROOT.resolve()
    p = (root / rel).resolve()
    root_str = os.fspath(root)
    p_str = os.fspath(p)
    try:
        common = os.path.commonpath([root_str, p_str])
    except ValueError as e:
        raise PermissionError("path fuori dal progetto") from e
    if os.path.normcase(common) != os.path.normcase(root_str):
        raise PermissionError(f"path fuori dal progetto: {rel}")
    return p


@router.get("/tree")
def tree(path: str = ""):
    """One directory level (lazy tree). path is relative to the project root."""
    try:
        base = _safe_path(path)
    except PermissionError as e:
        return _err(403, "forbidden", e)
    if not base.is_dir():
        return _err(404, "not_found", path)
    items = []
    try:
        for child in sorted(base.iterdir(), key=lambda c: (c.is_file(), c.name.lower())):
            if child.name in config.IGNORE_DIRS:
                continue
            items.append({
                "name": child.name,
                "dir": child.is_dir(),
                "path": child.relative_to(config.PROJECT_ROOT).as_posix(),
            })
    except OSError as e:
        return _err(500, "tree_error", e)
    return items


@router.get("/file")
def get_file(path: str):
    try:
        p = _safe_path(path)
    except PermissionError as e:
        return _err(403, "forbidden", e)
    if not p.is_file():
        return _err(404, "not_found", path)
    suffix = p.suffix.lower()
    if suffix and suffix not in config.TEXT_EXTS and p.name.lower() not in config.TEXT_EXTS:
        return _err(415, "binary", f"estensione non testuale: {p.suffix}")
    if p.stat().st_size > config.MAX_FILE_BYTES:
        return _err(413, "too_large", f"{p.stat().st_size} byte (max {config.MAX_FILE_BYTES})")
    try:
        return {"path": path, "content": p.read_text(encoding="utf-8", errors="replace")}
    except OSError as e:
        return _err(500, "read_error", e)


@router.put("/file")
async def put_file(request: Request):
    try:
        body = await request.json()
        rel, content = body.get("path"), body.get("content")
        if not rel or not isinstance(content, str):
            return _err(400, "bad_request", "servono 'path' e 'content'")
        p = _safe_path(rel)
    except PermissionError as e:
        return _err(403, "forbidden", e)
    except Exception as e:
        return _err(400, "bad_request", e)
    if not p.is_file():
        return _err(404, "not_found", "il file deve già esistere (niente create da editor)")
    if p.resolve() == config.CONFIG_YAML.resolve():
        return _save_config_content(content)
    try:
        p.write_text(content, encoding="utf-8")
        return {"saved": True, "path": rel}
    except OSError as e:
        return _err(500, "write_error", e)


def _copy_image_to_clipboard(img):
    """Put a PIL image on the Windows clipboard as CF_DIB (paste-able anywhere)."""
    import io
    try:
        import win32clipboard
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "BMP")
        data = buf.getvalue()[14:]  # strip BMP file header -> DIB
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        finally:
            win32clipboard.CloseClipboard()
        return True
    except Exception:
        return False


@router.post("/screenshot")
async def screenshot(request: Request):
    """Capture a region of the app window (client-area CSS coords + dpr) from
    the real screen, save it to reports/screenshots/ and copy it to the
    clipboard so the user can paste it anywhere."""
    import ctypes
    from ctypes import wintypes
    from datetime import datetime

    try:
        body = await request.json()
        x, y = float(body["x"]), float(body["y"])
        w, h = float(body["w"]), float(body["h"])
        dpr = float(body.get("dpr", 1.0))
    except Exception as e:
        return _err(400, "bad_request", e)
    if w < 3 or h < 3:
        return _err(400, "bad_request", "selezione troppo piccola")

    user32 = ctypes.windll.user32
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass
    hwnd = user32.FindWindowW(None, config.WINDOW_TITLE)
    if not hwnd:
        return _err(404, "no_window", "finestra dell'app non trovata")
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))

    bbox = (pt.x + round(x * dpr), pt.y + round(y * dpr),
            pt.x + round((x + w) * dpr), pt.y + round((y + h) * dpr))
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab(bbox=bbox, all_screens=True)
    except Exception as e:
        return _err(500, "grab_error", e)

    out_dir = config.PROJECT_ROOT / "reports" / "screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png"
    img.save(path)
    copied = _copy_image_to_clipboard(img)
    return {"path": path.relative_to(config.PROJECT_ROOT).as_posix(), "clipboard": copied}


@router.get("/graph")
def graph():
    """Graphify knowledge graph, slimmed for the 3D viewer."""
    import json as _json
    gpath = config.PROJECT_ROOT / "graphify-out" / "graph.json"
    if not gpath.exists():
        return _err(404, "not_found", "graph.json mancante — esegui graphify")
    try:
        g = _json.loads(gpath.read_text(encoding="utf-8"))
        nodes = [{"id": n["id"], "label": n.get("label", n["id"])[:60],
                  "group": n.get("community", 0),
                  "file": (n.get("source_file") or "")[-60:]}
                 for n in g.get("nodes", [])]
        ids = {n["id"] for n in nodes}
        links = []
        for e in g.get("links", []):
            s = e["source"] if isinstance(e["source"], str) else e["source"].get("id")
            t = e["target"] if isinstance(e["target"], str) else e["target"].get("id")
            if s in ids and t in ids:
                links.append({"source": s, "target": t})
        return {"nodes": nodes, "links": links}
    except Exception as e:
        return _err(500, "graph_error", e)


@router.get("/model")
def model():
    """Model health for the dashboard: current honest metrics + training history."""
    import json as _json
    out = {"current": None, "history": []}
    mpath = config.PROJECT_ROOT / "models" / "atp_metrics.json"
    if mpath.exists():
        try:
            m = _json.loads(mpath.read_text())
            am = m.get("all_models") or {}
            # Schema-tolerant: legacy used best_*; the routed E4 schema uses
            # routed_* + named families (target_odds_*, target_routed_ensemble).
            if "best_accuracy" in m:
                best_model = m.get("best_model")
                acc, ll = m.get("best_accuracy"), m.get("best_log_loss")
                roc, ece = m.get("best_roc_auc"), m.get("best_ece")
            else:
                best_model = "target_routed_ensemble"
                acc, ll = m.get("routed_accuracy"), m.get("routed_log_loss")
                roc, ece = m.get("routed_roc_auc"), m.get("routed_ece")
            out["current"] = {
                "best_model": best_model,
                "accuracy": acc, "log_loss": ll, "roc_auc": roc, "ece": ece,
                "trained_at": m.get("trained_at"),
                "odds_ensemble_accuracy": (am.get("target_odds_ensemble") or {}).get("accuracy"),
                "models": {k: {"accuracy": v.get("accuracy"), "log_loss": v.get("log_loss")}
                           for k, v in am.items()},
            }
        except Exception:
            pass
    hpath = config.PROJECT_ROOT / "reports" / "metrics_history.csv"
    if hpath.exists():
        try:
            import csv as _csv
            with open(hpath, newline="") as f:
                out["history"] = list(_csv.DictReader(f))
        except Exception:
            pass
    return out


@router.get("/media")
def media(path: str):
    """Stream an image/video/audio/pdf file from inside the project for in-app preview."""
    try:
        p = _safe_path(path)
    except PermissionError as e:
        return _err(403, "forbidden", e)
    if not p.is_file():
        return _err(404, "not_found", path)
    mt = MEDIA_TYPES.get(p.suffix.lower())
    if not mt:
        return _err(415, "unsupported", f"non è un media: {p.suffix}")
    return FileResponse(str(p), media_type=mt)


def _html_to_text(html: str, base_url: str = ""):
    """Dependency-free readable extraction: title, text, links."""
    import html as _h
    import re as _re
    from urllib.parse import urljoin
    title = ""
    m = _re.search(r"<title[^>]*>(.*?)</title>", html, _re.I | _re.S)
    if m:
        title = _h.unescape(_re.sub(r"\s+", " ", m.group(1))).strip()
    # links before stripping
    links = []
    for lm in _re.finditer(r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, _re.I | _re.S):
        href, txt = lm.group(1), _re.sub(r"<[^>]+>", "", lm.group(2))
        txt = _h.unescape(_re.sub(r"\s+", " ", txt)).strip()
        if txt and href and not href.startswith(("javascript:", "#")):
            links.append({"text": txt[:80], "href": urljoin(base_url, href)})
        if len(links) >= 60:
            break
    body = _re.sub(r"<(script|style|head|nav|footer|svg)[^>]*>.*?</\1>", " ", html, flags=_re.I | _re.S)
    body = _re.sub(r"<br\s*/?>", "\n", body, flags=_re.I)
    body = _re.sub(r"</(p|div|h[1-6]|li|tr)>", "\n", body, flags=_re.I)
    body = _re.sub(r"<[^>]+>", " ", body)
    body = _h.unescape(body)
    body = _re.sub(r"[ \t]+", " ", body)
    body = _re.sub(r"\n\s*\n\s*\n+", "\n\n", body).strip()
    return title, body[:20000], links


def _validate_public_http_url(url: str):
    """Reject browser targets that are not public HTTP(S) destinations."""
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as e:
        raise _UnsafeBrowseURL(f"URL non valido: {e}") from None
    if parsed.scheme.lower() not in {"http", "https"} or not hostname:
        raise _UnsafeBrowseURL("sono ammessi solo URL http/https completi")
    if parsed.username is not None or parsed.password is not None:
        raise _UnsafeBrowseURL("le credenziali nell'URL non sono ammesse")
    if "%" in hostname:
        raise _UnsafeBrowseURL("gli scope IPv6 non sono ammessi")

    _resolve_public_addresses(
        hostname, port or (443 if parsed.scheme.lower() == "https" else 80))
    return url


def _resolve_public_addresses(host, port):
    """Resolve a host and reject the whole result if any address is non-public."""
    try:
        infos = socket.getaddrinfo(
            host.rstrip("."), port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise _UnsafeBrowseURL(f"host non risolvibile: {host}") from e
    addresses = set()
    for info in infos:
        try:
            addresses.add(ipaddress.ip_address(info[4][0]))
        except ValueError as e:
            raise _UnsafeBrowseURL(
                f"indirizzo non valido per host: {host}") from e

    if not addresses:
        raise _UnsafeBrowseURL(f"host non risolvibile: {host}")
    blocked = sorted(str(address) for address in addresses if not address.is_global)
    if blocked:
        raise _UnsafeBrowseURL(
            f"destinazione di rete non pubblica non ammessa: {', '.join(blocked)}")
    return infos


def _create_public_connection(
        address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None):
    """Connect only to an address from the validated DNS result."""
    host, port = address
    last_error = None
    for family, socktype, proto, _, sockaddr in _resolve_public_addresses(host, port):
        sock = None
        try:
            sock = socket.socket(family, socktype, proto)
            if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(sockaddr)
            return sock
        except OSError as e:
            last_error = e
            if sock is not None:
                sock.close()
    if last_error is not None:
        raise last_error
    raise OSError("getaddrinfo returned no usable addresses")


class _PublicHTTPConnection(http.client.HTTPConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = _create_public_connection


class _PublicHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = _create_public_connection


class _PublicHTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req):
        return self.do_open(_PublicHTTPConnection, req)


class _PublicHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(
            _PublicHTTPSConnection, req, context=self._context,
            check_hostname=self._check_hostname)


class _PublicOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Apply public-network validation to every redirect hop."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_public_http_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch_url(url: str):
    """Fetch a public web page while preventing local-network requests."""
    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36")
    _validate_public_http_url(url)
    req = urllib.request.Request(
        url, headers={"User-Agent": ua, "Accept": "text/html,*/*"})
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _PublicHTTPHandler(),
        _PublicHTTPSHandler(),
        _PublicOnlyRedirectHandler(),
    )
    with opener.open(req, timeout=20) as response:
        _validate_public_http_url(response.geturl())
        ct = response.headers.get("Content-Type", "")
        raw = response.read(3_000_000)
    return raw.decode("utf-8", errors="replace"), ct


@router.get("/browse")
def browse(url: str):
    """Agentic browser fetch: returns title + readable text + links for a URL."""
    url = url.strip()
    if not urlsplit(url).scheme:
        url = "https://" + url
    try:
        html, ct = _fetch_url(url)
    except _UnsafeBrowseURL as e:
        return _err(400, "unsafe_url", e)
    except Exception as e:
        return _err(502, "fetch_error", e)
    if "html" not in ct and "<html" not in html[:2000].lower():
        # non-HTML (json/text): return raw, truncated
        return {"url": url, "title": url, "text": html[:20000], "links": [], "content_type": ct}
    title, text, links = _html_to_text(html, url)
    return {"url": url, "title": title or url, "text": text, "links": links, "content_type": ct}


def _git(args, timeout=90):
    import subprocess
    return subprocess.run(["git", "-C", str(config.PROJECT_ROOT)] + args,
                          capture_output=True, text=True, timeout=timeout)


def _update_remote():
    """The remote pointing at the public UnaBetting repo (fallback: origin)."""
    r = _git(["remote", "-v"])
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and config.PUBLIC_REPO.lower() in parts[1].lower():
            return parts[0]
    return "origin"


def _ver_tuple(s):
    """'v1.2.3' / '1.2.3' -> (1,2,3); non-numeric parts drop to 0."""
    import re
    nums = re.findall(r"\d+", (s or "").strip())
    return tuple(int(n) for n in nums[:3]) + (0,) * (3 - len(nums[:3]))


def _http_json(url, timeout=15):
    import json as _j
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "UnaBetting-updater",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return _j.loads(r.read().decode("utf-8"))


def _latest_release():
    return _http_json(f"https://api.github.com/repos/{config.PUBLIC_REPO}/releases/latest")


def _os_installer_tag():
    """Asset-name infix for this platform's installer (matches release.yml)."""
    import sys as _s
    return ("windows" if _s.platform.startswith("win")
            else "macos" if _s.platform == "darwin" else "linux")


@router.get("/update/check")
def update_check():
    """Packaged builds compare the local VERSION against the latest GitHub Release;
    a source checkout falls back to the git fast-forward check (for contributors)."""
    from src.runtime_paths import FROZEN, app_version
    if FROZEN:
        try:
            rel = _latest_release()
            tag = rel.get("tag_name", "")
            cur = app_version()
            assets = rel.get("assets", [])
            bundle = next((a for a in assets if a["name"].startswith("UnaBetting-runtime-")), None)
            installer = next((a for a in assets if _os_installer_tag() in a["name"]
                              and not a["name"].startswith("UnaBetting-runtime-")), None)
            available = _ver_tuple(tag) > _ver_tuple(cur)
            return {"mode": "release", "current": cur, "latest": tag,
                    "available": available,
                    "notes": (rel.get("body") or "")[:1500],
                    "latest_date": rel.get("published_at"),
                    "has_bundle": bool(bundle),
                    "installer_url": installer["browser_download_url"] if installer else None}
        except Exception as e:
            return _err(502, "update_check_failed", e)
    # dev / source checkout: git fast-forward check
    try:
        cur = _git(["rev-parse", "--short", "HEAD"]).stdout.strip()
        remote, branch = _update_remote(), config.UPDATE_BRANCH
        _git(["fetch", remote, branch], timeout=60)
        ref = f"{remote}/{branch}"
        counts = _git(["rev-list", "--left-right", "--count", f"HEAD...{ref}"]).stdout.split()
        ahead = int(counts[0]) if len(counts) == 2 else 0
        behind = int(counts[1]) if len(counts) == 2 else 0
        latest = _git(["rev-parse", "--short", ref]).stdout.strip()
        msg = _git(["log", "-1", "--format=%s", ref]).stdout.strip()
        ldate = _git(["log", "-1", "--format=%cI", ref]).stdout.strip()
        return {"mode": "git", "current": cur, "latest": latest, "behind": behind,
                "ahead": ahead, "available": behind > 0 and ahead == 0,
                "notes": msg, "latest_date": ldate}
    except Exception as e:
        return _err(502, "update_check_failed", e)


# Bundle members under these roots are app artifacts and may be overwritten; the
# user's portfolio db and settings are NEVER in the bundle, so they stay untouched.
#: Hard ceiling on the downloaded bundle (the slim runtime bundle is ~42 MB). Guards
#: against a runaway/oversized release asset filling the disk during download.
_MAX_BUNDLE_BYTES = 500 * 1024 * 1024

#: User data a bundle must never touch. Matched on the normalized (posix, lower-case)
#: path AFTER zip-slip containment, so neither case nor separator tricks (Windows/macOS
#: are case-insensitive; `data\live\x` etc.) can sneak a write onto these.
_PROTECTED_NAMES = ("betanalytix.db", "settings.json")
_PROTECTED_PREFIXES = ("data/live/",)
_CONFIG_MEMBER = "config/config.yaml"
_CONFIG_DEFAULTS_SNAPSHOT = "config/.runtime-default.yaml"
_MISSING = object()


def _is_protected(rel_posix_lower):
    name = rel_posix_lower.rsplit("/", 1)[-1]
    return (name in _PROTECTED_NAMES
            or any(rel_posix_lower.startswith(p) for p in _PROTECTED_PREFIXES))


def _load_yaml_mapping(blob, label):
    try:
        value = yaml.safe_load(blob.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as e:
        raise ValueError(f"{label} is not valid UTF-8 YAML: {e}") from None
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a YAML mapping")
    return value


def _merge_config_defaults(old, current, new):
    """Advance untouched defaults while preserving user overrides and extra keys."""
    if old is not _MISSING and current == old:
        return new
    if not isinstance(current, dict) or not isinstance(new, dict):
        return current

    old_map = old if isinstance(old, dict) else {}
    merged = {}
    for key, new_value in new.items():
        if key not in current:
            merged[key] = new_value
            continue
        old_value = old_map.get(key, _MISSING)
        merged[key] = _merge_config_defaults(old_value, current[key], new_value)
    for key, current_value in current.items():
        old_value = old_map.get(key, _MISSING)
        if key not in new and (old_value is _MISSING or current_value != old_value):
            merged[key] = current_value
    return merged


def _prepare_runtime_config(root, bundle_blob, baseline_config=None):
    """Return writes needed to safely update the persistent runtime config."""
    config_path = (root / _CONFIG_MEMBER).resolve()
    defaults_path = (root / _CONFIG_DEFAULTS_SNAPSHOT).resolve()
    if not config_path.is_relative_to(root) or not defaults_path.is_relative_to(root):
        raise ValueError("unsafe generated config path")
    new_defaults = _load_yaml_mapping(bundle_blob, "bundle config")
    writes = [(defaults_path, bundle_blob)]

    if not config_path.exists():
        writes.insert(0, (config_path, bundle_blob))
        return writes

    current_blob = config_path.read_bytes()
    current = _load_yaml_mapping(current_blob, "current config")
    old_blob = None
    if defaults_path.is_file():
        old_blob = defaults_path.read_bytes()
    elif baseline_config is not None and Path(baseline_config).is_file():
        old_blob = Path(baseline_config).read_bytes()
    old_defaults = (_load_yaml_mapping(old_blob, "previous default config")
                    if old_blob is not None else _MISSING)

    merged = _merge_config_defaults(old_defaults, current, new_defaults)
    if merged != current:
        merged_blob = yaml.safe_dump(
            merged, sort_keys=False, allow_unicode=True).encode("utf-8")
        backup_path = config_path.with_suffix(".yaml.bak").resolve()
        if not backup_path.is_relative_to(root):
            raise ValueError("unsafe generated config backup path")
        writes.insert(0, (backup_path, current_blob))
        writes.insert(1, (config_path, merged_blob))
    return writes


def _write_runtime_files_transactionally(root, writes):
    """Install validated runtime files, rolling back on any write failure."""
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    stage_dir = Path(tempfile.mkdtemp(prefix=".runtime-update-", dir=root))
    staged = []
    installed = []
    cleanup_stage = True
    try:
        destinations = set()
        for index, (destination, blob) in enumerate(writes):
            destination = Path(destination).resolve()
            if not destination.is_relative_to(root):
                raise ValueError(f"unsafe runtime update path: {destination}")
            if destination in destinations:
                raise ValueError(f"duplicate runtime update path: {destination}")
            destinations.add(destination)

            staged_path = stage_dir / f"new-{index:06d}"
            with staged_path.open("wb") as f:
                f.write(blob)
                f.flush()
                os.fsync(f.fileno())
            staged.append((destination, staged_path, stage_dir / f"old-{index:06d}"))

        for destination, staged_path, backup_path in staged:
            destination.parent.mkdir(parents=True, exist_ok=True)
            backup = None
            if destination.exists():
                if not destination.is_file():
                    raise OSError(f"runtime update target is not a file: {destination}")
                os.replace(destination, backup_path)
                backup = backup_path
            installed.append((destination, backup))
            os.replace(staged_path, destination)
    except Exception as install_error:
        rollback_errors = []
        for destination, backup in reversed(installed):
            try:
                if backup is None:
                    destination.unlink(missing_ok=True)
                else:
                    os.replace(backup, destination)
            except OSError as rollback_error:
                rollback_errors.append(f"{destination}: {rollback_error}")
        if rollback_errors:
            cleanup_stage = False
            detail = "; ".join(rollback_errors)
            raise OSError(
                f"runtime update failed ({install_error}); rollback incomplete "
                f"({detail}); recovery files kept in {stage_dir}"
            ) from install_error
        raise
    finally:
        if cleanup_stage:
            shutil.rmtree(stage_dir, ignore_errors=True)


#: Ed25519 public key that signs release bundles. Module-level so tests can inject a
#: test keypair via monkeypatch; production keeps this baked-in key.
_UPDATER_PUBKEY = b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAx5CLlxfVh6r1rPNaBcJqQhr1zgNDcAEkXTIvIUXs1Mc=
-----END PUBLIC KEY-----"""


def _extract_runtime_bundle(zip_path, data_root, baseline_config=None):
    """Extract a runtime bundle into data_root. Returns the number of files written.

    INTEGRITY, NOT AUTHENTICITY: manifest.json lives inside the same zip it attests,
    so the sha256 checks only catch accidental corruption / truncation, NOT a
    tampered or malicious bundle (an attacker who alters files just rewrites the
    hashes). The bundle is trusted because it is fetched over HTTPS from the
    project's own GitHub Releases — see the signing follow-up in CLAUDE.md.

    Every member is validated BEFORE anything is written (a rejected bundle writes
    nothing): it must resolve inside data_root (zip-slip / absolute-path guard), be
    listed in the manifest with a matching size and sha256, and the manifest must not
    list files absent from the zip. Protected user paths (_is_protected) are skipped.
    Runtime config is three-way merged against the previous shipped defaults so new
    defaults land without replacing user overrides; the prior config is backed up.
    Schema produced by scripts/build_release_bundle.py. Raises ValueError on any
    violation.
    """
    import hashlib
    import zipfile
    import base64
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization
    from cryptography.exceptions import InvalidSignature

    # Verification key read at call time from the module global, so tests can inject a
    # test keypair (production uses the baked-in key below).
    UPDATER_PUBKEY = _UPDATER_PUBKEY

    root = Path(data_root).resolve()
    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        raise ValueError("not a valid zip bundle") from None
    with zf:
        try:
            raw_manifest = zf.read("manifest.json")
            manifest = json.loads(raw_manifest)
        except KeyError:
            raise ValueError("bundle has no manifest.json — refusing to extract") from None
        except json.JSONDecodeError as e:
            raise ValueError(f"manifest.json is not valid JSON: {e}") from None
            
        sig_b64 = manifest.pop("signature", None)
        if not sig_b64:
            raise ValueError("unsigned bundle — refusing to extract")
            
        try:
            pubkey = serialization.load_pem_public_key(UPDATER_PUBKEY)
            if not isinstance(pubkey, ed25519.Ed25519PublicKey):
                raise ValueError("invalid baked public key type")
                
            # Reconstruct the exact canonical JSON that was signed
            payload = json.dumps(manifest, separators=(',', ':'), sort_keys=True).encode("utf-8")
            pubkey.verify(base64.b64decode(sig_b64), payload)
        except InvalidSignature:
            raise ValueError("bundle signature verification failed — refusing to extract")
        except Exception as e:
            raise ValueError(f"error verifying signature: {e}")
            
        try:
            expected = {f["path"]: (f["sha256"], int(f["bytes"]))
                        for f in manifest.get("files", [])}
        except (KeyError, TypeError, ValueError):
            raise ValueError("malformed manifest entry") from None

        # Containment first: reject any zip-slip / absolute-path member BEFORE the
        # manifest checks, so an unsafe path is caught deterministically on every OS
        # (Windows normalizes backslash/absolute names, which would otherwise trip the
        # manifest-absent check first) and even if it were also listed in the manifest.
        for m in zf.namelist():
            if m.endswith("/") or m == "manifest.json":
                continue
            if not (root / m).resolve().is_relative_to(root):
                raise ValueError(f"unsafe path in bundle: {m}")

        members = set(zf.namelist())
        absent = sorted(p for p in expected if p not in members)
        if absent:
            raise ValueError(f"manifest lists files absent from bundle: {absent[:5]}")

        to_write = []  # validate-all-then-write: (dst, blob)
        config_blob = None
        for m in zf.namelist():
            if m.endswith("/") or m == "manifest.json":
                continue
            dst = (root / m).resolve()
            if not dst.is_relative_to(root):
                raise ValueError(f"unsafe path in bundle: {m}")
            if _is_protected(dst.relative_to(root).as_posix().lower()):
                continue
            entry = expected.get(m)
            if entry is None:
                raise ValueError(f"file not in manifest: {m}")
            sha, size = entry
            blob = zf.read(m)
            if len(blob) != size:
                raise ValueError(f"size mismatch: {m}")
            if hashlib.sha256(blob).hexdigest() != sha:
                raise ValueError(f"sha256 mismatch: {m}")
            if m == _CONFIG_MEMBER:
                config_blob = blob
            else:
                to_write.append((dst, blob))

        if not to_write and config_blob is None:
            raise ValueError("bundle contains no installable files")

        config_writes = []
        if config_blob is not None:
            try:
                config_writes = _prepare_runtime_config(
                    root, config_blob, baseline_config=baseline_config)
            except OSError as e:
                raise ValueError(f"cannot prepare runtime config: {e}") from None

        _write_runtime_files_transactionally(root, to_write + config_writes)
    return len(to_write) + (1 if config_blob is not None else 0)


@router.post("/update/apply")
def update_apply():
    """Packaged: download the latest runtime bundle and extract it into DATA_ROOT
    (models + reference data + merged config), preserving the user's portfolio db,
    settings, and config overrides. Source checkout: git fast-forward pull."""
    from src.runtime_paths import BUNDLE_DIR, FROZEN, DATA_ROOT, app_version
    if FROZEN:
        import tempfile
        import urllib.request
        try:
            rel = _latest_release()
            tag = rel.get("tag_name", "")
            if _ver_tuple(tag) <= _ver_tuple(app_version()):
                return {"ok": True, "updated": False, "version": app_version(),
                        "output": "Already up to date."}
            bundle = next((a for a in rel.get("assets", [])
                           if a["name"].startswith("UnaBetting-runtime-")), None)
            if not bundle:
                return {"ok": False, "updated": False,
                        "output": "New app version needs the installer (no in-place "
                                  "bundle). Download it from the Releases page.",
                        "installer_required": True}
            url = bundle["browser_download_url"]
            if not url.startswith("https://"):
                return _err(502, "bundle_rejected", "download URL is not https")
            # Path(...).name: never trust the asset name as a path component.
            tmp = Path(tempfile.gettempdir()) / Path(bundle["name"]).name
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "UnaBetting-updater"})
                got = 0
                with urllib.request.urlopen(req, timeout=120) as r, tmp.open("wb") as f:
                    while chunk := r.read(1 << 20):
                        got += len(chunk)
                        if got > _MAX_BUNDLE_BYTES:
                            raise ValueError("bundle exceeds size limit")
                        f.write(chunk)
                n = _extract_runtime_bundle(
                    tmp, DATA_ROOT,
                    baseline_config=BUNDLE_DIR / "config" / "config.yaml")
            except ValueError as e:
                return _err(502, "bundle_rejected", e)
            finally:
                tmp.unlink(missing_ok=True)
            (DATA_ROOT / "VERSION").write_text(tag.lstrip("v") + "\n", encoding="utf-8")
            return {"ok": True, "updated": True, "version": tag, "files": n,
                    "restart_required": True,
                    "output": f"Updated to {tag} ({n} files). Restart to apply."}
        except Exception as e:
            return _err(500, "update_failed", e)
    # dev / source checkout: git ff-only pull
    try:
        remote, branch = _update_remote(), config.UPDATE_BRANCH
        r = _git(["pull", "--ff-only", remote, branch], timeout=180)
        ok = r.returncode == 0
        out = (r.stdout + r.stderr).strip()[-1500:]
        return {"ok": ok, "output": out,
                "restart_required": ok and "Already up to date" not in out}
    except Exception as e:
        return _err(500, "update_failed", e)


@router.get("/loops")
def loops():
    """Loop run logs (reports/loops) newest first, for the Loops panel."""
    if not config.LOOPS_LOG_DIR.exists():
        return []
    out = []
    for f in sorted(config.LOOPS_LOG_DIR.glob("*.log"),
                    key=lambda x: x.stat().st_mtime, reverse=True):
        out.append({"name": f.name, "size": f.stat().st_size,
                    "mtime": f.stat().st_mtime,
                    "path": f.relative_to(config.PROJECT_ROOT).as_posix()})
    return out


@router.get("/config")
def get_config():
    try:
        return {"path": str(config.CONFIG_YAML),
                "content": config.CONFIG_YAML.read_text(encoding="utf-8")}
    except OSError as e:
        return _err(500, "config_read_error", e)


@router.put("/config")
async def put_config(request: Request):
    try:
        body = await request.json()
        content = body.get("content")
    except Exception as e:
        return _err(400, "bad_request", e)
    return _save_config_content(content)


@router.get("/chat/config")
def get_chat_config():
    return chat.load_chat_settings()


@router.put("/chat/config")
async def put_chat_config(request: Request):
    try:
        body = await request.json()
        return chat.save_chat_settings(body)
    except (ValueError, json.JSONDecodeError) as e:
        return _err(400, "invalid_chat_config", e)
    except OSError as e:
        return _err(500, "chat_config_write_error", e)


def _chat_unavailable(error):
    provider = chat.load_chat_settings()["provider"]
    code = "ollama_unavailable" if provider == "ollama" else \
        "chat_provider_unavailable"
    return _err(502, code, error)


@router.get("/chat/models")
def get_chat_models(
        ram_gb: float | None = Query(default=None, ge=1, le=4096),
        vram_gb: float | None = Query(default=None, ge=0, le=1024)):
    try:
        return chat.list_ollama_models(
            total_ram_bytes=int(ram_gb * chat.GIB) if ram_gb is not None else None,
            total_vram_bytes=int(vram_gb * chat.GIB) if vram_gb is not None else None,
        )
    except (OSError, ValueError, json.JSONDecodeError) as e:
        return _chat_unavailable(e)


@router.post("/chat/test")
def test_chat_model():
    try:
        return chat.run_chat_self_test()
    except (OSError, ValueError, json.JSONDecodeError) as e:
        return _chat_unavailable(e)
