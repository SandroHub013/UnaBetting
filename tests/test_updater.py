"""Security tests for the in-app updater's bundle extraction.

The runtime bundle is downloaded from GitHub Releases and unpacked into the
writable DATA_ROOT. These tests pin the defenses: zip-slip / absolute-path
containment, sha256 manifest verification, all-or-nothing extraction, and the
never-overwrite list for user data.
"""
import hashlib
import io
import json
import urllib.request
import zipfile

import pytest
import yaml

import src.dashboard.data_api as data_api
from src.dashboard.data_api import _extract_runtime_bundle

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# Throwaway signing keypair; the extractor's verification key is monkeypatched to this
# public key (autouse), so bundles signed here verify exactly like production ones.
_TEST_PRIV = ed25519.Ed25519PrivateKey.generate()
_TEST_PUB_PEM = _TEST_PRIV.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)


@pytest.fixture(autouse=True)
def _use_test_pubkey(monkeypatch):
    monkeypatch.setattr(data_api, "_UPDATER_PUBKEY", _TEST_PUB_PEM, raising=False)


def _sign(manifest):
    import base64
    payload = json.dumps(manifest, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.b64encode(_TEST_PRIV.sign(payload)).decode()


def _make_bundle(path, files, manifest_files=None, with_manifest=True, signed=True):
    """Build a zip at `path` with {member: bytes}; manifest defaults to correct hashes."""
    if manifest_files is None:
        manifest_files = [
            {"path": m, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
            for m, b in files.items()
        ]
    with zipfile.ZipFile(path, "w") as zf:
        for member, blob in files.items():
            zf.writestr(member, blob)
        if with_manifest:
            manifest = {"name": "UnaBetting", "version": "9.9.9", "files": manifest_files}
            if signed:
                manifest["signature"] = _sign(manifest)
            zf.writestr("manifest.json", json.dumps(manifest))


def _yaml_bytes(value):
    return yaml.safe_dump(value, sort_keys=False).encode("utf-8")


def test_valid_bundle_extracts(tmp_path):
    bundle = tmp_path / "bundle.zip"
    root = tmp_path / "data_root"
    _make_bundle(bundle, {"models/atp_metrics.json": b'{"ok": 1}',
                          "config/config.yaml": b"a: 1\n"})
    n = _extract_runtime_bundle(bundle, root)
    assert n == 2
    assert (root / "models/atp_metrics.json").read_bytes() == b'{"ok": 1}'
    assert (root / "config/config.yaml").read_bytes() == b"a: 1\n"
    assert (root / "config/.runtime-default.yaml").read_bytes() == b"a: 1\n"


def test_config_updates_preserve_overrides_and_advance_defaults(tmp_path):
    root = tmp_path / "data_root"
    config_dir = root / "config"
    config_dir.mkdir(parents=True)
    old_defaults = {
        "model": {"threshold": 10, "family": "baseline"},
        "betting": {"min_edge": 0.03},
    }
    current = {
        "model": {"threshold": 10, "family": "custom-family"},
        "betting": {"min_edge": 0.07},
        "user_only": {"enabled": True},
    }
    baseline = tmp_path / "bundled-default.yaml"
    baseline.write_bytes(_yaml_bytes(old_defaults))
    current_blob = _yaml_bytes(current)
    (config_dir / "config.yaml").write_bytes(current_blob)

    v2_defaults = {
        "model": {"threshold": 20, "family": "v2-default", "calibrated": True},
        "betting": {"min_edge": 0.04},
        "new_section": {"enabled": True},
    }
    v2_blob = _yaml_bytes(v2_defaults)
    v2_bundle = tmp_path / "v2.zip"
    _make_bundle(v2_bundle, {
        "models/version.txt": b"v2",
        "config/config.yaml": v2_blob,
    })

    assert _extract_runtime_bundle(v2_bundle, root, baseline_config=baseline) == 2
    merged_v2 = yaml.safe_load((config_dir / "config.yaml").read_text(encoding="utf-8"))
    assert merged_v2 == {
        "model": {"threshold": 20, "family": "custom-family", "calibrated": True},
        "betting": {"min_edge": 0.07},
        "new_section": {"enabled": True},
        "user_only": {"enabled": True},
    }
    assert (config_dir / "config.yaml.bak").read_bytes() == current_blob
    assert (config_dir / ".runtime-default.yaml").read_bytes() == v2_blob

    v3_defaults = {
        "model": {"threshold": 30, "family": "v3-default", "calibrated": False},
        "betting": {"min_edge": 0.05},
    }
    v3_blob = _yaml_bytes(v3_defaults)
    v3_bundle = tmp_path / "v3.zip"
    _make_bundle(v3_bundle, {"config/config.yaml": v3_blob})

    assert _extract_runtime_bundle(v3_bundle, root, baseline_config=baseline) == 1
    merged_v3 = yaml.safe_load((config_dir / "config.yaml").read_text(encoding="utf-8"))
    assert merged_v3 == {
        "model": {"threshold": 30, "family": "custom-family", "calibrated": False},
        "betting": {"min_edge": 0.07},
        "user_only": {"enabled": True},
    }
    assert (config_dir / ".runtime-default.yaml").read_bytes() == v3_blob


def test_invalid_current_config_rejects_bundle_before_any_write(tmp_path):
    root = tmp_path / "data_root"
    config_dir = root / "config"
    config_dir.mkdir(parents=True)
    current = b"model: [unclosed\n"
    (config_dir / "config.yaml").write_bytes(current)
    bundle = tmp_path / "bundle.zip"
    _make_bundle(bundle, {
        "models/new.pkl": b"model",
        "config/config.yaml": b"model:\n  threshold: 20\n",
    })

    with pytest.raises(ValueError, match="current config"):
        _extract_runtime_bundle(bundle, root)

    assert (config_dir / "config.yaml").read_bytes() == current
    assert not (config_dir / "config.yaml.bak").exists()
    assert not (config_dir / ".runtime-default.yaml").exists()
    assert not (root / "models/new.pkl").exists()


def test_traversal_member_rejected(tmp_path):
    bundle = tmp_path / "bundle.zip"
    root = tmp_path / "data_root"
    evil = b"evil"
    _make_bundle(bundle, {"../outside.txt": evil})
    with pytest.raises(ValueError, match="unsafe path"):
        _extract_runtime_bundle(bundle, root)
    assert not (tmp_path / "outside.txt").exists()


def test_absolute_member_rejected(tmp_path):
    bundle = tmp_path / "bundle.zip"
    root = tmp_path / "data_root"
    target = tmp_path / "abs_target.txt"
    _make_bundle(bundle, {str(target): b"evil"})
    with pytest.raises(ValueError, match="unsafe path"):
        _extract_runtime_bundle(bundle, root)
    assert not target.exists()


def test_missing_manifest_rejected(tmp_path):
    bundle = tmp_path / "bundle.zip"
    _make_bundle(bundle, {"models/x.txt": b"x"}, with_manifest=False)
    with pytest.raises(ValueError, match="manifest"):
        _extract_runtime_bundle(bundle, tmp_path / "data_root")


def test_not_a_zip_rejected(tmp_path):
    bogus = tmp_path / "bundle.zip"
    bogus.write_bytes(b"this is not a zip file")
    with pytest.raises(ValueError, match="valid zip"):
        _extract_runtime_bundle(bogus, tmp_path / "data_root")


def test_malformed_manifest_entry_rejected(tmp_path):
    """A manifest entry missing sha256/bytes is a ValueError, not a raw KeyError."""
    bundle = tmp_path / "bundle.zip"
    _make_bundle(bundle, {"models/x.txt": b"x"},
                 manifest_files=[{"path": "models/x.txt"}])  # no sha256/bytes
    with pytest.raises(ValueError, match="malformed manifest"):
        _extract_runtime_bundle(bundle, tmp_path / "data_root")


def test_unsigned_manifest_rejected(tmp_path):
    """A manifest without an Ed25519 signature is rejected before extraction."""
    bundle = tmp_path / "bundle.zip"
    _make_bundle(bundle, {"models/x.txt": b"x"}, signed=False)
    with pytest.raises(ValueError, match="unsigned bundle"):
        _extract_runtime_bundle(bundle, tmp_path / "data_root")
    assert not (tmp_path / "data_root" / "models" / "x.txt").exists()


def test_manifest_lists_file_absent_from_bundle_rejected(tmp_path):
    """Truncated bundle: manifest claims a file the zip doesn't contain -> reject
    (else a partial/mixed-version install would slip through and bump VERSION)."""
    bundle = tmp_path / "bundle.zip"
    present = b"present"
    _make_bundle(bundle, {"models/a.txt": present},
                 manifest_files=[
                     {"path": "models/a.txt", "bytes": len(present),
                      "sha256": hashlib.sha256(present).hexdigest()},
                     {"path": "models/missing.txt", "bytes": 3, "sha256": "00"},
                 ])
    with pytest.raises(ValueError, match="absent from bundle"):
        _extract_runtime_bundle(bundle, tmp_path / "data_root")


def test_empty_bundle_rejected(tmp_path):
    """A manifest-only zip installs nothing -> reject (don't report a 0-file 'update')."""
    bundle = tmp_path / "bundle.zip"
    _make_bundle(bundle, {}, manifest_files=[])
    with pytest.raises(ValueError, match="no installable files"):
        _extract_runtime_bundle(bundle, tmp_path / "data_root")


def test_size_mismatch_rejected(tmp_path):
    bundle = tmp_path / "bundle.zip"
    blob = b"hello"
    _make_bundle(bundle, {"models/x.txt": blob},
                 manifest_files=[{"path": "models/x.txt", "bytes": 999,
                                  "sha256": hashlib.sha256(blob).hexdigest()}])
    with pytest.raises(ValueError, match="size mismatch"):
        _extract_runtime_bundle(bundle, tmp_path / "data_root")


def test_file_not_in_manifest_rejected(tmp_path):
    bundle = tmp_path / "bundle.zip"
    _make_bundle(bundle, {"models/x.txt": b"x", "models/smuggled.txt": b"y"},
                 manifest_files=[{"path": "models/x.txt", "bytes": 1,
                                  "sha256": hashlib.sha256(b"x").hexdigest()}])
    with pytest.raises(ValueError, match="not in manifest"):
        _extract_runtime_bundle(bundle, tmp_path / "data_root")


def test_hash_mismatch_rejected_and_nothing_written(tmp_path):
    """Validate-all-then-write: a bad member late in the zip must not leave the
    earlier (valid) members on disk."""
    bundle = tmp_path / "bundle.zip"
    root = tmp_path / "data_root"
    good, bad = b"good", b"tampered"
    _make_bundle(bundle, {"models/a.txt": good, "models/b.txt": bad},
                 manifest_files=[
                     {"path": "models/a.txt", "bytes": len(good),
                      "sha256": hashlib.sha256(good).hexdigest()},
                     {"path": "models/b.txt", "bytes": len(bad),  # size ok; hash wrong
                      "sha256": hashlib.sha256(b"other").hexdigest()},
                 ])
    with pytest.raises(ValueError, match="sha256 mismatch"):
        _extract_runtime_bundle(bundle, root)
    assert not (root / "models/a.txt").exists(), "partial extraction occurred"


def test_user_data_never_overwritten(tmp_path):
    bundle = tmp_path / "bundle.zip"
    root = tmp_path / "data_root"
    (root / "data").mkdir(parents=True)
    db = root / "data" / "betanalytix.db"
    db.write_bytes(b"my bets")
    _make_bundle(bundle, {"data/betanalytix.db": b"clobbered",
                          "models/ok.txt": b"fine"})
    n = _extract_runtime_bundle(bundle, root)
    assert n == 1  # only models/ok.txt
    assert db.read_bytes() == b"my bets"


def _bundle_bytes(files):
    buf = io.BytesIO()
    _make_bundle(buf, files)
    return buf.getvalue()


def _patch_frozen_update(monkeypatch, tmp_path, bundle_bytes):
    """Wire update_apply's FROZEN path to a fake release serving bundle_bytes."""
    import src.runtime_paths as rp
    monkeypatch.setattr(rp, "FROZEN", True, raising=False)
    monkeypatch.setattr(rp, "DATA_ROOT", tmp_path, raising=False)
    monkeypatch.setattr(rp, "app_version", lambda: "0.1.0", raising=False)
    monkeypatch.setattr(data_api, "_latest_release", lambda: {
        "tag_name": "v9.9.9",
        "assets": [{"name": "UnaBetting-runtime-v9.9.9.zip",
                    "browser_download_url": "https://example.invalid/b.zip"}],
    })
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: io.BytesIO(bundle_bytes))


def test_update_apply_happy_path_writes_version(tmp_path, monkeypatch):
    _patch_frozen_update(monkeypatch, tmp_path,
                         _bundle_bytes({"models/ok.txt": b"fine"}))
    res = data_api.update_apply()
    assert res["ok"] and res["updated"] and res["version"] == "v9.9.9"
    assert (tmp_path / "models" / "ok.txt").read_bytes() == b"fine"
    assert (tmp_path / "VERSION").read_text().strip() == "9.9.9"


def test_update_apply_rejects_bad_bundle_without_writing_version(tmp_path, monkeypatch):
    _patch_frozen_update(monkeypatch, tmp_path,
                         _bundle_bytes({"../escape.txt": b"evil"}))
    res = data_api.update_apply()
    assert res.status_code == 502  # JSONResponse from _err
    assert json.loads(bytes(res.body))["error"] == "bundle_rejected"
    assert not (tmp_path / "VERSION").exists()
    assert not (tmp_path.parent / "escape.txt").exists()


def test_protected_match_is_case_and_separator_insensitive(tmp_path):
    """Windows/macOS are case-insensitive: a bundle can't clobber the portfolio db
    by varying case (`Betanalytix.db`) or separators (`data\\live\\...`)."""
    bundle = tmp_path / "bundle.zip"
    root = tmp_path / "data_root"
    (root / "data").mkdir(parents=True)
    db = root / "data" / "betanalytix.db"
    db.write_bytes(b"my bets")
    _make_bundle(bundle, {"data/Betanalytix.DB": b"clobbered",
                          "data/live/predictions.json": b"x",
                          "models/ok.txt": b"fine"})
    n = _extract_runtime_bundle(bundle, root)
    assert n == 1  # only models/ok.txt; the two protected variants are skipped
    assert db.read_bytes() == b"my bets"
    assert not (root / "data" / "live" / "predictions.json").exists()
