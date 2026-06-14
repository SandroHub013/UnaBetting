"""Loop runner scripts should stay portable across machines."""
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WINDOWS_ABSOLUTE_PATH = re.compile(r"[A-Za-z]:\\")


def _script(name: str) -> str:
    return (ROOT / "scripts" / "loops" / name).read_text(encoding="utf-8")


def test_loop_runner_scripts_do_not_pin_machine_specific_paths():
    for script in ("run_dev_loop_win.ps1", "run_loop.ps1", "run_dev_loop.sh"):
        text = _script(script)
        assert "G:\\tennis betting" not in text
        assert "C:\\Users\\Utente" not in text
        assert "/mnt/g/tennis" not in text
        assert not WINDOWS_ABSOLUTE_PATH.search(text)


def test_loop_runner_scripts_resolve_repo_from_script_location():
    for script in ("run_dev_loop_win.ps1", "run_loop.ps1"):
        text = _script(script)
        assert "$scriptRoot" in text
        assert "Resolve-Path" in text
        assert "Join-Path $scriptRoot '..\\.." in text


def test_dev_loop_scripts_reset_main_with_git_switch():
    for script in ("run_dev_loop_win.ps1", "run_dev_loop.sh"):
        text = _script(script)
        assert "git checkout" not in text
        assert "git switch" in text
