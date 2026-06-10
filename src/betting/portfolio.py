"""
BetAnalytix v1.0 — Tennis Betting Decision Database
====================================================
SQLite-backed system that tracks EVERY model decision, placed bet,
and result. Provides analytics for strategy refinement.

Tables:
  decisions   - Every scan signal (prob, edge, kelly, news adj, research)
  bets        - Placed bets (stake, odds, side, linked to decision)
  results     - Resolved outcomes (won/lost, profit, bankroll after)
  daily_stats - End-of-day snapshots (bankroll, ROI, drawdown, win rate)
"""

import os
import json
import sqlite3
import threading
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "betanalytix.db"


class BetAnalytix:
    """SQLite-backed betting decision database."""

    def __init__(self, db_path: str | Path = DB_PATH):
        self._db_path = str(db_path)
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        # Defensive lock around multi-step ops (place_bet, resolve_bet).
        # WAL + check_same_thread=False alone does not prevent read-then-write races.
        self._lock = threading.Lock()
        self._create_tables()
        self._migrate_schema()

    def _migrate_schema(self):
        """Idempotent schema upgrades for older DBs."""
        cols = {r["name"] for r in self._conn.execute("PRAGMA table_info(bets)").fetchall()}
        if "idempotency_key" not in cols:
            # Nullable + UNIQUE index so old rows (NULL) coexist; new rows enforce uniqueness.
            self._conn.execute("ALTER TABLE bets ADD COLUMN idempotency_key TEXT")
            self._conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_bets_idempotency "
                "ON bets(idempotency_key) WHERE idempotency_key IS NOT NULL"
            )
            self._conn.commit()

    def _create_tables(self):
        c = self._conn
        c.executescript("""
        CREATE TABLE IF NOT EXISTS decisions (
            id          TEXT PRIMARY KEY,
            scan_id     TEXT NOT NULL,
            timestamp   TEXT NOT NULL,
            match_str   TEXT NOT NULL,
            p1_name     TEXT,
            p2_name     TEXT,
            tournament  TEXT,
            tourney_level TEXT,
            surface     TEXT,
            odds_1      REAL,
            odds_2      REAL,
            ml_prob_1   REAL,
            ml_prob_2   REAL,
            news_adj_prob_1 REAL,
            news_adj_prob_2 REAL,
            news_adjustment REAL DEFAULT 0.0,
            news_confidence REAL DEFAULT 0.0,
            news_reason TEXT,
            news_sources TEXT,
            edge        REAL,
            value_side  INTEGER,
            kelly_fraction REAL,
            suggested_stake REAL,
            exp_game_diff REAL,
            exp_total_games REAL,
            market_spread REAL,
            market_total REAL,
            low_confidence INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS bets (
            id          TEXT PRIMARY KEY,
            decision_id TEXT NOT NULL REFERENCES decisions(id),
            timestamp   TEXT NOT NULL,
            match_str   TEXT NOT NULL,
            side        INTEGER NOT NULL,
            side_name   TEXT,
            odds        REAL NOT NULL,
            model_prob  REAL NOT NULL,
            edge        REAL NOT NULL,
            kelly_pct   REAL NOT NULL,
            stake       REAL NOT NULL,
            status      TEXT NOT NULL DEFAULT 'pending',
            profit      REAL,
            bankroll_after REAL,
            resolved_at TEXT,
            notes       TEXT
        );

        CREATE TABLE IF NOT EXISTS daily_stats (
            date        TEXT PRIMARY KEY,
            bankroll    REAL NOT NULL,
            total_bets  INTEGER DEFAULT 0,
            won         INTEGER DEFAULT 0,
            lost        INTEGER DEFAULT 0,
            pending     INTEGER DEFAULT 0,
            total_staked REAL DEFAULT 0.0,
            total_profit REAL DEFAULT 0.0,
            roi_pct     REAL DEFAULT 0.0,
            max_drawdown_pct REAL DEFAULT 0.0,
            win_rate    REAL DEFAULT 0.0,
            best_bet    TEXT,
            worst_bet   TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_decisions_scan ON decisions(scan_id);
        CREATE INDEX IF NOT EXISTS idx_decisions_time ON decisions(timestamp);
        CREATE INDEX IF NOT EXISTS idx_bets_status ON bets(status);
        CREATE INDEX IF NOT EXISTS idx_bets_decision ON bets(decision_id);
        """)
        c.commit()

    # ==============================================================
    # DECISIONS — Log every model signal from scan
    # ==============================================================

    def log_decisions(self, predictions: list, scan_id: str = None) -> str:
        """Log all predictions from a scan as decisions. Returns scan_id."""
        if not scan_id:
            scan_id = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        ts = datetime.now().isoformat()
        rows = []

        for p in predictions:
            f = p.get("forensics", {})
            adj = p.get("news_adjustment") or {}
            decision_id = f"dec_{uuid.uuid4().hex[:12]}"

            rows.append((
                decision_id,
                scan_id,
                ts,
                p.get("match", ""),
                f.get("p1_name", ""),
                f.get("p2_name", ""),
                f.get("tourney_name", ""),
                f.get("tourney_level", ""),
                p.get("surface", ""),
                p.get("odds_1", 0),
                p.get("odds_2", 0),
                p.get("raw_prob_1", p.get("prob_1", 0)),
                p.get("raw_prob_2", p.get("prob_2", 0)),
                p.get("prob_1", 0),
                p.get("prob_2", 0),
                adj.get("effective", 0),
                adj.get("confidence", 0),
                adj.get("reason", ""),
                json.dumps(adj.get("sources", []), ensure_ascii=False),
                p.get("edge", 0),
                p.get("value_side", 0),
                p.get("kelly_fraction", 0),
                p.get("suggested_stake", 0),
                p.get("exp_game_diff", 0),
                p.get("exp_total_games", 0),
                p.get("market_spread", 0),
                p.get("market_total", 0),
                1 if p.get("low_confidence") else 0,
            ))

        self._conn.executemany("""
            INSERT OR REPLACE INTO decisions (
                id, scan_id, timestamp, match_str, p1_name, p2_name,
                tournament, tourney_level, surface,
                odds_1, odds_2, ml_prob_1, ml_prob_2,
                news_adj_prob_1, news_adj_prob_2,
                news_adjustment, news_confidence, news_reason, news_sources,
                edge, value_side, kelly_fraction, suggested_stake,
                exp_game_diff, exp_total_games, market_spread, market_total,
                low_confidence
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        self._conn.commit()
        return scan_id

    def get_decisions(self, limit: int = 100, scan_id: str = None) -> list[dict]:
        """Get recent decisions, optionally filtered by scan."""
        if scan_id:
            rows = self._conn.execute(
                "SELECT * FROM decisions WHERE scan_id=? ORDER BY timestamp DESC",
                (scan_id,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM decisions ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_decision_by_match(self, match_str: str) -> Optional[dict]:
        """Get the latest decision for a specific match."""
        row = self._conn.execute(
            "SELECT * FROM decisions WHERE match_str=? ORDER BY timestamp DESC LIMIT 1",
            (match_str,)
        ).fetchone()
        return dict(row) if row else None

    # ==============================================================
    # BETS — Track placed bets
    # ==============================================================

    def place_bet(self, decision_id: str, side: int, side_name: str,
                  odds: float, model_prob: float, edge: float,
                  kelly_pct: float, stake: float,
                  match_str: str = "", notes: str = "",
                  idempotency_key: Optional[str] = None) -> str:
        """Record a placed bet. Returns bet_id.

        If idempotency_key is provided and a row with that key already exists,
        the existing bet_id is returned — no duplicate row is created.
        """
        ts = datetime.now().isoformat()
        with self._lock, self._conn:
            if idempotency_key:
                existing = self._conn.execute(
                    "SELECT id FROM bets WHERE idempotency_key=?", (idempotency_key,)
                ).fetchone()
                if existing:
                    return existing["id"]

            bet_id = f"bet_{uuid.uuid4().hex[:12]}"
            self._conn.execute("""
                INSERT INTO bets (id, decision_id, timestamp, match_str,
                    side, side_name, odds, model_prob, edge,
                    kelly_pct, stake, status, notes, idempotency_key)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (bet_id, decision_id, ts, match_str,
                  side, side_name, odds, model_prob, edge,
                  kelly_pct, stake, "pending", notes, idempotency_key))
            return bet_id

    def resolve_bet(self, bet_id: str, won: bool) -> dict:
        """Mark a bet as won or lost. Updates profit and bankroll atomically."""
        # Lock + implicit transaction (`with self._conn:`): read-then-update is atomic.
        with self._lock, self._conn:
            bet = self._conn.execute("SELECT * FROM bets WHERE id=?", (bet_id,)).fetchone()
            if not bet:
                raise ValueError(f"Bet {bet_id} not found")

            bet = dict(bet)
            if bet.get("status") in ("won", "lost"):
                # Idempotent resolve — do not double-apply P&L
                return {
                    "bet_id": bet_id, "status": bet["status"],
                    "profit": bet.get("profit", 0),
                    "bankroll": bet.get("bankroll_after", self.get_bankroll()),
                }

            if won:
                profit = bet["stake"] * (bet["odds"] - 1)
                status = "won"
            else:
                profit = -bet["stake"]
                status = "lost"

            bankroll = self.get_bankroll()
            new_bankroll = bankroll + profit

            self._conn.execute("""
                UPDATE bets SET status=?, profit=?, bankroll_after=?, resolved_at=?
                WHERE id=?
            """, (status, profit, new_bankroll, datetime.now().isoformat(), bet_id))

            return {"bet_id": bet_id, "status": status, "profit": profit, "bankroll": new_bankroll}

    def undo_resolve(self, bet_id: str):
        """Undo a resolution, set bet back to pending."""
        self._conn.execute("""
            UPDATE bets SET status='pending', profit=NULL, bankroll_after=NULL, resolved_at=NULL
            WHERE id=?
        """, (bet_id,))
        self._conn.commit()

    def get_bets(self, status: str = None, limit: int = 100) -> list[dict]:
        """Get bets, optionally filtered by status."""
        if status:
            rows = self._conn.execute(
                "SELECT * FROM bets WHERE status=? ORDER BY timestamp DESC LIMIT ?",
                (status, limit)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM bets ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_pending_bets(self) -> list[dict]:
        return self.get_bets(status="pending", limit=500)

    # ==============================================================
    # BANKROLL — Calculate from initial + all resolved bets
    # ==============================================================

    def get_bankroll(self) -> float:
        """Calculate current bankroll from initial + all resolved P&L."""
        try:
            import yaml
            with open(PROJECT_ROOT / "config" / "config.yaml") as f:
                config = yaml.safe_load(f)
            initial = config.get("betting", {}).get("initial_bankroll", 1000)
        except Exception:
            initial = 1000

        row = self._conn.execute(
            "SELECT COALESCE(SUM(profit), 0) as total_pl FROM bets WHERE status IN ('won', 'lost')"
        ).fetchone()
        return initial + (row["total_pl"] if row else 0)

    # ==============================================================
    # ANALYTICS — Performance stats
    # ==============================================================

    def get_stats(self) -> dict:
        """Get comprehensive performance statistics."""
        bets = self.get_bets(limit=10000)
        resolved = [b for b in bets if b["status"] in ("won", "lost")]
        pending = [b for b in bets if b["status"] == "pending"]

        if not resolved:
            return {
                "total_bets": 0, "pending": len(pending),
                "won": 0, "lost": 0, "win_rate": 0,
                "total_staked": 0, "total_profit": 0,
                "roi": 0, "bankroll": self.get_bankroll(),
                "max_drawdown": 0, "current_streak": 0,
                "best_bet": None, "worst_bet": None,
                "by_surface": {}, "by_edge_range": {},
                "monthly": {},
            }

        won = [b for b in resolved if b["status"] == "won"]
        lost = [b for b in resolved if b["status"] == "lost"]
        total_staked = sum(b["stake"] for b in resolved)
        total_profit = sum(b["profit"] or 0 for b in resolved)
        win_rate = len(won) / len(resolved) if resolved else 0

        # Current streak
        streak = 0
        for b in sorted(resolved, key=lambda x: x["resolved_at"] or "", reverse=True):
            if streak == 0:
                streak_type = b["status"]
                streak = 1
            elif b["status"] == streak_type:
                streak += 1
            else:
                break
        streak_val = streak if streak_type == "won" else -streak

        # Max drawdown — SQL window function (O(n) in engine, no Python loop)
        dd_row = self._conn.execute("""
            SELECT COALESCE(MAX(running_peak - cumulative), 0) AS max_dd FROM (
                SELECT
                    SUM(COALESCE(profit, 0)) OVER (ORDER BY COALESCE(resolved_at, timestamp)) AS cumulative,
                    MAX(SUM(COALESCE(profit, 0))) OVER (ORDER BY COALESCE(resolved_at, timestamp)) AS running_peak
                FROM bets
                WHERE status IN ('won', 'lost')
            )
        """).fetchone()
        max_dd = float(dd_row["max_dd"] if dd_row else 0)

        # By surface
        by_surface = {}
        for b in resolved:
            # Get surface from linked decision
            dec = self._conn.execute(
                "SELECT surface FROM decisions WHERE id=?", (b["decision_id"],)
            ).fetchone()
            surf = dict(dec)["surface"] if dec else "Unknown"
            if surf not in by_surface:
                by_surface[surf] = {"bets": 0, "won": 0, "profit": 0, "staked": 0}
            by_surface[surf]["bets"] += 1
            by_surface[surf]["staked"] += b["stake"]
            by_surface[surf]["profit"] += b["profit"] or 0
            if b["status"] == "won":
                by_surface[surf]["won"] += 1

        for s in by_surface.values():
            s["win_rate"] = s["won"] / s["bets"] if s["bets"] > 0 else 0
            s["roi"] = s["profit"] / s["staked"] if s["staked"] > 0 else 0

        # By edge range
        by_edge = {"0-5%": {"bets": 0, "won": 0, "profit": 0, "staked": 0},
                   "5-10%": {"bets": 0, "won": 0, "profit": 0, "staked": 0},
                   "10-20%": {"bets": 0, "won": 0, "profit": 0, "staked": 0},
                   "20%+": {"bets": 0, "won": 0, "profit": 0, "staked": 0}}
        for b in resolved:
            e = abs(b["edge"]) * 100
            if e < 5:
                bucket = "0-5%"
            elif e < 10:
                bucket = "5-10%"
            elif e < 20:
                bucket = "10-20%"
            else:
                bucket = "20%+"
            by_edge[bucket]["bets"] += 1
            by_edge[bucket]["staked"] += b["stake"]
            by_edge[bucket]["profit"] += b["profit"] or 0
            if b["status"] == "won":
                by_edge[bucket]["won"] += 1

        for bucket in by_edge.values():
            bucket["win_rate"] = bucket["won"] / bucket["bets"] if bucket["bets"] > 0 else 0
            bucket["roi"] = bucket["profit"] / bucket["staked"] if bucket["staked"] > 0 else 0

        # Monthly
        monthly = {}
        for b in resolved:
            month = (b["resolved_at"] or b["timestamp"])[:7]
            if month not in monthly:
                monthly[month] = {"bets": 0, "won": 0, "profit": 0, "staked": 0}
            monthly[month]["bets"] += 1
            monthly[month]["staked"] += b["stake"]
            monthly[month]["profit"] += b["profit"] or 0
            if b["status"] == "won":
                monthly[month]["won"] += 1

        # Best / worst bet
        best = max(resolved, key=lambda b: b["profit"] or 0)
        worst = min(resolved, key=lambda b: b["profit"] or 0)

        return {
            "total_bets": len(resolved),
            "pending": len(pending),
            "won": len(won),
            "lost": len(lost),
            "win_rate": win_rate,
            "total_staked": total_staked,
            "total_profit": total_profit,
            "roi": total_profit / total_staked if total_staked > 0 else 0,
            "bankroll": self.get_bankroll(),
            "max_drawdown": max_dd,
            "current_streak": streak_val,
            "best_bet": {"match": best["match_str"], "profit": best["profit"]},
            "worst_bet": {"match": worst["match_str"], "profit": worst["profit"]},
            "by_surface": by_surface,
            "by_edge_range": by_edge,
            "monthly": dict(sorted(monthly.items())),
        }

    def get_today_pnl(self) -> float:
        """Get today's profit/loss."""
        today = date.today().isoformat()
        row = self._conn.execute(
            "SELECT COALESCE(SUM(profit), 0) as pnl FROM bets WHERE resolved_at LIKE ? AND status IN ('won','lost')",
            (f"{today}%",)
        ).fetchone()
        return row["pnl"] if row else 0.0

    def get_today_bets(self) -> list[dict]:
        """Get all of today's bets."""
        today = date.today().isoformat()
        rows = self._conn.execute(
            "SELECT * FROM bets WHERE timestamp LIKE ? ORDER BY timestamp DESC",
            (f"{today}%",)
        ).fetchall()
        return [dict(r) for r in rows]

    def save_daily_snapshot(self):
        """Save end-of-day stats snapshot."""
        stats = self.get_stats()
        today = date.today().isoformat()

        self._conn.execute("""
            INSERT OR REPLACE INTO daily_stats (
                date, bankroll, total_bets, won, lost, pending,
                total_staked, total_profit, roi_pct, max_drawdown_pct,
                win_rate, best_bet, worst_bet
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            today,
            stats["bankroll"],
            stats["total_bets"],
            stats["won"],
            stats["lost"],
            stats["pending"],
            stats["total_staked"],
            stats["total_profit"],
            stats["roi"] * 100,
            stats["max_drawdown"],
            stats["win_rate"] * 100,
            json.dumps(stats["best_bet"], ensure_ascii=False) if stats["best_bet"] else None,
            json.dumps(stats["worst_bet"], ensure_ascii=False) if stats["worst_bet"] else None,
        ))
        self._conn.commit()

    def get_daily_history(self, days: int = 90) -> list[dict]:
        """Get daily stats history for charts."""
        rows = self._conn.execute(
            "SELECT * FROM daily_stats ORDER BY date DESC LIMIT ?",
            (days,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ==============================================================
    # DECISION COUNT / HISTORY
    # ==============================================================

    def get_scan_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(DISTINCT scan_id) as c FROM decisions").fetchone()
        return row["c"] if row else 0

    def get_decision_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) as c FROM decisions").fetchone()
        return row["c"] if row else 0

    def close(self):
        self._conn.close()
