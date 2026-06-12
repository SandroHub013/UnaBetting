#!/usr/bin/env python
"""scripts/audit/check_secrets.py — Scan for hardcoded secrets in tracked files."""
import re
import sys
from pathlib import Path

SECRET_PATTERNS = [
    (r'(?i)(api[_-]?key|apikey|secret|token|password)\s*[:=]\s*["']?[a-zA-Z0-9_\-]{20,}["']?', 'Generic secret'),
    (r'ODDS_API_KEY\s*=\s*[a-zA-Z0-9_\-]{20,}', 'The Odds API key'),
    (r'OPENROUTER_API_KEY\s*=\s*[a-zA-Z0-9_\-]{20,}', 'OpenRouter API key'),
    (r'[a-zA-Z0-9_\-]{32,}', 'Possible 32+ char secret'),
]

ALLOWLIST_PATHS = {
    '.env.example',
    '.github/ISSUE_TEMPLATE/*.md',
    'docs/**/*.md',
    'tests/**/*.py',
}

ALLOWLIST_PATTERNS = [
    'your_odds_api_key_here',
    'your_openrouter_api_key_here',
]

def should_skip(path: Path) -> bool:
    for pattern in ALLOWLIST_PATHS:
        if path.match(pattern):
            return True
    return False

def is_false_positive(line: str) -> bool:
    for pattern in ALLOWLIST_PATTERNS:
        if pattern in line:
            return True
    return False

def scan_file(path: Path) -> list[tuple[int, str, str]]:
    findings = []
    try:
        content = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return findings
    for i, line in enumerate(content.splitlines(), 1):
        if is_false_positive(line):
            continue
        for pattern, desc in SECRET_PATTERNS:
            if re.search(pattern, line):
                findings.append((i, desc, line.strip()[:100]))
    return findings

def main():
    root = Path(__file__).resolve().parent.parent.parent
    tracked_files = []
    
    # Get tracked files from git
    import subprocess
    result = subprocess.run(['git', 'ls-files'], cwd=root, capture_output=True, text=True)
    if result.returncode != 0:
        print('Error: git ls-files failed', file=sys.stderr)
        return 1
    
    all_findings = []
    for rel_path in result.stdout.splitlines():
        path = root / rel_path
        if should_skip(path):
            continue
        findings = scan_file(path)
        for line_no, desc, snippet in findings:
            all_findings.append((rel_path, line_no, desc, snippet))
    
    if all_findings:
        print(f'❌ Found {len(all_findings)} potential secret(s):')
        for rel_path, line_no, desc, snippet in all_findings:
            print(f'  {rel_path}:{line_no}: {desc} -> {snippet}')
        return 1
    else:
        print('✅ No secrets found in tracked files.')
        return 0

if __name__ == '__main__':
    sys.exit(main())
