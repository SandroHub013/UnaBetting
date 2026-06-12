"""Cross-platform runtime paths for the packaged app (Windows / macOS / Linux).

Two roots, deliberately separate:

- ``BUNDLE_DIR`` — read-only resources shipped *inside* the app. In a PyInstaller
  build this is ``sys._MEIPASS`` (the temporary extraction dir); in a normal source
  checkout it is the repo root. Static assets, the seed copy of models/data and the
  default config live here.
- ``DATA_ROOT`` — the writable, persistent location for the user's data: the
  ``betanalytix.db`` portfolio, downloaded model updates, settings, live caches. In a
  source checkout this is just the repo root (data lives in the repo, as in dev). In a
  packaged build it is the per-OS application-data directory, so it survives app
  updates and is writable even when the app itself sits in a read-only location.

On first launch of a packaged build, ``seed_data_root()`` copies the bundled seed
(models + inference data + default config) into ``DATA_ROOT`` so the user finds
everything ready without downloading the multi-GB raw dataset or running the pipeline.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_NAME = "UnaBetting"

#: True when running from a PyInstaller (or similar) frozen build.
FROZEN = bool(getattr(sys, "frozen", False))


def _bundle_dir() -> Path:
    """Read-only resources shipped with the app."""
    if FROZEN:
        # PyInstaller extracts data files under sys._MEIPASS; onefile and onedir
        # both expose it. Fall back to the executable's dir for onedir layouts.
        meipass = getattr(sys, "_MEIPASS", None)
        return Path(meipass) if meipass else Path(sys.executable).resolve().parent
    # Source checkout: repo root (this file is src/runtime_paths.py -> parents[1]).
    return Path(__file__).resolve().parents[1]


def _user_data_dir() -> Path:
    """Per-OS, per-user writable application-data directory."""
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
        return Path(base) / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    # Linux / other POSIX: respect the XDG base-dir spec.
    base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / APP_NAME


BUNDLE_DIR: Path = _bundle_dir()

#: Writable data root. Repo root in dev; per-OS app-data dir when packaged.
#: Override with UNABETTING_DATA_DIR for portable installs / testing.
_override = os.environ.get("UNABETTING_DATA_DIR")
if _override:
    DATA_ROOT: Path = Path(_override)
elif FROZEN:
    DATA_ROOT = _user_data_dir()
else:
    DATA_ROOT = BUNDLE_DIR


# Subdirectories of the bundled seed that get copied into DATA_ROOT on first run.
# Everything the app needs to run with no pipeline and no raw data download.
_SEED_SUBDIRS = ("models", "data", "config", "reports")


def seed_data_root() -> None:
    """Populate DATA_ROOT from the bundled seed on first launch (packaged builds).

    Copies each seed file only if it is missing in DATA_ROOT, so a user's existing
    data (their betanalytix.db, settings, downloaded model updates) is never
    overwritten by a reinstall or update. No-op in a source checkout.
    """
    if DATA_ROOT == BUNDLE_DIR:
        return  # dev: nothing to seed, data already lives in the repo
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    for sub in _SEED_SUBDIRS:
        src = BUNDLE_DIR / sub
        if not src.is_dir():
            continue
        for srcfile in src.rglob("*"):
            if srcfile.is_dir():
                continue
            rel = srcfile.relative_to(BUNDLE_DIR)
            dst = DATA_ROOT / rel
            if dst.exists():
                continue  # preserve user data — never clobber
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(srcfile, dst)


def app_version() -> str:
    """Current app version, read from the bundled VERSION file (falls back 0.0.0)."""
    for root in (DATA_ROOT, BUNDLE_DIR):
        vf = root / "VERSION"
        if vf.is_file():
            return vf.read_text(encoding="utf-8").strip()
    return "0.0.0"
