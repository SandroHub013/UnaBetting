"""
Tennis Pro Terminal v5.0 — Multi-Market Betting TUI
====================================================
Tabs: Markets | Forensics | Agent | Dashboard
Features:
  - Real Kelly Criterion (fractional, capped)
  - Strategy presets (Conservative / Balanced / Aggressive / Custom)
  - BetAnalytix integration (decision logging)
  - News adjustment indicator with source count
  - Real model metrics in ticker
  - Dashboard with performance analytics
"""
import os
from dotenv import load_dotenv
load_dotenv()

import subprocess
import json
from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import (
    Header, Footer, Static, DataTable, Input, Button,
    TabbedContent, TabPane, ProgressBar, RichLog, Select,
)
from textual.binding import Binding
from textual import work
from rich.text import Text
from src.live.agent_llm import AgentLLM
from src.ui.audio_engine import AudioEngine
# from src.betting.portfolio import BetAnalytix
# from src.betting.backtest import kelly_fraction as calc_kelly

CUR_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CUR_DIR))
PRED_PATH = os.path.join(PROJECT_ROOT, "data", "live", "predictions.json")
METRICS_PATH = os.path.join(PROJECT_ROOT, "models", "atp_metrics.json")

# ── Strategy Presets ──────────────────────────────────────────
STRATEGY_PRESETS = {
    "conservative": {
        "label": "Conservative",
        "min_edge": 0.10,
        "kelly_mult": 0.15,
        "max_odds": 5.0,
        "min_odds": 1.30,
    },
    "balanced": {
        "label": "Balanced",
        "min_edge": 0.05,
        "kelly_mult": 0.25,
        "max_odds": 8.0,
        "min_odds": 1.20,
    },
    "aggressive": {
        "label": "Aggressive",
        "min_edge": 0.03,
        "kelly_mult": 0.35,
        "max_odds": 10.0,
        "min_odds": 1.15,
    },
    "custom": {
        "label": "Custom",
        "min_edge": 0.0,
        "kelly_mult": 0.25,
        "max_odds": 99.0,
        "min_odds": 1.01,
    },
}

STRATEGY_OPTIONS = [
    ("Conservative (edge>=10%, K15%)", "conservative"),
    ("Balanced (edge>=5%, K25%)", "balanced"),
    ("Aggressive (edge>=3%, K35%)", "aggressive"),
    ("Custom (manual filters)", "custom"),
]

# ── Surface detection fallback ────────────────────────────────
_SURFACE_KEYWORDS = {
    'wimbledon': 'Grass', 'halle': 'Grass', "queen's": 'Grass', 'queens': 'Grass',
    'eastbourne': 'Grass', 'hertogenbosch': 'Grass', 's hertogenbosch': 'Grass',
    'mallorca': 'Grass', 'newport': 'Grass',
    'roland garros': 'Clay', 'french open': 'Clay',
    'monte carlo': 'Clay', 'monte_carlo': 'Clay', 'montecarlo': 'Clay',
    'madrid': 'Clay', 'rome': 'Clay', 'roma': 'Clay', 'barcelona': 'Clay',
    'lyon': 'Clay', 'hamburg': 'Clay', 'bastad': 'Clay', 'kitzbuhel': 'Clay',
    'buenos aires': 'Clay', 'rio': 'Clay', 'sao paulo': 'Clay',
    'umag': 'Clay', 'gstaad': 'Clay', 'cordoba': 'Clay',
    'marrakech': 'Clay', 'houston': 'Clay', 'bucharest': 'Clay',
    'estoril': 'Clay', 'geneva': 'Clay', 'parma': 'Clay',
    'cagliari': 'Clay', 'belgrade': 'Clay', 'sardegna': 'Clay',
    'stuttgart': 'Clay',
}


def _detect_surface(match_str: str, prediction: dict) -> str:
    surf = prediction.get("surface", "")
    if surf and surf != "?":
        return surf
    surf = prediction.get("forensics", {}).get("surface", "")
    if surf and surf != "?":
        return surf
    search = f"{match_str} {prediction.get('sport_key', '')} {prediction.get('sport_title', '')}".lower()
    for kw, s in _SURFACE_KEYWORDS.items():
        if kw in search:
            return s
    return "Hard"


_SURF_STYLE = {
    "Hard":  ("[bold #42A5F5]H[/]", "#42A5F5"),
    "Clay":  ("[bold #FF7043]C[/]", "#FF7043"),
    "Grass": ("[bold #66BB6A]G[/]", "#66BB6A"),
}

SORT_OPTIONS = [
    ("Time", "time"),
    ("Edge (High-Low)", "edge_desc"),
    ("Edge (Low-High)", "edge_asc"),
    ("Prob (High-Low)", "prob_desc"),
    ("Kelly (High-Low)", "kelly_desc"),
    ("Odds P1 (Low-High)", "odds_asc"),
]
SURFACE_OPTIONS = [
    ("All Surfaces", "all"),
    ("Hard", "Hard"),
    ("Clay", "Clay"),
    ("Grass", "Grass"),
]


def _load_model_metrics() -> dict:
    """Load model metrics from training output."""
    try:
        with open(METRICS_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _compute_kelly_stake(prob: float, odds: float, bankroll: float,
                         kelly_mult: float, max_stake: float = 500.0) -> float:
    """Compute real Kelly stake: f* = (bp - q) / b, then scale by kelly_mult and bankroll."""
    f = calc_kelly(prob, odds)
    if f <= 0:
        return 0.0
    stake = f * kelly_mult * bankroll
    return min(stake, max_stake, bankroll * 0.05)


# ==================================================================
# MAIN APP
# ==================================================================

class BloombergTUI(App):
    """Tennis Pro Terminal v5.0"""

    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("s", "scan_markets", "Scan", show=True),
        Binding("c", "clear_log", "Clear Log", show=True),
        Binding("r", "refresh_data", "Refresh", show=True),
        Binding("space", "voice_talk", "Voice", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="global-ticker")
        yield Static("", id="summary-bar")

        with TabbedContent(id="tabs"):
            # ── TAB 1: MARKETS ─────────────────────────────
            with TabPane("Markets", id="tab-markets"):
                with Horizontal(id="filter-bar"):
                    yield Select(
                        STRATEGY_OPTIONS,
                        value="balanced",
                        id="strategy-select",
                        allow_blank=False,
                    )
                    yield Select(SORT_OPTIONS, value="time", id="sort-select", allow_blank=False)
                    yield Select(SURFACE_OPTIONS, value="all", id="surface-select", allow_blank=False)
                    yield Input(placeholder="Min edge % (override)", id="edge-input", type="number")
                yield ProgressBar(id="scan-progress", total=100, show_eta=False)
                yield DataTable(id="match-table")

            # ── TAB 2: FORENSICS ───────────────────────────
            with TabPane("Forensics", id="tab-forensics"):
                with VerticalScroll(id="forensics-scroll"):
                    yield Static(
                        "\n\n[dim]Select a match from the Markets tab to view forensics[/dim]",
                        id="forensics-display",
                    )

            # ── TAB 3: AGENT ───────────────────────────────
            with TabPane("Agent", id="tab-agent"):
                yield Static("", id="thinking-indicator")
                yield RichLog(id="agent-log", highlight=True, markup=True)
                with Horizontal(id="input-bar"):
                    yield Input(
                        placeholder="> Type command or press Space to Talk...",
                        id="command-input",
                    )
                    yield Button("TALK", id="voice-btn", variant="primary")

            # ── TAB 4: DASHBOARD ───────────────────────────
            with TabPane("Dashboard", id="tab-dashboard"):
                with VerticalScroll(id="dashboard-scroll"):
                    yield Static(
                        "\n\n[dim]Dashboard loads after first scan or bet.[/dim]",
                        id="dashboard-display",
                    )

        yield Footer()

    # ==============================================================
    # Lifecycle
    # ==============================================================

    def on_mount(self) -> None:
        self.agent_llm = AgentLLM()
        self.audio = AudioEngine()
        self.audio.play_music()
        self.audio.play_sfx("startup")

        # BetAnalytix database
        self.db = BetAnalytix()

        # Betting config
        self._load_betting_config()

        # State
        self.all_predictions = []
        self.current_predictions = {}

        # TTS
        self._tts_on = self.audio.tts_auto
        self._last_agent_response = ""

        # Typing effect
        self._typing_buffer = ""
        self._typing_pos = 0
        self._typing_timer = None

        # Thinking dots
        self._thinking_timer = None
        self._thinking_dots = 0

        # Scanning pulse
        self._scan_pulse_timer = None
        self._scan_pulse_on = False

        # Active strategy
        self._strategy = "balanced"

        # ── Setup Markets table ──
        table = self.query_one("#match-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns(
            "MATCH", "SURF", "ODDS 1/2", "ML PROB", "NEWS",
            "EDGE", "SPREAD (ML/Mkt)", "TOTALS (ML/Mkt)", "KELLY",
        )

        self.query_one("#scan-progress").display = False
        self.query_one("#thinking-indicator").display = False

        # Ticker & summary
        self._update_ticker()
        self._update_summary_bar()

        self.log_msg("PRO Terminal v5.0 initialized.", "system")
        self.log_msg("Press [bold]s[/bold] to scan live markets.", "system")
        self.log_msg("[dim]/tts on|off | /speak | /stats | /bankroll[/dim]", "system")

        if os.path.exists(PRED_PATH):
            self._load_predictions()
            self._apply_filters()

    def _load_betting_config(self):
        """Load betting config from config.yaml."""
        try:
            import yaml
            with open(os.path.join(PROJECT_ROOT, "config", "config.yaml")) as f:
                cfg = yaml.safe_load(f)
            bet_cfg = cfg.get("betting", {})
            self._initial_bankroll = bet_cfg.get("initial_bankroll", 1000)
            self._max_stake = bet_cfg.get("max_stake", 500)
            self._config_kelly_mult = bet_cfg.get("kelly_fraction", 0.25)
        except Exception:
            self._initial_bankroll = 1000
            self._max_stake = 500
            self._config_kelly_mult = 0.25

    # ==============================================================
    # Logging
    # ==============================================================

    def log_msg(self, message: str, style: str = "") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        log = self.query_one("#agent-log", RichLog)
        colors = {
            "system": "#FFD700", "agent": "#00FF00",
            "error": "bold red", "user": "bold white",
        }
        c = colors.get(style, "dim")
        prefix = {
            "agent": "Sandro: ", "error": "ERROR: ",
            "user": "> ", "system": "",
        }.get(style, "")
        log.write(Text.from_markup(f"[{c}][{ts}] {prefix}[/]{message}"))

    # ==============================================================
    # Ticker — real metrics from training
    # ==============================================================

    def _update_ticker(self) -> None:
        metrics = _load_model_metrics()
        if metrics:
            best = metrics.get("best_model", "XGBoost")
            acc = metrics.get("best_accuracy", 0) * 100
            ece = metrics.get("best_ece", 0)
            cal = "CALIBRATED" if ece < 0.03 else "UNCALIBRATED"
            bankroll = self.db.get_bankroll()
            strategy = STRATEGY_PRESETS.get(self._strategy, {}).get("label", "Balanced")
            self.query_one("#global-ticker", Static).update(
                f" [SYSTEM ONLINE] | MODEL: {best} {acc:.1f}% ACC (ECE {ece:.4f} {cal}) "
                f"| BANKROLL: EUR {bankroll:,.0f} | STRATEGY: {strategy} "
            )
        else:
            bankroll = self.db.get_bankroll()
            self.query_one("#global-ticker", Static).update(
                f" [SYSTEM ONLINE] | MODEL: XGBoost | BANKROLL: EUR {bankroll:,.0f} "
                f"| Press S to scan "
            )

    def _update_summary_bar(self) -> None:
        bankroll = self.db.get_bankroll()
        today_pnl = self.db.get_today_pnl()
        pending = len(self.db.get_pending_bets())
        strategy = STRATEGY_PRESETS.get(self._strategy, {}).get("label", "Balanced")
        total_matches = len(self.all_predictions)
        value_count = sum(
            1 for p in self.all_predictions
            if p.get("edge", 0) >= STRATEGY_PRESETS.get(self._strategy, {}).get("min_edge", 0.05)
            and not p.get("low_confidence")
        )

        pnl_color = "#00FF00" if today_pnl >= 0 else "#FF4444"
        now = datetime.now().strftime("%H:%M")

        self.query_one("#summary-bar", Static).update(
            f" {strategy} | {total_matches} matches | {value_count} value bets | "
            f"Bankroll: EUR {bankroll:,.0f} | "
            f"Today P&L: [{pnl_color}]EUR {today_pnl:+,.0f}[/] | "
            f"Pending: {pending} | {now} "
        )

    # ==============================================================
    # Thinking indicator (animated dots)
    # ==============================================================

    def _start_thinking(self) -> None:
        indicator = self.query_one("#thinking-indicator", Static)
        indicator.display = True
        self._thinking_dots = 0
        self._update_thinking_dots()
        self._thinking_timer = self.set_interval(0.4, self._update_thinking_dots)

    def _update_thinking_dots(self) -> None:
        self._thinking_dots = (self._thinking_dots % 3) + 1
        dots = "." * self._thinking_dots + " " * (3 - self._thinking_dots)
        indicator = self.query_one("#thinking-indicator", Static)
        indicator.update(f"[bold #FFD700]  Sandro is thinking{dots}[/]")

    def _stop_thinking(self) -> None:
        if self._thinking_timer:
            self._thinking_timer.stop()
            self._thinking_timer = None
        indicator = self.query_one("#thinking-indicator", Static)
        indicator.display = False

    # ==============================================================
    # Typing effect
    # ==============================================================

    def _start_typing_effect(self, text: str) -> None:
        self._typing_buffer = text
        self._typing_pos = 0
        indicator = self.query_one("#thinking-indicator", Static)
        indicator.display = True
        indicator.update("")
        self._typing_timer = self.set_interval(0.015, self._typing_tick)

    def _typing_tick(self) -> None:
        if self._typing_pos >= len(self._typing_buffer):
            if self._typing_timer:
                self._typing_timer.stop()
                self._typing_timer = None
            indicator = self.query_one("#thinking-indicator", Static)
            indicator.display = False
            self.log_msg(self._typing_buffer, "agent")
            return

        chunk_size = 6
        self._typing_pos = min(self._typing_pos + chunk_size, len(self._typing_buffer))
        partial = self._typing_buffer[:self._typing_pos]
        indicator = self.query_one("#thinking-indicator", Static)
        indicator.update(f"[#00FF00]Sandro: {partial}[/]")

    # ==============================================================
    # Scanning pulse
    # ==============================================================

    def _start_scan_pulse(self) -> None:
        self._scan_pulse_on = True
        self._scan_pulse_timer = self.set_interval(0.6, self._pulse_tick)

    def _pulse_tick(self) -> None:
        ticker = self.query_one("#global-ticker", Static)
        self._scan_pulse_on = not self._scan_pulse_on
        if self._scan_pulse_on:
            ticker.add_class("scanning")
        else:
            ticker.remove_class("scanning")

    def _stop_scan_pulse(self) -> None:
        if self._scan_pulse_timer:
            self._scan_pulse_timer.stop()
            self._scan_pulse_timer = None
        ticker = self.query_one("#global-ticker", Static)
        ticker.remove_class("scanning")

    # ==============================================================
    # Actions
    # ==============================================================

    def action_clear_log(self) -> None:
        self.query_one("#agent-log", RichLog).clear()

    def action_refresh_data(self) -> None:
        self._load_predictions()
        self._apply_filters()
        self._update_ticker()
        self._update_summary_bar()

    def action_scan_markets(self) -> None:
        self.log_msg("Initiating market scan...", "system")
        self.query_one("#global-ticker", Static).update(
            " [SCANNING] | Fetching live data from Bookmakers... "
        )
        pb = self.query_one("#scan-progress", ProgressBar)
        pb.display = True
        pb.update(progress=0)
        self._start_scan_pulse()
        self.run_background_scan()

    @work(exclusive=True, thread=True)
    def run_background_scan(self):
        try:
            env = {**os.environ, "PYTHONUTF8": "1"}
            run_opts = dict(check=True, cwd=PROJECT_ROOT, env=env)
            subprocess.run(["python", "-X", "utf8", "-m", "src.data.scraper"], **run_opts)
            self.call_from_thread(self._update_progress, 45)
            subprocess.run(["python", "-X", "utf8", "-m", "src.live.inference"], **run_opts)
            self.call_from_thread(self._update_progress, 95)
            self.call_from_thread(self.on_scan_complete, True)
        except Exception as e:
            self.call_from_thread(self.on_scan_complete, False, str(e))

    def _update_progress(self, value: int) -> None:
        self.query_one("#scan-progress", ProgressBar).update(progress=value)

    def on_scan_complete(self, success: bool, error: str = "") -> None:
        self._stop_scan_pulse()
        pb = self.query_one("#scan-progress", ProgressBar)
        pb.update(progress=100)
        pb.display = False
        if success:
            self.audio.play_sfx("scan_complete")
            self.log_msg("Market scan completed.", "system")
            self._load_predictions()
            self._apply_filters()

            # Auto-log decisions to BetAnalytix
            try:
                scan_id = self.db.log_decisions(self.all_predictions)
                n = len(self.all_predictions)
                self.log_msg(f"Logged {n} decisions to BetAnalytix [{scan_id}].", "system")
            except Exception as e:
                self.log_msg(f"BetAnalytix log error: {e}", "error")

            self._update_ticker()
            self._update_summary_bar()
        else:
            self.audio.play_sfx("error")
            self.log_msg(f"Scan failed: {error}", "error")
            self.query_one("#global-ticker", Static).update(
                " [SYSTEM ONLINE] | ERROR SCANNING MARKETS "
            )

    # ==============================================================
    # Data loading & filtering
    # ==============================================================

    def _load_predictions(self) -> None:
        try:
            if not os.path.exists(PRED_PATH):
                self.log_msg("Predictions file not found.", "error")
                return
            with open(PRED_PATH, "r") as f:
                self.all_predictions = json.load(f)
            for p in self.all_predictions:
                p["_surface"] = _detect_surface(p.get("match", ""), p)
                # Pre-compute Kelly for each prediction
                side = p.get("value_side", 1)
                prob = p["prob_1"] if side == 1 else p["prob_2"]
                odds = p["odds_1"] if side == 1 else p["odds_2"]
                p["_kelly_raw"] = calc_kelly(prob, odds)
            self.current_predictions = {p["match"]: p for p in self.all_predictions}
        except Exception as e:
            self.log_msg(f"Failed to load predictions: {e}", "error")

    def _get_strategy(self) -> dict:
        """Get current strategy config."""
        return STRATEGY_PRESETS.get(self._strategy, STRATEGY_PRESETS["balanced"])

    def _apply_filters(self) -> None:
        preds = list(self.all_predictions)
        if not preds:
            self._update_summary_bar()
            return

        strategy = self._get_strategy()

        # Strategy filter -- apply unless custom
        if self._strategy != "custom":
            preds = [
                p for p in preds
                if p.get("odds_1", 0) >= strategy["min_odds"]
                and p.get("odds_1", 0) <= strategy["max_odds"]
            ]

        # Surface filter
        try:
            surface_val = self.query_one("#surface-select", Select).value
        except Exception:
            surface_val = "all"
        if surface_val and surface_val != "all":
            preds = [p for p in preds if p.get("_surface", "").lower() == surface_val.lower()]

        # Min edge filter -- from strategy or manual override
        try:
            edge_text = self.query_one("#edge-input", Input).value.strip()
            if edge_text:
                min_edge = float(edge_text) / 100.0
            else:
                min_edge = strategy["min_edge"] if self._strategy != "custom" else 0.0
        except (ValueError, Exception):
            min_edge = strategy["min_edge"] if self._strategy != "custom" else 0.0

        if min_edge > 0:
            preds = [p for p in preds if p.get("edge", 0) >= min_edge]

        # Sort -- default chronological
        try:
            sort_val = self.query_one("#sort-select", Select).value
        except Exception:
            sort_val = "time"

        def _time_key(p):
            ct = p.get("commence_time", "")
            if ct:
                return ct
            m = p.get("match", "")
            try:
                return "9999-" + m.split("]")[0].strip("[")
            except Exception:
                return "9999-99:99"

        sort_map = {
            "time":       (_time_key, False),
            "edge_desc":  (lambda p: p.get("edge", 0), True),
            "edge_asc":   (lambda p: p.get("edge", 0), False),
            "prob_desc":  (lambda p: max(p.get("prob_1", 0), p.get("prob_2", 0)), True),
            "kelly_desc": (lambda p: p.get("_kelly_raw", 0), True),
            "odds_asc":   (lambda p: p.get("odds_1", 0), False),
        }
        key_fn, rev = sort_map.get(sort_val, sort_map["time"])
        preds.sort(key=key_fn, reverse=rev)

        self._populate_table(preds)
        self._update_summary_bar()

    def _populate_table(self, preds: list) -> None:
        table = self.query_one("#match-table", DataTable)
        table.clear()

        strategy = self._get_strategy()
        bankroll = self.db.get_bankroll()
        kelly_mult = strategy["kelly_mult"]

        for p in preds:
            match_name = p["match"]
            o1, o2 = p["odds_1"], p["odds_2"]
            prob1, prob2 = p["prob_1"], p["prob_2"]
            raw_p1 = p.get("raw_prob_1", prob1)
            raw_p2 = p.get("raw_prob_2", prob2)
            edge = p.get("edge", 0)
            side = p.get("value_side", 1)
            low_conf = p.get("low_confidence", False)
            surface = p.get("_surface", "Hard")

            # Surface badge
            surf_markup, _ = _SURF_STYLE.get(surface, ("[dim]?[/]", "#888888"))

            # ML PROB column
            ml_prob_str = f"{raw_p1:.0%} / {raw_p2:.0%}"

            # NEWS column -- source count + adjustment indicator
            adj = p.get("news_adjustment")
            if adj and adj.get("applied"):
                eff = adj.get("effective", 0)
                sources = adj.get("sources", [])
                n_src = len(sources) if isinstance(sources, list) else 0
                if abs(eff) >= 0.05:
                    news_markup = f"[bold red]{eff*100:+.0f}pp ({n_src}src)[/]"
                else:
                    news_markup = f"[bold yellow]{eff*100:+.0f}pp ({n_src}src)[/]"
            elif adj and adj.get("sources"):
                sources = adj.get("sources", [])
                n_src = len(sources) if isinstance(sources, list) else 0
                news_markup = f"[dim]0pp ({n_src}src)[/]"
            else:
                news_markup = "[dim]--[/]"

            # Edge
            edge_str = f"P{side} {edge*100:+.1f}%"
            if low_conf:
                edge_markup = f"[dim]{edge_str} ![/]"
            elif edge > 0.10:
                edge_markup = f"[bold #00FF00]{edge_str}[/]"
            elif edge > 0.05:
                edge_markup = f"[bold green]{edge_str}[/]"
            elif edge > 0.03:
                edge_markup = f"[green]{edge_str}[/]"
            elif edge > 0:
                edge_markup = f"[yellow]{edge_str}[/]"
            else:
                edge_markup = f"[red]{edge_str}[/]"

            # Spread
            exp_diff = p.get("exp_game_diff", 0)
            mkt_spread = p.get("market_spread", 0)
            f_data = p.get("forensics", {})
            spread_edge = f_data.get("spread_edge")
            if mkt_spread:
                sp = f"{exp_diff:+.1f} / {mkt_spread:+.1f}"
                sp_markup = f"[bold yellow]{sp}[/]" if spread_edge else sp
            else:
                sp_markup = f"[dim]{exp_diff:+.1f} / --[/]"

            # Totals
            exp_total = p.get("exp_total_games", 0)
            mkt_total = p.get("market_total", 0)
            totals_edge = f_data.get("totals_edge")
            if mkt_total:
                tt = f"{exp_total:.1f} / {mkt_total:.1f}"
                tt_markup = f"[bold yellow]{tt}[/]" if totals_edge else tt
            else:
                tt_markup = f"[dim]{exp_total:.1f} / --[/]"

            # Kelly -- REAL Kelly Criterion
            val_prob = prob1 if side == 1 else prob2
            val_odds = o1 if side == 1 else o2
            stake = _compute_kelly_stake(val_prob, val_odds, bankroll, kelly_mult, self._max_stake)
            kelly_pct = p.get("_kelly_raw", 0) * 100

            if stake > 0 and not low_conf:
                if kelly_pct > 10:
                    kelly_markup = f"[bold #00FF00]EUR {stake:.0f} ({kelly_pct:.0f}%)[/]"
                elif kelly_pct > 5:
                    kelly_markup = f"[bold cyan]EUR {stake:.0f} ({kelly_pct:.0f}%)[/]"
                else:
                    kelly_markup = f"[cyan]EUR {stake:.0f} ({kelly_pct:.0f}%)[/]"
            else:
                kelly_markup = "[dim]--[/]"

            # Match name
            name_markup = f"[dim]{match_name}[/]" if low_conf else match_name

            table.add_row(
                Text.from_markup(name_markup) if low_conf else match_name,
                Text.from_markup(surf_markup),
                f"{o1:.2f} / {o2:.2f}",
                ml_prob_str,
                Text.from_markup(news_markup),
                Text.from_markup(edge_markup),
                Text.from_markup(sp_markup),
                Text.from_markup(tt_markup),
                Text.from_markup(kelly_markup),
            )

        self.log_msg(f"Displayed {len(preds)} predictions ({self._get_strategy()['label']}).", "system")

    # ==============================================================
    # Filter handlers
    # ==============================================================

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "strategy-select":
            self._strategy = event.value
            self._apply_filters()
            self._update_ticker()
            self._update_summary_bar()
        elif event.select.id in ("sort-select", "surface-select"):
            self._apply_filters()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "edge-input":
            self._apply_filters()

    # ==============================================================
    # Forensics tab
    # ==============================================================

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "match-table":
            return

        table = self.query_one("#match-table", DataTable)
        try:
            row_data = table.get_row(event.row_key)
        except Exception:
            return
        match_name = row_data[0]
        if isinstance(match_name, Text):
            match_name = match_name.plain

        if not self.current_predictions or match_name not in self.current_predictions:
            return

        p = self.current_predictions[match_name]
        self._render_forensics(p)
        self.query_one("#tabs", TabbedContent).active = "tab-forensics"

    def _render_forensics(self, p: dict) -> None:
        f = p.get("forensics", {})
        low_conf = p.get("low_confidence", False)
        strategy = self._get_strategy()
        bankroll = self.db.get_bankroll()

        # Confidence
        if low_conf:
            conf = "[bold red]LOW -- missing player data[/]"
        elif abs(p["prob_1"] - 0.5) > 0.15:
            conf = "[bold green]HIGH[/]"
        else:
            conf = "[bold yellow]MEDIUM[/]"

        # Player names
        match_str = p.get("match", "")
        p1_name = f.get("p1_name", "")
        p2_name = f.get("p2_name", "")
        if not p1_name or not p2_name:
            try:
                names_part = match_str.split("] ")[1]
                p1_name, p2_name = names_part.split(" vs ")
            except Exception:
                p1_name, p2_name = "P1", "P2"

        # Surface & tourney
        surface = p.get("_surface", _detect_surface(match_str, p))
        _, surf_color = _SURF_STYLE.get(surface, ("?", "#888888"))
        tourney = f.get("tourney_name", "")
        level = f.get("tourney_level", "")
        level_map = {"G": "Grand Slam", "M": "Masters 1000", "A": "ATP 250/500",
                     "C": "Challenger", "S": "Davis Cup", "F": "Finals"}
        level_label = level_map.get(level, "ATP")
        if not tourney:
            tourney = level_label

        # Rankings
        p1_rank = f.get("p1_rank", "?")
        p2_rank = f.get("p2_rank", "?")

        # ELO bars
        def elo_bar(val, width=15):
            clamped = min(2400, max(1400, val))
            filled = int((clamped - 1400) / 1000 * width)
            return f"[green]{'█' * filled}[/][dim]{'░' * (width - filled)}[/] {val}"

        # Spread/totals odds
        if "spread_odds_1" in f:
            sp_odds = f"{f['spread_odds_1']:.2f} / {f['spread_odds_2']:.2f}"
        elif "spread_odds" in f:
            sp_odds = f["spread_odds"]
        else:
            sp_odds = "-- / --"

        if "total_over_odds" in f:
            tt_odds = f"{f['total_over_odds']:.2f} / {f['total_under_odds']:.2f}"
        elif "totals_odds" in f:
            tt_odds = f["totals_odds"]
        else:
            tt_odds = "-- / --"

        # Edge tags
        spread_edge = f.get("spread_edge")
        totals_edge = f.get("totals_edge")
        if spread_edge is None and f.get("market_spread") and f.get("exp_game_diff"):
            diff = f["exp_game_diff"] - f["market_spread"]
            if diff > 1.0:
                spread_edge = "P1"
            elif diff < -1.0:
                spread_edge = "P2"
        if totals_edge is None and f.get("market_total") and f.get("exp_total_games"):
            if f["exp_total_games"] > f["market_total"] + 0.5:
                totals_edge = "OVER"
            elif f["exp_total_games"] < f["market_total"] - 0.5:
                totals_edge = "UNDER"

        sp_tag = f"  [bold green]>>> VALORE {spread_edge}[/]" if spread_edge else ""
        tt_tag = f"  [bold green]>>> VALORE {totals_edge}[/]" if totals_edge else ""

        # Edge bar
        edge_pct = p["edge"] * 100
        edge_blocks = min(20, max(0, int(edge_pct / 2)))
        if edge_pct > 10:
            edge_bar = f"[bold #00FF00]{'█' * edge_blocks}[/][dim]{'░' * (20 - edge_blocks)}[/] [bold #00FF00]{edge_pct:+.1f}%[/]"
        elif edge_pct > 3:
            edge_bar = f"[bold green]{'█' * edge_blocks}[/][dim]{'░' * (20 - edge_blocks)}[/] [bold green]{edge_pct:+.1f}%[/]"
        elif edge_pct > 0:
            edge_bar = f"[yellow]{'█' * edge_blocks}[/][dim]{'░' * (20 - edge_blocks)}[/] [yellow]{edge_pct:+.1f}%[/]"
        else:
            edge_bar = f"[red]{'█' * max(1, edge_blocks)}[/][dim]{'░' * (20 - max(1, edge_blocks))}[/] [red]{edge_pct:+.1f}%[/]"

        # Kelly -- REAL
        side = p.get("value_side", 1)
        val_prob = p["prob_1"] if side == 1 else p["prob_2"]
        val_odds = p["odds_1"] if side == 1 else p["odds_2"]
        kelly_pct = calc_kelly(val_prob, val_odds) * 100
        stake = _compute_kelly_stake(val_prob, val_odds, bankroll, strategy["kelly_mult"], self._max_stake)
        side_name = p1_name if side == 1 else p2_name

        sep = "[bold cyan]" + "─" * 56 + "[/]"
        sep2 = "[dim]" + "─" * 56 + "[/]"

        # ── NEWS ADJUSTMENT SECTION ──
        adj = p.get("news_adjustment")
        raw_p1 = p.get("raw_prob_1", p["prob_1"])
        raw_p2 = p.get("raw_prob_2", p["prob_2"])

        if adj and adj.get("applied"):
            eff = adj.get("effective", 0)
            conf_adj = adj.get("confidence", 0)
            reason = adj.get("reason", "--")
            sources = adj.get("sources", [])
            src_list = ""
            if isinstance(sources, list) and sources:
                src_items = ", ".join(str(s) for s in sources[:5])
                src_list = f"\n  [dim]Sources[/]         {src_items}"
            adj_color = "bold red" if abs(eff) >= 0.05 else "bold yellow"
            news_section = f"""\n{sep2}
[bold]  NEWS ADJUSTMENT (Agentic Research)[/]
{sep2}

  [dim]Prob originale[/]   {raw_p1:.1%} / {raw_p2:.1%}
  [dim]Adjustment[/]       [{adj_color}]{eff*100:+.1f}pp[/] (confidence {conf_adj:.0%})
  [dim]Prob adjusted[/]    [bold]{p['prob_1']:.1%} / {p['prob_2']:.1%}[/]
  [dim]Motivo[/]           [{adj_color}]{reason}[/]{src_list}
"""
        elif adj and not adj.get("applied"):
            news_section = f"""\n{sep2}
[bold]  NEWS ADJUSTMENT[/]
{sep2}

  [dim]Nessun aggiustamento applicato (adjustment troppo piccolo)[/]
"""
        else:
            news_section = f"""\n{sep2}
[bold]  NEWS ADJUSTMENT[/]
{sep2}

  [dim]Nessuna news rilevante trovata[/]
"""

        ticket = f"""{sep}
[bold cyan]  FORENSIC ANALYSIS v5.0[/]
{sep}

[bold]{match_str}[/]
[{surf_color}]{surface}[/] | {tourney} ({level_label})

{sep2}
[bold]  PLAYER COMPARISON[/]
{sep2}

  [bold cyan]{p1_name:<26}[/] [dim]vs[/]  [bold cyan]{p2_name}[/]

  [dim]Rank[/]        #{p1_rank:<22} [dim]Rank[/]        #{p2_rank}
  [dim]ELO[/]         {elo_bar(f.get('p1_elo', 1500))}
  [dim]            [/]{elo_bar(f.get('p2_elo', 1500))}
  [dim]Surf ELO[/]    {elo_bar(f.get('p1_surface_elo', 1500))}
  [dim]            [/]{elo_bar(f.get('p2_surface_elo', 1500))}
  [dim]Form L10[/]    {f.get('p1_form', 'N/A'):<24} [dim]Form L10[/]    {f.get('p2_form', 'N/A')}
  [dim]H2H[/]         {f.get('p1_h2h', 0)} - {f.get('p2_h2h', 0)}

{sep2}
[bold]  SPECIAL MARKETS[/]
{sep2}

  [dim]Spread[/]   ML [bold yellow]{f.get('exp_game_diff', 0):+.1f}[/]  vs  Mkt [bold cyan]{f.get('market_spread', 0):+.1f}[/]  ({sp_odds}){sp_tag}
  [dim]Totals[/]   ML [bold yellow]{f.get('exp_total_games', 0):.1f}[/]  vs  Mkt [bold cyan]{f.get('market_total', 0):.1f}[/]  ({tt_odds}){tt_tag}

{sep2}
[bold]  BETTING TICKET[/]
{sep2}

  [dim]Strategy[/]     [bold]{strategy['label']}[/] (Kelly {strategy['kelly_mult']*100:.0f}%)
  [dim]Value Side[/]   [bold]{side_name}[/] (Player {side})
  [dim]Odds[/]         {p['odds_1']:.2f} / {p['odds_2']:.2f}
  [dim]ML Prob[/]      {p['prob_1']:.1%} / {p['prob_2']:.1%}
  [dim]Edge[/]         {edge_bar}
  [dim]Kelly f*[/]     {kelly_pct:.1f}% of bankroll
  [dim]Stake[/]        [bold cyan]EUR {stake:.0f}[/] (bankroll EUR {bankroll:,.0f})
  [dim]Confidence[/]   {conf}
{news_section}"""
        self.query_one("#forensics-display", Static).update(ticket)

    # ==============================================================
    # Dashboard Tab -- performance analytics
    # ==============================================================

    def _render_dashboard(self) -> None:
        stats = self.db.get_stats()
        bankroll = stats["bankroll"]
        sep = "[bold cyan]" + "─" * 60 + "[/]"
        sep2 = "[dim]" + "─" * 60 + "[/]"

        win_rate = stats["win_rate"] * 100
        roi = stats["roi"] * 100

        streak = stats["current_streak"]
        if streak > 0:
            streak_str = f"[bold green]W{streak}[/]"
        elif streak < 0:
            streak_str = f"[bold red]L{abs(streak)}[/]"
        else:
            streak_str = "[dim]--[/]"

        best = stats.get("best_bet")
        worst = stats.get("worst_bet")
        best_str = f"{best['match'][:35]} [green]EUR {best['profit']:+,.0f}[/]" if best else "--"
        worst_str = f"{worst['match'][:35]} [red]EUR {worst['profit']:+,.0f}[/]" if worst else "--"

        # Surface section
        surf_lines = ""
        for surf, s in sorted(stats.get("by_surface", {}).items()):
            wr = s["win_rate"] * 100
            sr = s["roi"] * 100
            _, color = _SURF_STYLE.get(surf, ("?", "#888888"))
            surf_lines += (
                f"  [{color}]{surf:<8}[/]  {s['bets']:>4} bets  |  "
                f"WR {wr:5.1f}%  |  ROI {sr:+6.1f}%  |  P&L EUR {s['profit']:+,.0f}\n"
            )
        if not surf_lines:
            surf_lines = "  [dim]No data yet[/]\n"

        # Edge range section
        edge_lines = ""
        for bucket, e in stats.get("by_edge_range", {}).items():
            if e["bets"] > 0:
                wr = e["win_rate"] * 100
                er = e["roi"] * 100
                edge_lines += (
                    f"  {bucket:<8}  {e['bets']:>4} bets  |  "
                    f"WR {wr:5.1f}%  |  ROI {er:+6.1f}%  |  P&L EUR {e['profit']:+,.0f}\n"
                )
        if not edge_lines:
            edge_lines = "  [dim]No data yet[/]\n"

        # Monthly section
        monthly_lines = ""
        for month, m in stats.get("monthly", {}).items():
            if m["bets"] > 0:
                wr = m["won"] / m["bets"] * 100 if m["bets"] > 0 else 0
                mr = m["profit"] / m["staked"] * 100 if m["staked"] > 0 else 0
                pnl_color = "green" if m["profit"] >= 0 else "red"
                monthly_lines += (
                    f"  {month}  {m['bets']:>4} bets  |  "
                    f"WR {wr:5.1f}%  |  ROI {mr:+6.1f}%  |  "
                    f"[{pnl_color}]P&L EUR {m['profit']:+,.0f}[/]\n"
                )
        if not monthly_lines:
            monthly_lines = "  [dim]No data yet[/]\n"

        scan_count = self.db.get_scan_count()
        decision_count = self.db.get_decision_count()

        dashboard = f"""{sep}
[bold cyan]  BETANALYTIX DASHBOARD v5.0[/]
{sep}

{sep2}
[bold]  OVERALL PERFORMANCE[/]
{sep2}

  [dim]Bankroll[/]       [bold]EUR {bankroll:,.0f}[/]
  [dim]Total Bets[/]     {stats['total_bets']}  ({stats['won']}W / {stats['lost']}L / {stats['pending']} pending)
  [dim]Win Rate[/]       [bold]{win_rate:.1f}%[/]
  [dim]ROI[/]            [bold]{roi:+.1f}%[/]
  [dim]Total Staked[/]   EUR {stats['total_staked']:,.0f}
  [dim]Total Profit[/]   [bold {'green' if stats['total_profit'] >= 0 else 'red'}]EUR {stats['total_profit']:+,.0f}[/]
  [dim]Max Drawdown[/]   [bold red]EUR {stats['max_drawdown']:,.0f}[/]
  [dim]Current Streak[/] {streak_str}
  [dim]Best Bet[/]       {best_str}
  [dim]Worst Bet[/]      {worst_str}

{sep2}
[bold]  BY SURFACE[/]
{sep2}

{surf_lines}
{sep2}
[bold]  BY EDGE RANGE[/]
{sep2}

{edge_lines}
{sep2}
[bold]  MONTHLY BREAKDOWN[/]
{sep2}

{monthly_lines}
{sep2}
[bold]  MODEL ACTIVITY[/]
{sep2}

  [dim]Total Scans[/]      {scan_count}
  [dim]Total Decisions[/]   {decision_count}
  [dim]Decisions/Scan[/]    {decision_count / max(1, scan_count):.1f}
"""
        self.query_one("#dashboard-display", Static).update(dashboard)

    # ==============================================================
    # Button handlers
    # ==============================================================

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "voice-btn":
            self.action_voice_talk()

    # ==============================================================
    # Tab switch handler -- auto refresh dashboard
    # ==============================================================

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        tab_id = event.pane.id if hasattr(event, 'pane') else ""
        if tab_id == "tab-dashboard":
            self._render_dashboard()

    # ==============================================================
    # Agent console
    # ==============================================================

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "command-input":
            return
        cmd = event.value.strip()
        if not cmd:
            return

        self.log_msg(cmd, "user")
        cmd_lower = cmd.lower().strip()

        # Built-in commands
        if cmd_lower in ("scan", "s", "scan markets"):
            self.action_scan_markets()
        elif cmd_lower in ("clear", "c"):
            self.action_clear_log()
        elif cmd_lower in ("reset", "reset agent", "nuova chat"):
            self.agent_llm.clear_history()
            self.log_msg("Conversation history cleared.", "system")
        elif cmd_lower == "/tts on":
            self._tts_on = True
            self.audio.tts_enabled = True
            self.log_msg("TTS enabled. Agent responses will be spoken.", "system")
        elif cmd_lower == "/tts off":
            self._tts_on = False
            self.log_msg("TTS disabled.", "system")
        elif cmd_lower == "/speak":
            if self._last_agent_response:
                self.audio.speak(self._last_agent_response)
                self.log_msg("[dim]Speaking last response...[/dim]", "system")
            else:
                self.log_msg("[dim]No response to speak yet.[/dim]", "system")
        elif cmd_lower == "/stats":
            self._render_dashboard()
            self.query_one("#tabs", TabbedContent).active = "tab-dashboard"
        elif cmd_lower == "/bankroll":
            bankroll = self.db.get_bankroll()
            today = self.db.get_today_pnl()
            self.log_msg(f"Bankroll: EUR {bankroll:,.0f} | Today: EUR {today:+,.0f}", "system")
        elif cmd_lower.startswith("/strategy"):
            parts = cmd_lower.split()
            if len(parts) > 1 and parts[1] in STRATEGY_PRESETS:
                self._strategy = parts[1]
                self.query_one("#strategy-select", Select).value = parts[1]
                self._apply_filters()
                self._update_ticker()
                self._update_summary_bar()
                self.log_msg(f"Strategy changed to: {STRATEGY_PRESETS[parts[1]]['label']}", "system")
            else:
                self.log_msg("Usage: /strategy conservative|balanced|aggressive|custom", "system")
        elif "backtest" in cmd_lower:
            self.run_background_backtest()
        else:
            self.run_agent_query(cmd)

        self.query_one("#command-input", Input).value = ""

    @work(exclusive=True, thread=True)
    def run_agent_query(self, query: str):
        self.call_from_thread(self._start_thinking)
        try:
            response = self.agent_llm.ask(query, PRED_PATH)
            # Mutate shared state on the UI thread to avoid torn reads from
            # other event handlers / timers that touch these attrs.
            def _apply():
                self._last_agent_response = response
                self.audio.last_response = response
                self._start_typing_effect(response)
            self.call_from_thread(self._stop_thinking)
            self.call_from_thread(_apply)
            if self._tts_on:
                self.audio.speak(response)
        except Exception as e:
            self.call_from_thread(self._stop_thinking)
            self.call_from_thread(self.log_msg, f"Agent error: {e}", "error")

    @work(exclusive=True, thread=True)
    def run_background_backtest(self):
        self.call_from_thread(self.log_msg, "Running backtest (non-blocking)...", "system")
        pb = self.query_one("#scan-progress", ProgressBar)
        self.call_from_thread(setattr, pb, "display", True)
        try:
            env = {**os.environ, "PYTHONUTF8": "1"}
            subprocess.run(
                ["python", "-X", "utf8", "-m", "src.betting.backtest"],
                check=True, cwd=PROJECT_ROOT, env=env,
            )
            self.call_from_thread(self.log_msg, "Backtest completed.", "system")
        except Exception as e:
            self.call_from_thread(self.log_msg, f"Backtest error: {e}", "error")
        finally:
            self.call_from_thread(setattr, pb, "display", False)

    # ==============================================================
    # Voice
    # ==============================================================

    def action_voice_talk(self) -> None:
        self._run_voice_input()

    @work(exclusive=True, thread=True)
    def _run_voice_input(self):
        self.call_from_thread(self.log_msg, "Listening... speak now.", "system")
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                audio_data = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                self.call_from_thread(self.log_msg, "Processing speech...", "system")
                text = recognizer.recognize_google(audio_data, language="it-IT")
                self.call_from_thread(self.log_msg, f"You said: {text}", "user")
                self.run_agent_query(text)
        except Exception as e:
            self.call_from_thread(self.log_msg, f"Speech error: {e}", "error")


def main():
    app = BloombergTUI()
    app.run()


if __name__ == "__main__":
    main()
