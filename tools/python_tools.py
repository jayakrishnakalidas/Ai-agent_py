from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .file_tools import ToolError


class PythonTools:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    def run(self, code: str) -> str:
        if not code.strip():
            raise ToolError("No Python code was supplied.")
        try:
            completed = subprocess.run([sys.executable, "-I", "-c", code], cwd=self.workspace,
                capture_output=True, text=True, timeout=20, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired as error:
            raise ToolError("Python execution exceeded the 20-second limit.") from error
        output = (completed.stdout + completed.stderr).strip()
        return output or f"Python completed (exit code {completed.returncode})."
