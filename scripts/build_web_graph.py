"""Build docs/web/graph-data.js from the graphify export, trimmed for the web.

The website's live 3D graph reads window.__GRAPH (a <script>, so it works under
file:// too — fetch() would be CORS-blocked locally). Re-run whenever graphify
re-maps the codebase so the site stays in sync.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = ROOT / "graphify-out" / "graph.json"
out = ROOT / "docs" / "web" / "graph-data.js"

g = json.loads(src.read_text(encoding="utf-8"))
ids = {n["id"] for n in g["nodes"]}
nodes = [{"id": n["id"], "label": (n.get("label") or n["id"])[:60],
          "group": int(n.get("community", 0) or 0)} for n in g["nodes"]]
links = []
for e in g.get("links", []):
    s = e["source"] if isinstance(e["source"], str) else e["source"].get("id")
    t = e["target"] if isinstance(e["target"], str) else e["target"].get("id")
    if s in ids and t in ids:
        links.append({"source": s, "target": t})

out.parent.mkdir(parents=True, exist_ok=True)
payload = json.dumps({"nodes": nodes, "links": links}, ensure_ascii=False, separators=(",", ":"))
out.write_text("window.__GRAPH=" + payload + ";", encoding="utf-8")
print(f"wrote {out.relative_to(ROOT)} — {len(nodes)} nodes, {len(links)} links, "
      f"{out.stat().st_size // 1024} KB")
