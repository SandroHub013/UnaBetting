#!/usr/bin/env python
"""scripts/audit/check_dependencies.py — Compare requirements.txt with actual imports."""
import ast
import subprocess
import sys
from pathlib import Path

STDLIB = {
    'os', 'sys', 'json', 're', 'pathlib', 'datetime', 'typing', 'collections',
    'itertools', 'functools', 'dataclasses', 'enum', 'uuid', 'hashlib', 'csv',
    'math', 'statistics', 'random', 'decimal', 'fractions', 'inspect', 'textwrap',
    'warnings', 'logging', 'argparse', 'subprocess', 'threading', 'multiprocessing',
    'asyncio', 'concurrent', 'queue', 'weakref', 'copy', 'pickle', 'shelve',
    'sqlite3', 'html', 'xml', 'email', 'mimetypes', 'base64', 'binascii',
    'codecs', 'locale', 'gettext', 'string', 'time', 'calendar', 'zoneinfo',
    'ipaddress', 'socket', 'selectors', 'select', 'signal', 'mmap', 'ctypes',
    'array', 'struct', 'numbers', 'fractions', 'numbers', 'numbers',
}

def get_imports_from_file(py_file: Path) -> set[str]:
    imports = set()
    try:
        tree = ast.parse(py_file.read_text(encoding='utf-8', errors='ignore'), filename=str(py_file))
    except SyntaxError:
        return imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split('.')[0])
    return imports

def get_all_imports(src_root: Path) -> set[str]:
    all_imports = set()
    for py_file in src_root.rglob('*.py'):
        if '__pycache__' in py_file.parts or '_archive' in py_file.parts:
            continue
        imports = get_imports_from_file(py_file)
        all_imports.update(imports)
    return all_imports

def get_installed_packages() -> set[str]:
    result = subprocess.run([sys.executable, '-m', 'pip', 'list', '--format=freeze'], capture_output=True, text=True)
    packages = set()
    for line in result.stdout.splitlines():
        if '==' in line:
            pkg = line.split('==')[0].lower().replace('-', '_')
            packages.add(pkg)
    return packages

def parse_requirements(req_file: Path) -> set[str]:
    packages = set()
    if not req_file.exists():
        return packages
    for line in req_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # Remove version specifiers and extras
        pkg = re.split(r'[<>=!~\[\]]', line)[0].strip().lower().replace('-', '_')
        packages.add(pkg)
    return packages

import re

def main():
    root = Path(__file__).resolve().parent.parent.parent
    src_root = root / 'src'
    req_file = root / 'requirements.txt'
    
    print('[AUDIT] Scanning imports in src/...')
    imports = get_all_imports(src_root)
    print(f'  Found {len(imports)} unique imports')
    
    print('[AUDIT] Reading requirements.txt...')
    required = parse_requirements(req_file)
    print(f'  Found {len(required)} required packages')
    
    print('[AUDIT] Checking installed packages...')
    installed = get_installed_packages()
    print(f'  Found {len(installed)} installed packages')
    
    # Imports not in requirements (but could be stdlib or transitive)
    missing_from_req = imports - required - STDLIB
    missing_from_req = {p for p in missing_from_req if p not in installed}
    
    # Requirements not imported anywhere (potential unused)
    unused_req = required - imports
    # Some packages are CLI tools or have different import names
    known_different_names = {
        'pyyaml': 'yaml',
        'beautifulsoup4': 'bs4',
        'python-dotenv': 'dotenv',
        'python-dateutil': 'dateutil',
        'scikit-learn': 'sklearn',
        'opencv-python': 'cv2',
        'pywin32': 'win32api',
        'pywebview': 'webview',
        'pywinpty': 'winpty',
    }
    for req_name, import_name in known_different_names.items():
        if req_name in unused_req and import_name in imports:
            unused_req.discard(req_name)
    
    # Installed but not in requirements (potential missing from requirements.txt)
    missing_from_req_file = installed - required - STDLIB
    
    print()
    if missing_from_req:
        print(f'⚠️  Imports potentially missing from requirements.txt: {sorted(missing_from_req)}')
    else:
        print('✅ All non-stdlib imports covered by requirements.txt')
    
    if unused_req:
        print(f'⚠️  Requirements potentially unused: {sorted(unused_req)}')
    else:
        print('✅ All requirements appear to be used')
    
    if missing_from_req_file:
        print(f'⚠️  Installed packages not in requirements.txt: {sorted(missing_from_req_file)}')
    else:
        print('✅ No extra installed packages')
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
