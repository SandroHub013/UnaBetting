"""Entrypoint: python -m src.dashboard

Desktop app: starts the local FastAPI server on a background thread and opens
a NATIVE window (pywebview / Edge WebView2) — no browser. `--browser` falls
back to the default browser; `--server-only` just runs the server.
"""
import socket
import sys
import threading
import time
import os

if sys.stdout is None:
    sys.stdout = open("dashboard_gui.log", "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = sys.stdout

import uvicorn

from . import config

URL = f"http://{config.HOST}:{config.PORT}"
WINDOW_TITLE = config.WINDOW_TITLE
ICON_PATH = config.STATIC_DIR / "icon.ico"


def _run_server():
    uvicorn.run("src.dashboard.server:app", host=config.HOST, port=config.PORT,
                log_level="warning")


def _apply_windows_icon():
    """Set the window/taskbar icon (otherwise Windows shows the python icon).

    pywebview only supports `icon=` on GTK/QT, so on Windows we send WM_SETICON
    to the window once it exists, and set an explicit AppUserModelID so the
    taskbar doesn't group/brand us as python.exe."""
    if sys.platform != "win32" or not ICON_PATH.exists():
        return
    import ctypes
    user32 = ctypes.windll.user32
    WM_SETICON, ICON_SMALL, ICON_BIG = 0x0080, 0, 1
    IMAGE_ICON, LR_LOADFROMFILE = 1, 0x0010
    for _ in range(120):                       # the window appears asynchronously
        hwnd = user32.FindWindowW(None, WINDOW_TITLE)
        if hwnd:
            for which, size in ((ICON_SMALL, 16), (ICON_BIG, 48)):
                hicon = user32.LoadImageW(0, str(ICON_PATH), IMAGE_ICON,
                                          size, size, LR_LOADFROMFILE)
                if hicon:
                    user32.SendMessageW(hwnd, WM_SETICON, which, hicon)
            return
        time.sleep(0.25)


def _wait_port(timeout=15.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((config.HOST, config.PORT), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def main():
    t = threading.Thread(target=_run_server, daemon=True)
    t.start()
    if not _wait_port():
        print("ERRORE: il server non risponde su " + URL)
        sys.exit(1)

    if "--server-only" in sys.argv:
        print(f"Mission Control (server only) -> {URL}")
        t.join()
        return

    if "--browser" not in sys.argv:
        try:
            import webview
            if sys.platform == "win32":
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "TennisBetting.MissionControl")
            webview.create_window(
                WINDOW_TITLE, URL,
                width=1500, height=940, min_size=(1100, 700))
            threading.Thread(target=_apply_windows_icon, daemon=True).start()
            webview.start()   # blocks until the window is closed
            return
        except Exception as e:
            print(f"[!] finestra nativa non disponibile ({e}) — apro il browser")

    import webbrowser
    webbrowser.open(URL)
    print(f"Mission Control -> {URL}  (Ctrl+C per chiudere)")
    t.join()


if __name__ == "__main__":
    main()
