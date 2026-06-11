"""Append the current models/atp_metrics.json snapshot to reports/metrics_history.csv.

Run after every training so the evolution loops can track the trajectory and
detect regressions. Idempotent per trained_at timestamp.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
metrics_path = ROOT / "models" / "atp_metrics.json"
out_path = ROOT / "reports" / "metrics_history.csv"

m = json.loads(metrics_path.read_text())
row = {
    "trained_at": m["trained_at"],
    "best_model": m["best_model"],
    "accuracy": round(m["best_accuracy"], 6),
    "log_loss": round(m["best_log_loss"], 6),
    "roc_auc": round(m["best_roc_auc"], 6),
    "brier": round(m["best_brier"], 6),
    "ece": round(m["best_ece"], 6),
    "lgbm_accuracy": round(m["all_models"].get("target_lightgbm", {}).get("accuracy", float("nan")), 6),
    "xgb_log_loss": round(m["all_models"].get("target_xgboost", {}).get("log_loss", float("nan")), 6),
}

out_path.parent.mkdir(exist_ok=True)
existing = []
if out_path.exists():
    with open(out_path, newline="") as f:
        existing = list(csv.DictReader(f))
    if any(r["trained_at"] == row["trained_at"] for r in existing):
        print(f"already logged: {row['trained_at']}")
        raise SystemExit(0)

with open(out_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(row.keys()))
    w.writeheader()
    for r in existing:
        w.writerow({k: r.get(k, "") for k in row})
    w.writerow(row)
print(f"logged {row['trained_at']}: acc={row['accuracy']} ll={row['log_loss']} roc={row['roc_auc']}")
