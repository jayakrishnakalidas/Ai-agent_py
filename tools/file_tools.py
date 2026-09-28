from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path


class ToolError(Exception):
    pass


class FileTools:
    """Workspace-only text and project-inspection tools with automatic backups."""
    MAX_READ = 250_000
    MAX_SEARCH_FILE = 1_000_000
    SKIP_DIRS = {".git", ".agent", ".agent_backups", "node_modules", "__pycache__"}

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()

    def _path(self, raw: str | None) -> Path:
        if not raw:
            raw = "."
        if not isinstance(raw, str):
            raise ToolError("Path must be a string.")
        candidate = (self.workspace / raw).resolve()
        try:
            candidate.relative_to(self.workspace)
        except ValueError as error:
            raise ToolError("Path is outside the workspace.") from error
        return candidate

    def _backup(self, target: Path) -> None:
        if not target.is_file():
            return
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
        destination = self.workspace / ".agent_backups" / stamp / target.relative_to(self.workspace)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, destination)

    def _read_text(self, target: Path) -> str:
        if not target.is_file():
            raise ToolError(f"Not a file: {target.relative_to(self.workspace)}")
        if target.stat().st_size > self.MAX_READ:
            raise ToolError(f"File exceeds {self.MAX_READ} byte read limit. Search it or read a smaller section.")
        try:
            return target.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise ToolError("Only UTF-8 text files can be read or edited.") from error

    def list_files(self, path: str = ".") -> str:
        target = self._path(path)
        if not target.is_dir():
            raise ToolError(f"Not a directory: {path}")
        entries = sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
        return "\n".join(("[DIR] " if item.is_dir() else "[FILE] ") + str(item.relative_to(self.workspace))
                         for item in entries) or "(empty folder)"

    def read_file(self, path: str, start_line: int | None = None, end_line: int | None = None) -> str:
        text = self._read_text(self._path(path))
        if start_line is not None or end_line is not None:
            lines = text.splitlines()
            total = len(lines)
            start = max(1, start_line) if start_line is not None else 1
            end = min(total, end_line) if end_line is not None else total
            if start > total:
                raise ToolError(f"start_line ({start}) exceeds total lines ({total}).")
            sliced = lines[start - 1:end]
            return f"--- Lines {start} to {end} of {total} in {path} ---\n" + "\n".join(
                f"{i:4d} | {line}" for i, line in enumerate(sliced, start=start)
            )
        return text

    def list_backups(self, path: str | None = None) -> str:
        backup_root = self.workspace / ".agent_backups"
        if not backup_root.exists():
            return "No backups exist yet."
        target_rel = Path(path).as_posix() if path else None
        matches: list[str] = []
        for stamp_dir in sorted(backup_root.iterdir(), reverse=True):
            if not stamp_dir.is_dir():
                continue
            for file in stamp_dir.rglob("*"):
                if file.is_file():
                    rel = file.relative_to(stamp_dir).as_posix()
                    if target_rel is None or rel == target_rel:
                        matches.append(f"[{stamp_dir.name}] {rel} ({file.stat().st_size} bytes)")
        return "\n".join(matches[:50]) or (f"No backups found for '{path}'." if path else "No backups found.")

    def restore_backup(self, path: str, backup_stamp: str | None = None) -> str:
        target = self._path(path)
        backup_root = self.workspace / ".agent_backups"
        if not backup_root.exists():
            raise ToolError("No backup history exists.")
        target_rel = target.relative_to(self.workspace)
        matched_file: Path | None = None
        matched_stamp: str = ""
        if backup_stamp:
            stamp_dir = backup_root / backup_stamp
            cand = stamp_dir / target_rel
            if cand.is_file():
                matched_file = cand
                matched_stamp = backup_stamp
        else:
            for stamp_dir in sorted(backup_root.iterdir(), reverse=True):
                cand = stamp_dir / target_rel
                if cand.is_file():
                    matched_file = cand
                    matched_stamp = stamp_dir.name
                    break
        if not matched_file:
            raise ToolError(f"No backup found for '{path}'" + (f" at stamp '{backup_stamp}'" if backup_stamp else "."))
        self._backup(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(matched_file, target)
        return f"Restored {target_rel} from backup snapshot [{matched_stamp}]."


    def write_file(self, path: str, content: str) -> str:
        if not isinstance(content, str):
            raise ToolError("File content must be text.")
        target = self._path(path)
        self._backup(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} characters to {target.relative_to(self.workspace)}."

    def create_folder(self, path: str) -> str:
        target = self._path(path)
        target.mkdir(parents=True, exist_ok=True)
        return f"Folder ready: {target.relative_to(self.workspace)}."

    def delete_file(self, path: str) -> str:
        target = self._path(path)
        if not target.is_file():
            raise ToolError(f"Not a file: {path}")
        self._backup(target)
        target.unlink()
        return f"Deleted {target.relative_to(self.workspace)}; a backup was saved."

    def replace_text(self, path: str, old: str, new: str, count: int = 1) -> str:
        if not old:
            raise ToolError("'old' text must not be empty.")
        if not isinstance(new, str) or not isinstance(count, int) or count < 1:
            raise ToolError("'new' must be text and 'count' must be at least 1.")
        target = self._path(path); content = self._read_text(target)
        occurrences = content.count(old)
        if occurrences == 0:
            raise ToolError("The exact old text was not found; read the file and retry with matching text.")
        self._backup(target)
        changed = min(count, occurrences)
        target.write_text(content.replace(old, new, changed), encoding="utf-8")
        return f"Replaced {changed} occurrence(s) in {target.relative_to(self.workspace)}."

    def insert_text(self, path: str, marker: str, text: str, position: str = "after") -> str:
        if position not in {"before", "after"} or not marker:
            raise ToolError("position must be 'before' or 'after', and marker must not be empty.")
        target = self._path(path); content = self._read_text(target); index = content.find(marker)
        if index < 0:
            raise ToolError("Marker text was not found; read the file and retry with matching text.")
        index = index if position == "before" else index + len(marker)
        self._backup(target)
        target.write_text(content[:index] + text + content[index:], encoding="utf-8")
        return f"Inserted text {position} the marker in {target.relative_to(self.workspace)}."

    def delete_text(self, path: str, text: str, count: int = 1) -> str:
        return self.replace_text(path, text, "", count)

    def patch_file(self, path: str, old: str, new: str) -> str:
        """A safe exact-text patch; the old block must exist before it is changed."""
        return self.replace_text(path, old, new, 1)

    def search_files(self, query: str, path: str = ".", max_results: int = 50) -> str:
        if not query:
            raise ToolError("Search query must not be empty.")
        if not isinstance(max_results, int) or not 1 <= max_results <= 200:
            raise ToolError("max_results must be between 1 and 200.")
        root = self._path(path)
        if not root.is_dir():
            raise ToolError(f"Not a directory: {path}")
        results: list[str] = []
        for file in root.rglob("*"):
            if any(part in self.SKIP_DIRS for part in file.parts) or not file.is_file():
                continue
            try:
                if file.stat().st_size > self.MAX_SEARCH_FILE:
                    continue
                for number, line in enumerate(file.read_text(encoding="utf-8").splitlines(), 1):
                    if query.lower() in line.lower():
                        results.append(f"{file.relative_to(self.workspace)}:{number}: {line.strip()[:300]}")
                        if len(results) >= max_results:
                            return "\n".join(results) + "\n[results limited]"
            except (OSError, UnicodeDecodeError):
                continue
        return "\n".join(results) or "No matches found."

    def find_symbol(self, symbol: str, path: str = ".") -> str:
        if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", symbol or ""):
            raise ToolError("Symbol must be a simple identifier.")
        patterns = [rf"^\s*(?:async\s+)?def\s+{re.escape(symbol)}\b", rf"^\s*class\s+{re.escape(symbol)}\b",
                    rf"^\s*(?:function|const|let|var)\s+{re.escape(symbol)}\b"]
        root = self._path(path); results: list[str] = []
        for file in root.rglob("*"):
            if any(part in self.SKIP_DIRS for part in file.parts) or not file.is_file():
                continue
            try:
                for number, line in enumerate(file.read_text(encoding="utf-8").splitlines(), 1):
                    if any(re.search(pattern, line) for pattern in patterns):
                        results.append(f"{file.relative_to(self.workspace)}:{number}: {line.strip()}")
            except (OSError, UnicodeDecodeError):
                continue
        return "\n".join(results) or f"Symbol '{symbol}' was not found."
