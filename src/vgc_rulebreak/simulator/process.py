"""Subprocess management for Pokemon Showdown simulate-battle."""

import os
import subprocess
from pathlib import Path
from typing import Any, Protocol


class BattleStream(Protocol):
    """Protocol for sending commands and receiving output from a battle simulator."""

    def send(self, command: str) -> None:
        """Send a single line command to the simulator."""
        ...

    def read_line(self, timeout: float = 5.0) -> str | None:
        """Read a single line from the simulator output."""
        ...

    def close(self) -> None:
        """Close simulator resources."""
        ...


class ShowdownProcess:
    """Manages a live pokemon-showdown simulate-battle subprocess."""

    DEFAULT_PATHS = (
        Path("/home/ubuntu/platform/src/oss/pokemon-showdown"),
        Path("./pokemon-showdown"),
    )

    def __init__(self, showdown_dir: Path | str | None = None) -> None:
        self.showdown_dir = self._resolve_showdown_dir(showdown_dir)
        self._process: subprocess.Popen[str] | None = None

    @classmethod
    def _resolve_showdown_dir(cls, custom_dir: Path | str | None) -> Path:
        if custom_dir is not None:
            candidate = Path(custom_dir)
            if candidate.exists():
                return candidate
            raise FileNotFoundError(f"Specified Showdown directory not found: {custom_dir}")

        env_path = os.environ.get("SHOWDOWN_PATH")
        if env_path:
            candidate = Path(env_path)
            if candidate.exists():
                return candidate

        for candidate in cls.DEFAULT_PATHS:
            if candidate.exists():
                return candidate

        raise FileNotFoundError(
            "Pokemon Showdown directory not found. Set SHOWDOWN_PATH or pass showdown_dir."
        )

    def start(self) -> None:
        """Spawn the pokemon-showdown simulate-battle child process."""
        if self._process is not None and self._process.poll() is None:
            return

        cmd = ["node", "pokemon-showdown", "simulate-battle"]
        self._process = subprocess.Popen(
            cmd,
            cwd=str(self.showdown_dir),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def send(self, command: str) -> None:
        """Send a command string to the subprocess stdin."""
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("Showdown process is not running. Call start() first.")
        clean = command.strip()
        self._process.stdin.write(f"{clean}\n")
        self._process.stdin.flush()

    def read_line(self, timeout: float = 5.0) -> str | None:
        """Read a single line from stdout."""
        if self._process is None or self._process.stdout is None:
            raise RuntimeError("Showdown process is not running. Call start() first.")
        line = self._process.stdout.readline()
        if not line:
            return None
        return line.rstrip("\r\n")

    def close(self) -> None:
        """Terminate the running subprocess."""
        if self._process is not None:
            try:
                if self._process.stdin:
                    self._process.stdin.close()
                self._process.terminate()
                self._process.wait(timeout=2.0)
            except Exception:
                self._process.kill()
            finally:
                self._process = None

    def __enter__(self) -> "ShowdownProcess":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
