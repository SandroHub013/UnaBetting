"""
Tennis Prediction Model - Data Update Automation Script
Pulls latest data from all sources, rebuilds the unified dataset, and optionally retrains.
"""

import os
import sys
import subprocess
import requests
import time
import yaml
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def update_git_repos(config):
    """Pull latest data from all git repositories."""
    print("\n" + "=" * 60)
    print("📦 AGGIORNAMENTO REPOSITORY GIT")
    print("=" * 60)
    
    repos = {
        "TML-Database": PROJECT_ROOT / config["paths"]["raw_data"] / "TML-Database",
        "Sackmann ATP": PROJECT_ROOT / config["paths"]["raw_data"] / "sackmann" / "tennis_atp",
        "Sackmann WTA": PROJECT_ROOT / config["paths"]["raw_data"] / "sackmann" / "tennis_wta",
        "Point-by-Point": PROJECT_ROOT / config["paths"]["raw_data"] / "sackmann" / "tennis_pointbypoint",
    }
    
    for name, repo_path in repos.items():
        if not repo_path.exists():
            print(f"  ⚠ {name} non trovato: {repo_path}")
            continue
            
        print(f"\n  ↻ Aggiornamento {name}...")
        try:
            # Fetch latest from remote
            subprocess.run(
                ["git", "-C", str(repo_path), "fetch", "origin"],
                check=True, capture_output=True, text=True, timeout=60
            )
            
            # Detect default branch
            result = subprocess.run(
                ["git", "-C", str(repo_path), "symbolic-ref", "refs/remotes/origin/HEAD"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                default_branch = result.stdout.strip().split("/")[-1]
            else:
                default_branch = "master"
            
            # Reset to latest
            subprocess.run(
                ["git", "-C", str(repo_path), "reset", "--hard", f"origin/{default_branch}"],
                check=True, capture_output=True, text=True, timeout=30
            )
            
            # Check latest commit date
            log_result = subprocess.run(
                ["git", "-C", str(repo_path), "log", "-1", "--format=%ad", "--date=short"],
                capture_output=True, text=True, timeout=10
            )
            last_date = log_result.stdout.strip() if log_result.returncode == 0 else "?"
            print(f"  ✓ {name} aggiornato (ultimo commit: {last_date})")
            
        except subprocess.CalledProcessError as e:
            print(f"  ✗ Errore aggiornamento {name}: {e.stderr}")
        except subprocess.TimeoutExpired:
            print(f"  ✗ Timeout aggiornamento {name}")


def update_odds(config):
    """Re-download latest odds files from tennis-data.co.uk."""
    print("\n" + "=" * 60)
    print("📊 AGGIORNAMENTO QUOTE - tennis-data.co.uk")
    print("=" * 60)
    
    base_url = config["data"]["tennis_data_co_uk"]["base_url"]
    output_dir = PROJECT_ROOT / config["paths"]["raw_data"] / "tennis_data_co_uk"
    current_year = datetime.now().year
    
    # Only re-download current year and previous year
    for year in [current_year - 1, current_year]:
        for tour_prefix, url_suffix in [("atp", ""), ("wta", "w")]:
            for ext in ["xlsx", "xls", "csv"]:
                url = f"{base_url}/{year}{url_suffix}/{year}.{ext}"
                try:
                    resp = requests.get(url, timeout=30, allow_redirects=True)
                    if resp.status_code == 200 and len(resp.content) > 1000:
                        content_type = resp.headers.get('Content-Type', '')
                        if 'html' in content_type:
                            continue
                        
                        filepath = output_dir / f"{tour_prefix}_{year}.{ext}"
                        old_size = filepath.stat().st_size if filepath.exists() else 0
                        with open(filepath, "wb") as f:
                            f.write(resp.content)
                        
                        new_size = len(resp.content)
                        delta = new_size - old_size
                        delta_str = f" (+{delta:,} bytes)" if delta > 0 else f" ({delta:,} bytes)" if delta < 0 else ""
                        print(f"  ✓ {tour_prefix.upper()} {year}: {new_size:,} bytes{delta_str}")
                        break
                except requests.RequestException:
                    continue
            time.sleep(0.3)


def rebuild_pipeline(config, retrain=False):
    """Rebuild the data pipeline: clean → features → (optional) train."""
    print("\n" + "=" * 60)
    print("🔧 REBUILD PIPELINE")
    print("=" * 60)
    
    # Step 1: Clean
    print("\n  1️⃣  Ricostruzione dataset unificato...")
    subprocess.run(
        [sys.executable, "-m", "src.data.clean"],
        cwd=str(PROJECT_ROOT),
        timeout=300
    )
    
    # Step 2: Features
    print("\n  2️⃣  Ricostruzione feature matrix...")
    subprocess.run(
        [sys.executable, "-m", "src.features.build_features"],
        cwd=str(PROJECT_ROOT),
        timeout=600
    )
    
    if retrain:
        # Step 3: Train
        print("\n  3️⃣  Re-training modelli...")
        subprocess.run(
            [sys.executable, "-m", "src.models.train"],
            cwd=str(PROJECT_ROOT),
            timeout=900
        )
    
    print("\n✅ Pipeline rebuild completato!")


def check_data_freshness(config):
    """Report on data freshness."""
    print("\n" + "=" * 60)
    print("📅 REPORT FRESCHEZZA DATI")
    print("=" * 60)
    
    unified_path = PROJECT_ROOT / config["paths"]["processed_data"] / "atp_unified.csv"
    if unified_path.exists():
        import pandas as pd
        # Read only last few rows for speed
        df = pd.read_csv(unified_path, usecols=["tourney_date"], low_memory=False)
        df["tourney_date"] = pd.to_datetime(df["tourney_date"], errors="coerce")
        last_date = df["tourney_date"].max()
        total_matches = len(df)
        
        days_old = (pd.Timestamp.now() - last_date).days if not pd.isna(last_date) else "?"
        
        print(f"  Dataset: {total_matches:,} partite")
        print(f"  Primo match: {df['tourney_date'].min().strftime('%Y-%m-%d')}")
        print(f"  Ultimo match: {last_date.strftime('%Y-%m-%d')}")
        print(f"  Giorni di gap: {days_old}")
        
        if isinstance(days_old, int) and days_old > 14:
            print(f"\n  ⚠ ATTENZIONE: dati vecchi di {days_old} giorni!")
            print(f"  → Esegui: python update_data.py --retrain")
    else:
        print("  ✗ Dataset unificato non trovato")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Aggiorna dati tennis e ricostruisci pipeline")
    parser.add_argument("--retrain", action="store_true", help="Anche re-trainare i modelli")
    parser.add_argument("--check", action="store_true", help="Solo verifica freschezza dati")
    parser.add_argument("--skip-git", action="store_true", help="Salta aggiornamento git repos")
    parser.add_argument("--skip-odds", action="store_true", help="Salta download quote")
    parser.add_argument("--skip-rebuild", action="store_true", help="Salta rebuild pipeline")
    args = parser.parse_args()
    
    config = load_config()
    
    print("🎾 TENNIS PREDICTION MODEL - DATA UPDATE")
    print("=" * 60)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if args.check:
        check_data_freshness(config)
        sys.exit(0)
    
    if not args.skip_git:
        update_git_repos(config)
    
    if not args.skip_odds:
        update_odds(config)
    
    if not args.skip_rebuild:
        rebuild_pipeline(config, retrain=args.retrain)
    
    check_data_freshness(config)
    
    print("\n✅ Aggiornamento completato!")
