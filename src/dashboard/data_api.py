"""REST API: read-only data cockpit + config editor (the only writing endpoint)."""
import json
import shutil
import sqlite3

import yaml
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse

from . import config

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


def _err(status, error, detail=""):
    return JSONResponse({"error": error, "detail": str(detail)}, status_code=status)


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
                "ORDER BY timestamp DESC LIMIT 1").fetchone()
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


@router.post("/bet")
async def place_bet(request: Request):
    """Register a manually placed bet (Bet-Analytix style tracking)."""
    try:
        b = await request.json()
        match_str = str(b["match_str"]).strip()
        side_name = str(b["side_name"]).strip()
        odds = float(b["odds"])
        stake = float(b["stake"])
        if not match_str or not side_name or odds <= 1.0 or stake <= 0:
            raise ValueError("match, giocatore, quota>1 e stake>0 obbligatori")
    except Exception as e:
        return _err(400, "bad_request", e)
    db = _portfolio()
    try:
        bet_id = db.place_bet(
            decision_id=str(b.get("decision_id", "")), side=int(b.get("side", 0)),
            side_name=side_name, odds=odds,
            model_prob=float(b.get("model_prob") or 0), edge=float(b.get("edge") or 0),
            kelly_pct=float(b.get("kelly_pct") or 0), stake=stake,
            match_str=match_str, notes=str(b.get("notes", "")))
        return {"bet_id": bet_id}
    except Exception as e:
        return _err(500, "db_error", e)
    finally:
        db.close()


@router.post("/bet/{bet_id}/resolve")
async def resolve_bet(bet_id: str, request: Request):
    try:
        won = bool((await request.json()).get("won"))
    except Exception as e:
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
    p = (config.PROJECT_ROOT / rel).resolve()
    root = str(config.PROJECT_ROOT.resolve())
    if not (str(p) == root or str(p).startswith(root + "\\") or str(p).startswith(root + "/")):
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
    out = {"current": None, "history": [], "market_baseline": 0.677}
    mpath = config.PROJECT_ROOT / "models" / "atp_metrics.json"
    if mpath.exists():
        try:
            m = _json.loads(mpath.read_text())
            out["current"] = {
                "best_model": m.get("best_model"),
                "accuracy": m.get("best_accuracy"),
                "log_loss": m.get("best_log_loss"),
                "roc_auc": m.get("best_roc_auc"),
                "ece": m.get("best_ece"),
                "trained_at": m.get("trained_at"),
                "models": {k: {"accuracy": v.get("accuracy"), "log_loss": v.get("log_loss")}
                           for k, v in (m.get("all_models") or {}).items()},
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


def _fetch_url(url: str):
    """Server-side fetch (urllib, curl.exe fallback for picky sites)."""
    import urllib.request
    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "text/html,*/*"})
        with urllib.request.urlopen(req, timeout=20) as r:
            ct = r.headers.get("Content-Type", "")
            raw = r.read(3_000_000)
        return raw.decode("utf-8", errors="replace"), ct
    except Exception:
        import subprocess
        r = subprocess.run(["curl.exe", "-sL", "--compressed", "-m", "25",
                            "-A", ua, url], capture_output=True, timeout=40)
        if r.returncode != 0 or not r.stdout:
            raise RuntimeError(f"fetch fallito (curl {r.returncode})")
        return r.stdout.decode("utf-8", errors="replace"), "text/html"


@router.get("/browse")
def browse(url: str):
    """Agentic browser fetch: returns title + readable text + links for a URL."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        html, ct = _fetch_url(url)
    except Exception as e:
        return _err(502, "fetch_error", e)
    if "html" not in ct and "<html" not in html[:2000].lower():
        # non-HTML (json/text): return raw, truncated
        return {"url": url, "title": url, "text": html[:20000], "links": [], "content_type": ct}
    title, text, links = _html_to_text(html, url)
    return {"url": url, "title": title or url, "text": text, "links": links, "content_type": ct}


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
        if not isinstance(content, str) or not content.strip():
            return _err(400, "bad_request", "campo 'content' mancante o vuoto")
        yaml.safe_load(content)  # reject invalid YAML before touching the file
    except yaml.YAMLError as e:
        return _err(400, "invalid_yaml", e)
    except Exception as e:
        return _err(400, "bad_request", e)
    try:
        backup = config.CONFIG_YAML.with_suffix(".yaml.bak")
        shutil.copy2(config.CONFIG_YAML, backup)
        config.CONFIG_YAML.write_text(content, encoding="utf-8")
        return {"saved": True, "backup": str(backup)}
    except OSError as e:
        return _err(500, "config_write_error", e)
