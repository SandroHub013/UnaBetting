"""Single source of truth for the project's headline numbers.

Reads the current model metrics (models/atp_metrics.json) and the last honest
backtest (reports/last_backtest.json) and publishes them to:
  - docs/web/metrics.js  (window.__METRICS)  -> website reads this at runtime
  - README.md            (between <!--METRICS--> ... <!--/METRICS--> markers)

The app already reads atp_metrics.json live via /api/model, so it stays in sync
automatically. Run this after each retrain/backtest (the metrics-publish loop does).
"""
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pct(x, d=1):
    return f"{x * 100:.{d}f}" if isinstance(x, (int, float)) else "—"


def main():
    m = json.loads((ROOT / "models" / "atp_metrics.json").read_text())
    am = m.get("all_models", {})
    # schema-tolerant (legacy best_* vs routed E4)
    if "best_accuracy" in m:
        acc, ll, roc = m["best_accuracy"], m["best_log_loss"], m["best_roc_auc"]
    else:
        acc, ll, roc = m.get("routed_accuracy"), m.get("routed_log_loss"), m.get("routed_roc_auc")
    odds_acc = (am.get("target_odds_ensemble") or {}).get("accuracy")
    trained = (m.get("trained_at") or "")[:10]

    bt_path = ROOT / "reports" / "last_backtest.json"
    bt = json.loads(bt_path.read_text()) if bt_path.exists() else {}
    roi = bt.get("roi_pct")
    winrate = (bt.get("win_rate") or 0) * 100 if bt.get("win_rate") is not None else None

    metrics = {
        "acc": _pct(acc), "ll": f"{ll:.3f}" if ll else "—",
        "roc": f"{roc:.3f}" if roc else "—", "odds_acc": _pct(odds_acc),
        "roi": (f"{roi:.0f}" if roi is not None else "—"),
        "winrate": (f"{winrate:.0f}" if winrate is not None else "—"),
        "trained": trained or str(date.today()),
    }

    # 1) website single source of truth
    web = ROOT / "docs" / "web" / "metrics.js"
    web.write_text("window.__METRICS=" + json.dumps(metrics) + ";", encoding="utf-8")

    # 2) README markered block
    block = (
        "<!--METRICS-->\n"
        f"**Current honest numbers** (test 2025+, updated {metrics['trained']}): "
        f"model accuracy **{metrics['acc']}%** · "
        f"log loss {metrics['ll']} · ROC {metrics['roc']} · "
        f"odds-ensemble {metrics['odds_acc']}% on real-odds rows · "
        f"honest backtest ROI **{metrics['roi']}%** (negative — no betting edge).\n"
        "<!--/METRICS-->"
    )
    readme = ROOT / "README.md"
    txt = readme.read_text(encoding="utf-8")
    if "<!--METRICS-->" in txt:
        txt = re.sub(r"<!--METRICS-->.*?<!--/METRICS-->", block, txt, flags=re.S)
    else:  # insert right after the disclaimer blockquote's first line
        txt = txt.replace("> ## ⚠️ Honest disclaimer", block + "\n\n> ## ⚠️ Honest disclaimer", 1)
    readme.write_text(txt, encoding="utf-8")

    print("published:", json.dumps(metrics))


if __name__ == "__main__":
    main()
