"""Build the slim *runtime bundle* shipped inside the packaged app.

The app needs only a few tens of MB to run (trained models + the precomputed
inference state + a little reference data) — NOT the ~1.7 GB raw dataset, which is
maintainer-only. This script collects exactly the runtime-critical files into a
staging tree and zips it, with a manifest (version + sha256 per file).

Run it after a retrain. The PyInstaller build bakes the staging tree into the app,
and `gh release create` attaches the zip so the in-app updater can pull model-only
updates without a reinstall.

    python scripts/build_release_bundle.py            # -> dist/UnaBetting-runtime-v<ver>.zip
    python scripts/build_release_bundle.py --out dist

What runs the app (verified against src/live/inference.py + src/models):
  - h2h / spread / totals models + the routed odds/blind ensembles
  - atp_scaler / atp_medians / atp_features.txt / atp_metrics.json / player_mapping
  - live_engines.pkl  (precomputed ELO + rolling-stats state — predict with no raw data)
  - data/processed/atp_unified.csv  (single-match predictor lookup)
  - config/config.yaml, reports/last_backtest.json, docs/web/metrics.js, VERSION
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Must exist — the build fails loudly without these.
CORE = [
    "VERSION",
    "config/config.yaml",
    "models/atp_scaler.pkl",
    "models/atp_medians.pkl",
    "models/atp_features.txt",
    "models/atp_metrics.json",
    "models/atp_player_mapping.pkl",
    "models/wta_scaler.pkl",
    "models/wta_medians.pkl",
    "models/wta_features.txt",
    "models/wta_metrics.json",
    "models/wta_player_mapping.pkl",
    "models/atp_live_engines.pkl",
    "models/wta_live_engines.pkl",
    "models/atp_target_xgboost.pkl",
    "models/atp_game_diff_xgboost.pkl",
    "models/atp_total_games_ensemble.pkl",
    "models/atp_target_odds_ensemble.pkl",
    "models/atp_target_blind_ensemble.pkl",
    "models/wta_target_xgboost.pkl",
    "models/wta_game_diff_xgboost.pkl",
    "models/wta_total_games_ensemble.pkl",
    "models/wta_target_odds_ensemble.pkl",
    "models/wta_target_blind_ensemble.pkl",
    "data/processed/atp_unified.csv",
    "data/processed/wta_unified.csv",
]

# Nice to have — a warning, not a failure, if missing.
OPTIONAL = [
    "reports/last_backtest.json",
    "docs/web/metrics.js",
    "models/atp_target_blind_xgboost.pkl",
    "models/atp_game_diff_blind_ensemble.pkl",
    "models/atp_total_games_blind_ensemble.pkl",
]


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}GB"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "dist"), help="output directory")
    args = ap.parse_args()

    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Resolve the file list.
    missing_core = [r for r in CORE if not (ROOT / r).exists()]
    if missing_core:
        print("[X] missing CORE runtime files — retrain/build first:")
        for r in missing_core:
            print(f"      {r}")
        return 1
    files = list(CORE)
    for r in OPTIONAL:
        if (ROOT / r).exists():
            files.append(r)
        else:
            print(f"[!] optional file absent (skipping): {r}")

    # Manifest + zip.
    manifest = {"name": "UnaBetting", "version": version, "files": []}
    zip_path = out_dir / f"UnaBetting-runtime-v{version}.zip"
    total = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            src = ROOT / rel
            size = src.stat().st_size
            total += size
            manifest["files"].append(
                {"path": rel, "bytes": size, "sha256": _sha256(src)}
            )
            zf.write(src, rel)
            
        import base64
        import os
        from cryptography.hazmat.primitives import serialization
        
        priv_key_path = ROOT / "keys" / "updater_private.pem"
        priv_key_env = os.environ.get("UPDATER_PRIVATE_KEY")
        
        if priv_key_env:
            priv_data = priv_key_env.encode("utf-8")
        elif priv_key_path.exists():
            priv_data = priv_key_path.read_bytes()
        else:
            print("[X] ERROR: Private key not found. Cannot sign the manifest.")
            print("    Generate keys with: python scripts/generate_update_keys.py")
            return 1
            
        try:
            privkey = serialization.load_pem_private_key(priv_data, password=None)
            payload = json.dumps(manifest, separators=(',', ':'), sort_keys=True).encode("utf-8")
            sig = privkey.sign(payload)
            manifest["signature"] = base64.b64encode(sig).decode("utf-8")
        except Exception as e:
            print(f"[X] ERROR: Failed to sign manifest: {e}")
            return 1
            
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    # Drop the manifest next to the zip too (CI / updater read it without unzipping).
    (out_dir / f"UnaBetting-runtime-v{version}.manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    # Also emit an unzipped staging tree that the PyInstaller spec bakes into the
    # app (guarantees the frozen build ships ONLY the slim set, never the full
    # models/ dir). CI unzips the release asset straight into this same path.
    import shutil
    stage = out_dir / "bundle_stage"
    if stage.exists():
        shutil.rmtree(stage)
    for rel in files:
        dst = stage / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dst)
    (stage / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[+] stage:    {stage.relative_to(ROOT) if stage.is_relative_to(ROOT) else stage}")

    print(f"[+] bundle:   {zip_path.relative_to(ROOT) if zip_path.is_relative_to(ROOT) else zip_path}")
    print(f"[+] version:  {version}")
    print(f"[+] files:    {len(files)}  (uncompressed {_human(total)})")
    print(f"[+] zip size: {_human(zip_path.stat().st_size)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
