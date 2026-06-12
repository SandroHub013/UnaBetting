"""Tests for the module-order audit script."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "audit" / "check_module_order.py"


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("check_module_order", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def audit():
    return _load_audit_module()


def test_module_order_script_exists():
    assert SCRIPT.is_file()


def test_audit_module_imports_cleanly(audit):
    for name in ("LAYERS", "ImportViolation", "check_file", "main"):
        assert hasattr(audit, name)


def test_no_layer_violations_in_src(audit, capsys):
    exit_code = audit.main([])
    captured = capsys.readouterr()
    assert exit_code == 0, "Module-order audit failed: " + captured.out
    assert "no layer violations" in captured.out


def test_layers_constant_matches_src_init(audit):
    audit_layers = set(audit.LAYERS.keys())
    init_file = (ROOT / "src" / "__init__.py").read_text()
    expected = {"data", "features", "models", "live", "betting", "dashboard", "ui"}
    assert audit_layers == expected
    for layer in expected:
        assert f'"{layer}"' in init_file or f"'{layer}'" in init_file


def test_pragma_allows_documented_cross_layer(audit, tmp_path, monkeypatch):
    fake_src = tmp_path / "src"
    (fake_src / "data").mkdir(parents=True)
    (fake_src / "models").mkdir(parents=True)
    (fake_src / "data" / "mod.py").write_text(
        "# pragma: allow_cross_layer data -> models
"
        "from src.models import x
"
    )
    monkeypatch.setattr(audit, "find_src_root", lambda _: fake_src)
    violations = audit.check_file(fake_src / "data" / "mod.py", fake_src)
    assert violations == []


def test_pragma_with_trailing_comment(audit, tmp_path, monkeypatch):
    fake_src = tmp_path / "src"
    (fake_src / "features").mkdir(parents=True)
    (fake_src / "betting").mkdir(parents=True)
    (fake_src / "features" / "mod.py").write_text(
        "# pragma: allow_cross_layer features -> betting  (see ADR-0006)
"
        "from src.betting import y
"
    )
    monkeypatch.setattr(audit, "find_src_root", lambda _: fake_src)
    violations = audit.check_file(fake_src / "features" / "mod.py", fake_src)
    assert violations == []


def test_unallowed_cross_layer_flagged(audit, tmp_path, monkeypatch):
    fake_src = tmp_path / "src"
    (fake_src / "data").mkdir(parents=True)
    (fake_src / "models").mkdir(parents=True)
    (fake_src / "data" / "mod.py").write_text(
        "from src.models import z  # bad -- no pragma
"
    )
    monkeypatch.setattr(audit, "find_src_root", lambda _: fake_src)
    violations = audit.check_file(fake_src / "data" / "mod.py", fake_src)
    assert len(violations) == 1
    v = violations[0]
    assert v.source_layer == "data"
    assert v.target_layer == "models"


def test_same_layer_import_allowed(audit, tmp_path, monkeypatch):
    fake_src = tmp_path / "src"
    (fake_src / "features").mkdir(parents=True)
    (fake_src / "features" / "a.py").write_text("from src.features.b import x
")
    (fake_src / "features" / "b.py").write_text("X = 1
")
    monkeypatch.setattr(audit, "find_src_root", lambda _: fake_src)
    violations = audit.check_file(fake_src / "features" / "a.py", fake_src)
    assert violations == []


def test_json_output_is_valid_json(audit, capsys):
    import json
    audit.main(["--json"])
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert isinstance(parsed, list)
    assert parsed == []
