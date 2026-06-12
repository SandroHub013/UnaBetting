#!/usr/bin/env python
"""scripts/ci/collect_coverage.py — Collect pytest coverage and output XML."""
import subprocess
import sys

def main():
    # Run tests with coverage
    result = subprocess.run([
        sys.executable, '-m', 'pytest',
        '--cov=src',
        '--cov-report=xml:coverage.xml',
        '--cov-report=term-missing',
        'tests/',
    ], capture_output=True, text=True)
    
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    
    return result.returncode

if __name__ == '__main__':
    sys.exit(main())
