"""Small cross-platform PTY adapter for dashboard terminals."""
import os
import shlex
import signal
from pathlib import Path
from typing import Sequence


def _command_argv(command: str | Sequence[str]) -> list[str]:
    argv = shlex.split(command) if isinstance(command, str) else list(command)
    if not argv:
        raise ValueError("terminal command cannot be empty")
    return argv


class PosixPtyProcess:
    """Minimal pywinpty-compatible wrapper around a POSIX pseudo-terminal."""

    def __init__(self, pid: int, fd: int):
        self.pid = pid
        self.fd = fd
        self._closed = False

    @classmethod
    def spawn(
        cls,
        command: str | Sequence[str],
        cwd: str | os.PathLike[str],
        dimensions: tuple[int, int] = (30, 120),
    ) -> "PosixPtyProcess":
        if os.name == "nt":
            raise OSError("POSIX terminals are not available on Windows")

        import pty

        argv = _command_argv(command)
        pid, fd = pty.fork()
        if pid == 0:
            try:
                os.chdir(Path(cwd))
                os.execvp(argv[0], argv)
            except BaseException as exc:
                message = f"[dashboard] unable to start {argv[0]!r}: {exc}\n"
                os.write(2, message.encode("utf-8", errors="replace"))
                os._exit(127)

        process = cls(pid, fd)
        try:
            process.setwinsize(*dimensions)
        except Exception:
            process.terminate(force=True)
            raise
        return process

    def read(self) -> str:
        return os.read(self.fd, 65536).decode("utf-8", errors="replace")

    def write(self, data: str) -> None:
        if data:
            os.write(self.fd, data.encode("utf-8"))

    def setwinsize(self, rows: int, cols: int) -> None:
        import fcntl
        import struct
        import termios

        size = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, size)

    def terminate(self, force: bool = False) -> None:
        if self._closed:
            return

        sig = signal.SIGKILL if force else signal.SIGTERM
        try:
            os.killpg(self.pid, sig)
        except ProcessLookupError:
            pass
        except OSError:
            try:
                os.kill(self.pid, sig)
            except ProcessLookupError:
                pass
        finally:
            self._closed = True
            try:
                os.close(self.fd)
            except OSError:
                pass

        try:
            os.waitpid(self.pid, 0)
        except ChildProcessError:
            pass


def spawn_terminal(
    command: str | Sequence[str],
    cwd: str | os.PathLike[str],
    dimensions: tuple[int, int] = (30, 120),
):
    """Spawn a terminal using ConPTY on Windows and a native PTY elsewhere."""
    if os.name == "nt":
        from winpty import PtyProcess

        return PtyProcess.spawn(command, cwd=str(cwd), dimensions=dimensions)
    return PosixPtyProcess.spawn(command, cwd=cwd, dimensions=dimensions)
