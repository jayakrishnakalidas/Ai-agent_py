from __future__ import annotations

from pathlib import Path


class ToolError(Exception):
    pass


class FileTools:
    MAX_READ = 250_000

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()

    def _path(self, raw: str | None) -> Path:
        if not raw:
            raw = "."
        candidate = (self.workspace / raw).resolve()
        try:
            candidate.relative_to(self.workspace)
        except ValueError as error:
            raise ToolError("Path is outside the workspace.") from error
        return candidate

    def list_files(self, path: str = ".") -> str:
        target = self._path(path)
        if not target.is_dir():
            raise ToolError(f"Not a directory: {path}")
        entries = sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
        return "\n".join(("[DIR] " if item.is_dir() else "[FILE] ") + str(item.relative_to(self.workspace))
                         for item in entries) or "(empty folder)"

    def read_file(self, path: str) -> str:
        target = self._path(path)
        if not target.is_file():
            raise ToolError(f"Not a file: {path}")
        if target.stat().st_size > self.MAX_READ:
            raise ToolError(f"File exceeds {self.MAX_READ} byte read limit.")
        try:
            return target.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise ToolError("Only UTF-8 text files can be read.") from error

    def write_file(self, path: str, content: str) -> str:
        target = self._path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} characters to {target.relative_to(self.workspace)}."

    def create_folder(self, path: str) -> str:
        target = self._path(path)
        target.mkdir(parents=True, exist_ok=True)
        return f"Folder ready: {target.relative_to(self.workspace)}."
