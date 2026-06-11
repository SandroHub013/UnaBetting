"""Dashboard constants: paths, network binding, command whitelist, shells."""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

HOST = "127.0.0.1"   # local only, by design — never bind 0.0.0.0
PORT = 8765
APP_NAME = "UnaBetting"
WINDOW_TITLE = "UnaBetting"

DB_PATH = PROJECT_ROOT / "data" / "betanalytix.db"
ODDS_HISTORY = PROJECT_ROOT / "data" / "live" / "odds_history.csv"
SIGNALS_LOG = PROJECT_ROOT / "data" / "live" / "signals_log.csv"
CONFIG_YAML = PROJECT_ROOT / "config" / "config.yaml"
STATIC_DIR = Path(__file__).resolve().parent / "static"

# Pipeline runner: ONLY these commands can be launched from the UI buttons.
# Free-form execution goes through the real terminals, not through this map.
PYTHON = sys.executable
COMMAND_WHITELIST = {
    # full live scan: fetch fresh odds (the-odds-api -> current_odds.csv), then
    # run model+news inference on them. NOTE: consumes paid API credits per run.
    "scan": [PYTHON, "-X", "utf8", "-c",
             "from src.data.scraper import fetch_all_tennis_odds, save_to_csv; "
             "save_to_csv(fetch_all_tennis_odds()); "
             "from src.live.inference import run_inference; run_inference()"],
    "download":  [PYTHON, "-X", "utf8", "-m", "src.data.download"],
    "clean":     [PYTHON, "-X", "utf8", "-m", "src.data.clean"],
    "features":  [PYTHON, "-X", "utf8", "-m", "src.features.build_features"],
    "train":     [PYTHON, "-X", "utf8", "-m", "src.models.train"],
    "backtest":  [PYTHON, "-X", "utf8", "-m", "src.models.backtest"],
    "inference": [PYTHON, "-X", "utf8", "-m", "src.live.inference"],
    "signals":   [PYTHON, "-X", "utf8", "-m", "src.betting.signals"],
}

# Interactive terminals (pywinpty). Key = ?shell= query param.
SHELLS = {
    "powershell": "powershell.exe -NoLogo",
    "wsl": "wsl.exe",
}

# Vibe-coding agents: launched inside a persistent tmux session on WSL
# (tmux new -A reattaches, so closing the tab never kills the agent).
# All verified present in WSL at ~/.local/bin (2026-06-10).
VIBE_AGENTS = {
    "claude": "claude",
    "opencode": "opencode",
    "codex": "codex",
    "hermes": "hermes",
    "agy": "agy",
}
# project path as seen from WSL (terminal cwd -> tmux working dir)
WSL_PROJECT_DIR = "/mnt/g/tennis betting"

# Only bookmakers shown/considered in the app (sharp reference + ADM-legal
# venues). Keep in sync with src.betting.signals.ALLOWED_BOOKS and config.yaml.
ALLOWED_BOOKMAKERS = ["pinnacle", "williamhill", "sport888", "marathonbet",
                      "betfair_ex_eu", "betfair_ex_uk"]

# In-app chat agent: local Ollama. qwen3.5:9b = best local tool-caller on the
# user's RTX 2070 Super (4/4 correct tool calls @26 tok/s, fits 8GB VRAM).
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "qwen3.5:9b")
CHAT_KEEP_ALIVE = "30m"   # keep weights warm while the app is open

# File explorer / editor (IDE panel)
IGNORE_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules",
               ".antigravitycli", "tennis_betting_sota.egg-info"}
TEXT_EXTS = {".py", ".md", ".txt", ".yaml", ".yml", ".json", ".csv", ".js",
             ".css", ".html", ".ps1", ".toml", ".cfg", ".ini", ".bat", ".sh",
             ".log", ".gitignore", ".env", ".example"}
MAX_FILE_BYTES = 1_500_000
LOOPS_LOG_DIR = PROJECT_ROOT / "reports" / "loops"


def auth_token():
    """Optional session token: if DASHBOARD_TOKEN is set, WS connections must
    pass it as ?token=. Read dynamically so tests can monkeypatch the env."""
    return os.environ.get("DASHBOARD_TOKEN", "")
