# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — cross-platform desktop build (Windows / macOS / Linux).

Build (run on the TARGET OS — you cannot cross-build a mac .app from Windows):
    python scripts/build_release_bundle.py      # produces dist/bundle_stage/
    pyinstaller packaging/unabetting.spec --noconfirm

Output:
    Windows : dist/UnaBetting/UnaBetting.exe   (onedir; wrap in Inno Setup for .exe installer)
    macOS   : dist/UnaBetting.app
    Linux   : dist/UnaBetting/UnaBetting        (tar.gz or AppImage it)

The slim runtime bundle (dist/bundle_stage) is baked in as the first-run seed; the
1.7 GB raw dataset and the dev-only model families are never included.
"""
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve().parent       # SPECPATH = packaging/ ; parent = repo root

STAGE = ROOT / "dist" / "bundle_stage"
if not STAGE.is_dir():
    raise SystemExit("dist/bundle_stage missing — run: python scripts/build_release_bundle.py")

# Read-only data baked into the app (becomes BUNDLE_DIR/... at runtime).
datas = [
    (str(ROOT / "src" / "dashboard" / "static"), "src/dashboard/static"),
    (str(ROOT / "VERSION"), "."),
]
for sub in ("models", "data", "config", "reports"):
    p = STAGE / sub
    if p.is_dir():
        datas.append((str(p), sub))

# ML libs need their data/binaries + dynamic submodules collected explicitly.
binaries = []
hiddenimports = []
for pkg in ("xgboost", "lightgbm", "sklearn", "uvicorn", "webview"):
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hiddenimports += h
    except Exception:
        pass
hiddenimports += collect_submodules("sklearn")
hiddenimports += ["uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto",
                  "uvicorn.protocols.websockets.auto", "uvicorn.lifespan.on"]

# Keep the binary lean: training-only / optional heavyweight deps are excluded.
excludes = ["torch", "torchvision", "matplotlib", "pytest", "notebook", "IPython",
            "optuna", "pygame", "pyttsx3"]

block_cipher = None

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

_icon = None
if sys.platform == "win32" and (ROOT / "src/dashboard/static/icon.ico").exists():
    _icon = str(ROOT / "src/dashboard/static/icon.ico")
elif sys.platform == "darwin" and (ROOT / "packaging/icon.icns").exists():
    _icon = str(ROOT / "packaging/icon.icns")

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="UnaBetting",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,            # GUI app — no console window
    icon=_icon,
)
coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=False, name="UnaBetting",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="UnaBetting.app",
        icon=_icon,
        bundle_identifier="xyz.unabetting.app",
        info_plist={"NSHighResolutionCapable": True, "LSBackgroundOnly": False},
    )
