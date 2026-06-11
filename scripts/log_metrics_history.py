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
am = m.get("all_models", {})


def _r(x):
    return round(x, 6) if isinstance(x, (int, float)) else ""


# Schema-tolerant: old runs used best_*; the routed E4 schema uses routed_* +
# named families (target_odds_*, target_blind_*, target_routed_ensemble).
if "best_accuracy" in m:                         # legacy schema
    best_model = m.get("best_model", "")
    acc, ll, roc = m["best_accuracy"], m["best_log_loss"], m["best_roc_auc"]
    brier, ece = m.get("best_brier", ""), m.get("best_ece", "")
else:                                            # routed E4 schema
    best_model = "target_routed_ensemble"
    acc = m.get("routed_accuracy")
    ll = m.get("routed_log_loss")
    roc = m.get("routed_roc_auc")
    routed = am.get("target_routed_ensemble", {})
    brier, ece = routed.get("brier", ""), m.get("routed_ece", "")

# headline = the routed/overall model; also track the odds-ensemble (real-odds rows)
odds_ens = am.get("target_odds_ensemble", am.get("target_ensemble", {}))
row = {
    "trained_at": m["trained_at"],
    "best_model": best_model,
    "accuracy": _r(acc),
    "log_loss": _r(ll),
    "roc_auc": _r(roc),
    "brier": _r(brier),
    "ece": _r(ece),
    "odds_ens_accuracy": _r(odds_ens.get("accuracy", float("nan"))),
    "odds_ens_log_loss": _r(odds_ens.get("log_loss", float("nan"))),
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
