"""Dashboard terminal command construction."""

from src.dashboard import config as dash_config
from src.dashboard.terminal import _terminal_command


def test_vibe_agent_uses_current_project_root(monkeypatch, tmp_path):
    project_root = tmp_path / "contributor's clone"
    monkeypatch.setattr(dash_config, "PROJECT_ROOT", project_root)

    command = _terminal_command("wsl", "codex")

    assert command[:3] == ["wsl.exe", "--cd", str(project_root.resolve())]
    assert command[3:6] == ["-e", "bash", "-lc"]
    assert command[6] == "tmux new-session -A -s vibe-codex codex"


def test_terminal_command_rejects_unknown_agent():
    assert _terminal_command("wsl", "not-installed") is None


def test_terminal_command_uses_shell_whitelist():
    assert _terminal_command("powershell") == dash_config.SHELLS["powershell"]
    assert _terminal_command("cmd") is None
