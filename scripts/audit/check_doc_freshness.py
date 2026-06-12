#!/usr/bin/env python
"""scripts/audit/check_doc_freshness.py — Warn if specs/ADRs are stale (>6 months)."""
import sys
from datetime import datetime, timedelta
from pathlib import Path

MAX_AGE_DAYS = 180  # 6 months

DOC_DIRS = [
    'docs/specs',
    'docs/roadmap',
    'docs/operations',
]

def get_last_modified(path: Path) -> datetime:
    stat = path.stat()
    return datetime.fromtimestamp(stat.st_mtime)

def check_freshness(root: Path) -> list[tuple[Path, int]]:
    stale = []
    for doc_dir in DOC_DIRS:
        dir_path = root / doc_dir
        if not dir_path.exists():
            continue
        for md_file in dir_path.rglob('*.md'):
            if md_file.name == 'README.md':
                continue  # README is index, not a spec
            mtime = get_last_modified(md_file)
            age = (datetime.now() - mtime).days
            if age > MAX_AGE_DAYS:
                stale.append((md_file.relative_to(root), age))
    return stale

def main():
    root = Path(__file__).resolve().parent.parent.parent
    stale = check_freshness(root)
    
    if stale:
        print(f'⚠️  {len(stale)} document(s) older than {MAX_AGE_DAYS} days:')
        for path, age in sorted(stale, key=lambda x: -x[1]):
            print(f'  {path} (last modified {age} days ago)')
        return 1
    else:
        print(f'✅ All documents fresh (< {MAX_AGE_DAYS} days).')
        return 0

if __name__ == '__main__':
    sys.exit(main())
