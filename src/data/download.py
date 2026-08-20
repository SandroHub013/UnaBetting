"""
Tennis Prediction Model - Data Download Script
Downloads all data sources: JeffSackmann repos, tennis-data.co.uk odds, etc.
"""

import os
import sys
import subprocess
import requests
import zipfile
import io
import yaml
import time
from pathlib import Path
from tqdm import tqdm

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


def load_config():
    """Load project configuration."""
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def ensure_dirs(config):
    """Create all necessary data directories."""
    dirs = [
        PROJECT_ROOT / config["paths"]["raw_data"] / "sackmann",
        PROJECT_ROOT / config["paths"]["raw_data"] / "tennis_data_co_uk",
        PROJECT_ROOT / config["paths"]["raw_data"] / "scraped",
        PROJECT_ROOT / config["paths"]["processed_data"],
        PROJECT_ROOT / config["paths"]["features"],
        PROJECT_ROOT / config["paths"]["models"],
        PROJECT_ROOT / config["paths"]["reports"],
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ {d.relative_to(PROJECT_ROOT)}")


def clone_or_pull_repo(repo_url, target_dir):
    """Clone a git repository, or pull if it already exists."""
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    repo_path = Path(target_dir) / repo_name

    if repo_path.exists() and (repo_path / ".git").exists():
        print(f"  ↻ Aggiornamento {repo_name}...")
        try:
            subprocess.run(
                ["git", "-C", str(repo_path), "pull", "--ff-only"],
                check=True,
                capture_output=True,
                text=True,
            )
            print(f"  ✓ {repo_name} aggiornato")
        except subprocess.CalledProcessError as e:
            print(f"  ⚠ Pull fallito per {repo_name}: {e.stderr}")
    else:
        print(f"  ↓ Clonazione {repo_name}...")
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(repo_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            print(f"  ✓ {repo_name} clonato")
        except subprocess.CalledProcessError as e:
            print(f"  ✗ Errore clonazione {repo_name}: {e.stderr}")
            return False
    return True


def download_sackmann_repos(config):
    """Download all JeffSackmann tennis data repositories."""
    print("\n" + "=" * 60)
    print("📦 DOWNLOAD REPOSITORY JEFFSACKMANN")
    print("=" * 60)

    sackmann_dir = PROJECT_ROOT / config["paths"]["raw_data"] / "sackmann"
    repos = config["data"]["sackmann"]

    results = {}
    for name, url in repos.items():
        success = clone_or_pull_repo(url, sackmann_dir)
        results[name] = success

    return results


def download_tml_database(config):
    """Download the TML-Database repository for ATP data."""
    print("\n" + "=" * 60)
    print("📦 DOWNLOAD TML-DATABASE (ATP)")
    print("=" * 60)

    raw_dir = PROJECT_ROOT / config["paths"]["raw_data"]
    url = "https://github.com/Tennismylife/TML-Database.git"

    success = clone_or_pull_repo(url, raw_dir)
    return success


def _atp_urls(base_url, year):
    # usually /{year}/{year}.xlsx; the last two are historical fallbacks
    return [
        f"{base_url}/{year}/{year}.xlsx",
        f"{base_url}/{year}/{year}.xls",
        f"{base_url}/{year}/{year}.csv",
        f"{base_url}/{year}/{str(year)[-2:]}.xlsx",
        f"{base_url}/{year}/archives.php",
    ]


def _wta_urls(base_url, year):
    return [
        f"{base_url}/{year}w/{year}.xlsx",
        f"{base_url}/{year}w/{year}.xls",
        f"{base_url}/{year}w/{year}.csv",
    ]


def _try_download(url):
    """Response body for a real file, or None (missing, tiny, or an HTML page)."""
    try:
        resp = requests.get(url, timeout=30, allow_redirects=True)
    except requests.RequestException:
        return None
    if resp.status_code != 200 or len(resp.content) <= 1000:
        return None
    if 'html' in resp.headers.get('Content-Type', ''):
        return None
    return resp.content


def _download_year_file(base_url, output_dir, tour, year, urls_of):
    """First candidate URL that yields a real file wins."""
    for url in urls_of(base_url, year):
        content = _try_download(url)
        if content is None:
            continue
        ext = url.split(".")[-1]
        if ext == "php":
            ext = "csv"  # fallback
        with open(output_dir / f"{tour}_{year}.{ext}", "wb") as f:
            f.write(content)
        return True
    return False


def _download_tour(base_url, output_dir, tour, years, urls_of, miss_note=""):
    downloaded = errors = 0
    for year in years:
        if _download_year_file(base_url, output_dir, tour, year, urls_of):
            print(f"    ✓ {tour.upper()} {year}")
            downloaded += 1
        else:
            suffix = f" {miss_note}" if miss_note else ""
            print(f"    ⚠ {tour.upper()} {year} - Non trovato{suffix}")
            errors += 1
        time.sleep(0.3)
    return downloaded, errors


def download_tennis_data_co_uk(config):
    """
    Download historical betting odds from tennis-data.co.uk.
    Downloads ATP and WTA CSV files for each year.
    """
    print("\n" + "=" * 60)
    print("📊 DOWNLOAD QUOTE E RISULTATI RECENTI - tennis-data.co.uk")
    print("=" * 60)

    base_url = config["data"]["tennis_data_co_uk"]["base_url"]
    output_dir = PROJECT_ROOT / config["paths"]["raw_data"] / "tennis_data_co_uk"

    # Use current year from system
    from datetime import datetime
    current_year = datetime.now().year
    downloaded = 0
    errors = 0

    atp_start = config["data"]["tennis_data_co_uk"]["atp_start_year"]
    print(f"\n  ATP ({atp_start}-{current_year}):")
    got, missed = _download_tour(
        base_url, output_dir, "atp", range(atp_start, current_year + 1),
        _atp_urls, "(possibile gap o formato diverso)")
    downloaded += got
    errors += missed

    wta_start = config["data"]["tennis_data_co_uk"]["wta_start_year"]
    print(f"\n  WTA ({wta_start}-{current_year}):")
    got, missed = _download_tour(
        base_url, output_dir, "wta", range(wta_start, current_year + 1), _wta_urls)
    downloaded += got
    errors += missed

    print(f"\n  Totale: {downloaded} file scaricati, {errors} errori")
    return downloaded, errors


def download_all():
    """Main download function - runs all data acquisition."""
    print("🎾 TENNIS PREDICTION MODEL - DATA DOWNLOAD")
    print("=" * 60)

    config = load_config()

    # 1. Create directory structure
    print("\n📁 Creazione struttura cartelle...")
    ensure_dirs(config)

    # 2. Download Sackmann repos
    sackmann_results = download_sackmann_repos(config)

    # 3. Download TML-Database (ATP)
    tml_success = download_tml_database(config)

    # 4. Download tennis-data.co.uk odds
    odds_downloaded, _odds_errors = download_tennis_data_co_uk(config)

    # Summary
    print("\n" + "=" * 60)
    print("📋 RIEPILOGO DOWNLOAD")
    print("=" * 60)

    print("\nJeffSackmann Repos:")
    for name, success in sackmann_results.items():
        status = "✓" if success else "✗"
        print(f"  {status} {name}")

    tml_status = "✓" if tml_success else "✗"
    print("\nTML-Database (ATP):")
    print(f"  {tml_status} TML-Database")

    print(f"\nQuote tennis-data.co.uk: {odds_downloaded} file scaricati")

    print("\n✅ Download completato!")
    print("Prossimo step: python -m src.data.clean")


if __name__ == "__main__":
    download_all()
