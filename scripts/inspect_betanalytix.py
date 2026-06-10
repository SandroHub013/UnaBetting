"""One-off: dump betanalytix.db schema + row counts for dashboard build."""
import sqlite3

con = sqlite3.connect(r"G:\tennis betting\data\betanalytix.db")
cur = con.cursor()
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("tables:", tables)
for t in tables:
    cols = [c[1] for c in cur.execute(f"PRAGMA table_info({t})")]
    n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"\n{t} ({n} rows): {cols}")
    for row in cur.execute(f"SELECT * FROM {t} LIMIT 2"):
        print("  ", row)
