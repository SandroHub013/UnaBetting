"""Frozen entry point for the packaged desktop app (Windows / macOS / Linux).

PyInstaller runs this script. It seeds the per-OS app-data directory from the
bundled slim runtime on first launch (so the user finds everything ready — no raw
data download, no pipeline), then hands off to the normal dashboard entry point.

In a source checkout this is equivalent to ``python -m src.dashboard`` (seeding is
a no-op when DATA_ROOT is the repo root).
"""
import os
import sys
from pathlib import Path

# Make the bundled packages importable both frozen (sys._MEIPASS) and from source.
_here = Path(__file__).resolve()
_root = getattr(sys, "_MEIPASS", None)
_root = Path(_root) if _root else _here.parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def main() -> None:
    from src.runtime_paths import seed_data_root, DATA_ROOT
    seed_data_root()
    # The pipeline runner shells out to the app's own interpreter; in a frozen
    # build sys.executable is the app exe, which would relaunch the GUI. Point
    # child processes at a real python if one is on PATH (best-effort).
    os.environ.setdefault("UNABETTING_DATA_DIR", str(DATA_ROOT))

    from src.dashboard.__main__ import main as dashboard_main
    dashboard_main()


if __name__ == "__main__":
    main()
