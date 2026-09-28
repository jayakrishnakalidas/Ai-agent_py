#!/usr/bin/env python3
"""Android Workspace MCP listener for LM Studio.

Run by LM Studio as a stdio MCP server. All protocol messages are written to stdout;
diagnostics go to stderr. The workspace argument follows agent.py's convention.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from tools.file_tools import FileTools, ToolError

ROOT = Path(__file__).resolve().parent
DEFAULT_ANDROID_ROOTS = ["/sdcard/Download", "/sdcard/Documents"]


class MCPError(Exception):
    pass


class AndroidWorkspaceMCP:
    def __init__(self, workspace: Path, adb: str, serial: str | None) -> None:
        self.workspace = workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.files = FileTools(self.workspace)
        self.adb, self.serial = adb, serial
        self.android_roots = self._load_android_roots()

    def _load_android_roots(self) -> list[PurePosixPath]:
        config = ROOT / "android_paths.txt"
        try:
            roots = [line.strip() for line in config.read_text(encoding="utf-8").splitlines()
                     if line.strip() and not line.lstrip().startswith("#")]
        except OSError:
            roots = DEFAULT_ANDROID_ROOTS
        valid = [PurePosixPath(root) for root in roots if root.startswith("/")]
        return valid or [PurePosixPath(root) for root in DEFAULT_ANDROID_ROOTS]

    def _adb_command(self, *args: str) -> list[str]:
        command = [self.adb]
        if self.serial:
            command.extend(["-s", self.serial])
        return command + list(args)

    def _run_adb(self, *args: str, input_data: str | None = None) -> str:
        try:
            result = subprocess.run(self._adb_command(*args), input=input_data, text=True,
                capture_output=True, timeout=25, encoding="utf-8", errors="replace")
        except FileNotFoundError as error:
            raise MCPError("ADB was not found. Install Android platform-tools or pass --adb PATH.") from error
        except subprocess.TimeoutExpired as error:
            raise MCPError("ADB command timed out after 25 seconds.") from error
        if result.returncode != 0:
            raise MCPError((result.stderr or result.stdout or "ADB command failed.").strip()[:1000])
        return result.stdout.strip()

    def _android_path(self, raw: str) -> str:
        if not isinstance(raw, str) or not raw.startswith("/"):
            raise MCPError("Android path must be absolute and inside an approved Android folder.")
        if not re.fullmatch(r"/[A-Za-z0-9._/-]+", raw):
            raise MCPError("Android paths may contain only letters, numbers, '.', '_', '-', and '/'.")
        path = PurePosixPath(raw)
        if ".." in path.parts:
            raise MCPError("Android paths cannot contain '..'.")
        if not any(path == root or root in path.parents for root in self.android_roots):
            allowed = ", ".join(map(str, self.android_roots))
            raise MCPError(f"Android path is outside approved folders: {allowed}")
        return str(path)

    def call(self, name: str, arguments: dict[str, Any]) -> str:
        if name == "workspace_list_files": return self.files.list_files(arguments.get("path", "."))
        if name == "workspace_read_file": return self.files.read_file(self._required(arguments, "path"))
        if name == "workspace_write_file":
            return self.files.write_file(self._required(arguments, "path"), self._required(arguments, "content"))
        if name == "workspace_create_folder": return self.files.create_folder(self._required(arguments, "path"))
        if name == "android_devices": return self._run_adb("devices", "-l") or "No ADB devices found."
        if name == "android_list_files": return self._run_adb("shell", "ls", "-la", "--", self._android_path(self._required(arguments, "path")))
        if name == "android_read_text_file":
            return self._run_adb("exec-out", "cat", "--", self._android_path(self._required(arguments, "path")))
        if name == "android_create_folder":
            return self._run_adb("shell", "mkdir", "-p", "--", self._android_path(self._required(arguments, "path"))) or "Folder ready."
        if name == "android_write_text_file": return self._android_write(arguments)
        raise MCPError(f"Unknown tool: {name}")

    @staticmethod
    def _required(arguments: dict[str, Any], key: str) -> str:
        value = arguments.get(key)
        if not isinstance(value, str) or not value:
            raise MCPError(f"'{key}' must be a non-empty string.")
        return value

    def _android_write(self, arguments: dict[str, Any]) -> str:
        destination = self._android_path(self._required(arguments, "path"))
        content = self._required(arguments, "content")
        parent = str(PurePosixPath(destination).parent)
        temp_name = ""
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".txt") as temp:
                temp.write(content); temp_name = temp.name
            self._run_adb("shell", "mkdir", "-p", "--", parent)
            self._run_adb("push", temp_name, destination)
            return f"Wrote {len(content)} characters to {destination}."
        finally:
            if temp_name:
                Path(temp_name).unlink(missing_ok=True)


TOOLS = [
    ("workspace_list_files", "List a workspace folder (relative path only).", {"path": {"type": "string"}}),
    ("workspace_read_file", "Read a UTF-8 text file in the workspace.", {"path": {"type": "string"}}),
    ("workspace_write_file", "Write a UTF-8 text file in the workspace.", {"path": {"type": "string"}, "content": {"type": "string"}}),
    ("workspace_create_folder", "Create a workspace folder.", {"path": {"type": "string"}}),
    ("android_devices", "List ADB-connected Android devices.", {}),
    ("android_list_files", "List files inside an approved Android storage folder.", {"path": {"type": "string"}}),
    ("android_read_text_file", "Read a text file inside an approved Android storage folder.", {"path": {"type": "string"}}),
    ("android_write_text_file", "Write a text file inside an approved Android storage folder.", {"path": {"type": "string"}, "content": {"type": "string"}}),
    ("android_create_folder", "Create a folder inside an approved Android storage folder.", {"path": {"type": "string"}}),
]


def tool_definitions() -> list[dict[str, Any]]:
    return [{"name": name, "description": description,
             "inputSchema": {"type": "object", "properties": properties,
                             "required": [key for key in properties if key in {"path", "content"}]}}
            for name, description, properties in TOOLS]


def respond(message_id: Any, result: dict[str, Any] | None = None, error: str | None = None) -> None:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": message_id}
    payload["error" if error else "result"] = ({"code": -32603, "message": error} if error else result)
    print(json.dumps(payload), flush=True)


def serve(server: AndroidWorkspaceMCP) -> None:
    for line in sys.stdin:
        try:
            request = json.loads(line)
            method, message_id = request.get("method"), request.get("id")
            if method == "initialize":
                respond(message_id, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                                     "serverInfo": {"name": "android-workspace-listener", "version": "1.0.0"}})
            elif method == "tools/list": respond(message_id, {"tools": tool_definitions()})
            elif method == "tools/call":
                params = request.get("params", {}); arguments = params.get("arguments", {})
                if not isinstance(arguments, dict): raise MCPError("Tool arguments must be an object.")
                text = server.call(params.get("name", ""), arguments)
                respond(message_id, {"content": [{"type": "text", "text": text}]})
            elif message_id is not None:
                respond(message_id, error=f"Unsupported MCP method: {method}")
        except (json.JSONDecodeError, MCPError, ToolError, OSError, ValueError, TypeError) as error:
            if 'message_id' in locals() and message_id is not None: respond(message_id, error=str(error))
            else: print(f"MCP listener error: {error}", file=sys.stderr, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Android Workspace MCP listener for LM Studio")
    parser.add_argument("workspace", nargs="?", default=str(ROOT / "workspace"), help="Workspace path")
    parser.add_argument("--adb", default="adb", help="ADB executable path")
    parser.add_argument("--serial", help="Target Android device serial (required if more than one is connected)")
    args = parser.parse_args()
    try: serve(AndroidWorkspaceMCP(Path(args.workspace), args.adb, args.serial))
    except (OSError, ValueError) as error: print(f"Cannot start MCP listener: {error}", file=sys.stderr); return 1
    return 0


if __name__ == "__main__": raise SystemExit(main())
