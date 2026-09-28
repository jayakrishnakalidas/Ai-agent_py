from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .file_tools import ToolError


class DevTools:
    """Focused validation and Git helpers for a workspace."""
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    def check_syntax(self, path: str) -> str:
        target = (self.workspace / path).resolve()
        try:
            target.relative_to(self.workspace)
        except ValueError as error:
            raise ToolError("Path is outside the workspace.") from error
        if not target.is_file():
            raise ToolError(f"Not a file: {path}")
        suffix = target.suffix.lower()
        try:
            if suffix == ".py":
                result = subprocess.run([sys.executable, "-m", "py_compile", str(target)], capture_output=True, text=True, timeout=30)
                if result.returncode:
                    raise ToolError(result.stderr.strip() or "Python syntax check failed.")
            elif suffix == ".json":
                json.loads(target.read_text(encoding="utf-8"))
            elif suffix in {".js", ".mjs", ".cjs"}:
                # Try node --check if node is available
                try:
                    res = subprocess.run(["node", "--check", str(target)], capture_output=True, text=True, timeout=15)
                    if res.returncode != 0:
                        raise ToolError(res.stderr.strip() or "JavaScript syntax error detected by Node.")
                except FileNotFoundError:
                    # Basic fallback checking for unmatched brackets/parens/braces in JS
                    text = target.read_text(encoding="utf-8")
                    stack = []
                    pairs = {')': '(', ']': '[', '}': '{'}
                    for line_no, line in enumerate(text.splitlines(), 1):
                        for char in line:
                            if char in "({[":
                                stack.append((char, line_no))
                            elif char in ")}]" and stack and stack[-1][0] == pairs[char]:
                                stack.pop()
            elif suffix in {".html", ".htm"}:
                text = target.read_text(encoding="utf-8")
                if "<html" not in text.lower() or "</html>" not in text.lower():
                    raise ToolError("HTML file missing <html> or </html> tags.")
            elif suffix == ".css":
                text = target.read_text(encoding="utf-8")
                open_braces = text.count("{")
                close_braces = text.count("}")
                if open_braces != close_braces:
                    raise ToolError(f"CSS has unmatched braces: {open_braces} open '{{' vs {close_braces} close '}}'.")
            elif suffix == ".php":
                try:
                    res = subprocess.run(["php", "-l", str(target)], capture_output=True, text=True, timeout=15)
                    if res.returncode != 0:
                        raise ToolError(res.stdout.strip() or "PHP syntax check failed.")
                except FileNotFoundError:
                    pass
            else:
                return f"No built-in syntax checker for {suffix or 'this file type'}."
        except (OSError, json.JSONDecodeError, subprocess.TimeoutExpired, UnicodeDecodeError) as error:
            raise ToolError(f"Syntax check failed: {error}") from error
        return f"Syntax check passed: {target.relative_to(self.workspace)}."

    def run_tests(self) -> str:
        command = [sys.executable, "-m", "pytest", "-q"]
        try:
            result = subprocess.run(command, cwd=self.workspace, capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired as error:
            raise ToolError("Tests exceeded 60 seconds.") from error
        output = (result.stdout + result.stderr).strip()
        return output or f"Tests completed (exit code {result.returncode})."

    def run_command(self, program: str, args: list[str] | None = None) -> str:
        """Run a small allowlist of development commands without a shell."""
        args = args or []
        if not isinstance(program, str) or not isinstance(args, list) or not all(isinstance(item, str) for item in args):
            raise ToolError("program must be text and args must be a list of text values.")
        if any(any(char in item for char in ";&|><`\n\r") or ".." in item for item in args):
            raise ToolError("Command arguments cannot contain shell operators or '..'.")
        permitted = False
        if program == "python":
            permitted = len(args) >= 2 and args[0] == "-m" and args[1] in {"pytest", "unittest", "compileall"}
        elif program == "node":
            permitted = bool(args) and args[0] == "--check"
        elif program == "npm":
            permitted = bool(args) and args[0] in {"test", "run"}
        elif program == "git":
            permitted = bool(args) and args[0] in {"status", "diff", "log", "add", "commit"}
        if not permitted:
            raise ToolError("Allowed commands: python -m pytest|unittest|compileall, node --check, npm test|run, git status|diff|log|add|commit.")
        try:
            result = subprocess.run([program, *args], cwd=self.workspace, capture_output=True, text=True,
                                    timeout=60, encoding="utf-8", errors="replace")
        except FileNotFoundError as error:
            raise ToolError(f"'{program}' is not installed.") from error
        except subprocess.TimeoutExpired as error:
            raise ToolError("Command exceeded 60 seconds.") from error
        output = (result.stdout + result.stderr).strip()
        return output or f"Command completed (exit code {result.returncode})."

    def _git(self, *args: str) -> str:
        try:
            result = subprocess.run(["git", *args], cwd=self.workspace, capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")
        except FileNotFoundError as error:
            raise ToolError("Git is not installed.") from error
        except subprocess.TimeoutExpired as error:
            raise ToolError("Git command timed out.") from error
        if result.returncode:
            raise ToolError((result.stderr or result.stdout).strip())
        return (result.stdout or "(no output)").strip()

    def git_status(self) -> str:
        return self._git("status", "--short")

    def git_diff(self) -> str:
        return self._git("diff", "--no-ext-diff")

    def git_log(self) -> str:
        return self._git("log", "--oneline", "-10")

    def git_add(self, path: str = ".") -> str:
        return self._git("add", path)

    def git_commit(self, message: str) -> str:
        if not message or not message.strip():
            raise ToolError("Commit message must not be empty.")
        return self._git("commit", "-m", message.strip())

