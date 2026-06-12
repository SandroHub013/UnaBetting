"""Maintainer one-shot: cut a new release.

  python scripts/publish_release.py --notes "What changed"

Steps:
  1. read VERSION
  2. build the slim runtime bundle (scripts/build_release_bundle.py)
  3. gh release create v<VERSION> with the bundle attached

Creating the release also creates+pushes the tag v<VERSION>, which triggers
.github/workflows/release.yml — the matrix then builds the Windows/macOS/Linux
installers and uploads them to this same release. End users download their
installer; the in-app updater pulls the runtime bundle for model-only updates.

Bump VERSION (and retrain if the models changed) BEFORE running this.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd, **kw):
    print("  $", " ".join(cmd))
    return subprocess.run(cmd, cwd=ROOT, **kw)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--notes", default="", help="release notes (markdown)")
    ap.add_argument("--draft", action="store_true", help="create as a draft")
    ap.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = ap.parse_args()

    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    tag = f"v{version}"
    zip_path = ROOT / "dist" / f"UnaBetting-runtime-v{version}.zip"

    # Refuse to clobber an existing release/tag.
    existing = subprocess.run(["gh", "release", "view", tag], cwd=ROOT,
                              capture_output=True, text=True)
    if existing.returncode == 0:
        print(f"[X] release {tag} already exists. Bump VERSION first.")
        return 1

    print(f"[*] building runtime bundle for {tag} ...")
    if _run([sys.executable, "scripts/build_release_bundle.py"]).returncode != 0:
        return 1
    if not zip_path.exists():
        print(f"[X] expected bundle not found: {zip_path}")
        return 1

    if not args.yes:
        print(f"\n[?] create GitHub release {tag} with {zip_path.name}? [y/N] ", end="")
        if input().strip().lower() not in ("y", "yes"):
            print("aborted.")
            return 1

    cmd = ["gh", "release", "create", tag, str(zip_path),
           "--title", f"UnaBetting {tag}",
           "--notes", args.notes or f"UnaBetting {tag}"]
    if args.draft:
        cmd.append("--draft")
    rc = _run(cmd).returncode
    if rc == 0:
        print(f"\n[+] released {tag}. The release workflow is now building the "
              "Windows/macOS/Linux installers and will attach them here:")
        print(f"    https://github.com/SandroHub013/UnaBetting/releases/tag/{tag}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
