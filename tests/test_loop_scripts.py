"""Loop runner scripts should stay portable across machines."""
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOOP_ROOT = ROOT / "scripts" / "loops"
WINDOWS_ABSOLUTE_PATH = re.compile(r"[A-Za-z]:\\")


def _loop_file(name: str) -> str:
    return (LOOP_ROOT / name).read_text(encoding="utf-8")


def _loop_docs() -> list[Path]:
    return sorted(LOOP_ROOT.glob("*.md"))


def test_loop_runner_scripts_do_not_pin_user_specific_paths():
    for script in ("run_dev_loop_win.ps1", "run_loop.ps1"):
        text = _loop_file(script)
        assert "G:\\tennis betting" not in text
        assert "C:\\Users\\Utente" not in text
        assert "/mnt/g/tennis" not in text
        assert not WINDOWS_ABSOLUTE_PATH.search(text)


def test_loop_docs_do_not_pin_user_specific_paths():
    for path in _loop_docs():
        text = path.read_text(encoding="utf-8")
        assert "G:\\tennis betting" not in text
        assert "C:\\Users\\Utente" not in text
        assert not WINDOWS_ABSOLUTE_PATH.search(text)


def test_loop_shell_runner_does_not_pin_wsl_specific_paths():
    text = _loop_file("run_dev_loop.sh")
    assert "/mnt/g/tennis" not in text
    assert "C:\\Users\\Utente" not in text
    assert not WINDOWS_ABSOLUTE_PATH.search(text)


def test_loop_runner_scripts_resolve_repo_from_script_location():
    for script in ("run_dev_loop_win.ps1", "run_loop.ps1"):
        text = _loop_file(script)
        assert "$scriptRoot" in text
        assert "Resolve-Path" in text
        assert "Join-Path $scriptRoot '..\\.." in text


def test_dev_loop_scripts_reset_main_with_git_switch():
    for script in ("run_dev_loop_win.ps1", "run_dev_loop.sh"):
        text = _loop_file(script)
        assert "git checkout" not in text
        assert "git switch" in text


def test_windows_dev_loop_preserves_opencode_exit_code():
    text = _loop_file("run_dev_loop_win.ps1")
    assert "$opencodeExit = $LASTEXITCODE" in text
    assert "exit $opencodeExit" in text
