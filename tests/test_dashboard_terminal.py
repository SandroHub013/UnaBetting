"""Dashboard terminal command construction and POSIX PTY behavior."""
import os
import sys

import pytest

from src.dashboard import config as dash_config
from src.dashboard import terminal
from src.dashboard.pty_process import PosixPtyProcess


_terminal_command = terminal._terminal_command


def test_windows_vibe_agent_uses_current_project_root(monkeypatch, tmp_path):
    project_root = tmp_path / "contributor's clone"
    monkeypatch.setattr(dash_config, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(terminal.sys, "platform", "win32")

    command = _terminal_command("wsl", "codex")

    assert command[:3] == ["wsl.exe", "--cd", str(project_root.resolve())]
    assert command[3:6] == ["-e", "bash", "-lc"]
    assert command[6] == "tmux new-session -A -s vibe-codex codex"


def test_posix_vibe_agent_uses_native_tmux(monkeypatch):
    monkeypatch.setattr(terminal.sys, "platform", "linux")

    assert _terminal_command("shell", "codex") == [
        "tmux", "new-session", "-A", "-s", "vibe-codex", "codex"]


def test_terminal_command_rejects_unknown_agent():
    assert _terminal_command("wsl", "not-installed") is None


def test_terminal_command_uses_shell_whitelist():
    assert _terminal_command(dash_config.DEFAULT_SHELL) == \
        dash_config.SHELLS[dash_config.DEFAULT_SHELL]
    assert _terminal_command("cmd") is None


@pytest.mark.skipif(os.name == "nt", reason="requires a POSIX PTY")
def test_posix_pty_streams_input_output_and_uses_cwd(tmp_path):
    script = """
import fcntl
import os
import struct
import sys
import termios

print("cwd=" + os.getcwd(), flush=True)
line = sys.stdin.readline().strip()
rows, cols, _, _ = struct.unpack(
    "HHHH", fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, b"\\0" * 8))
print(f"echo={line} size={rows}x{cols}", flush=True)
"""
    process = PosixPtyProcess.spawn(
        [sys.executable, "-c", script], cwd=tmp_path, dimensions=(24, 80))
    try:
        start = process.read()
        assert f"cwd={tmp_path}" in start

        process.setwinsize(32, 100)
        process.write("hello\n")
        output = ""
        while "echo=hello size=32x100" not in output:
            output += process.read()
        assert "echo=hello size=32x100" in output
    finally:
        process.terminate(force=True)
