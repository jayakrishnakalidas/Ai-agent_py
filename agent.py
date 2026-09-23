#!/usr/bin/env python3
"""D_F AI Agent Studio — a transparent, workspace-scoped local AI agent.

Works with LM Studio's OpenAI-compatible local server (usually port 1234).
Start LM Studio's server, then run: python agent.py [workspace_path]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.file_tools import FileTools, ToolError
from tools.python_tools import PythonTools
from tools.lmstudio import LMStudioClient, LMStudioError

ROOT = Path(__file__).resolve().parent
DEFAULT_API = os.getenv("LM_STUDIO_URL", "http://127.0.0.1:1234/v1")


def banner() -> None:
    print("\n" + "=" * 60)
    print("D_F AI AGENT STUDIO")
    print("=" * 60)


@dataclass
class AgentMemory:
    """Small, on-disk memory for the active workspace."""
    path: Path
    events: list[dict[str, str]] = field(default_factory=list)

    def load(self) -> None:
        try:
            if self.path.exists():
                self.events = json.loads(self.path.read_text(encoding="utf-8"))[-100:]
        except (OSError, json.JSONDecodeError):
            self.events = []

    def add(self, action: str, detail: str) -> None:
        self.events.append({"action": action, "detail": detail})
        self.events = self.events[-100:]
        try:
            self.path.write_text(json.dumps(self.events, indent=2), encoding="utf-8")
        except OSError:
            pass

    def clear(self) -> None:
        self.events = []
        try:
            self.path.write_text("[]", encoding="utf-8")
        except OSError:
            pass


@dataclass
class ChatMemory:
    """Persistent conversation turns, scoped to one workspace."""
    path: Path
    messages: list[dict[str, str]] = field(default_factory=list)

    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                self.messages = [entry for entry in data if isinstance(entry, dict)
                    and entry.get("role") in {"user", "assistant"}
                    and isinstance(entry.get("content"), str)][-80:]
        except (OSError, json.JSONDecodeError):
            self.messages = []

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        self.messages = self.messages[-80:]
        try:
            self.path.write_text(json.dumps(self.messages, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def recent(self) -> list[dict[str, str]]:
        return self.messages[-20:]

    def clear(self) -> None:
        self.messages = []
        try:
            self.path.write_text("[]", encoding="utf-8")
        except OSError:
            pass


class Agent:
    def __init__(self, workspace: Path, api_url: str, model: str | None = None) -> None:
        self.workspace = workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.files = FileTools(self.workspace)
        self.python = PythonTools(self.workspace)
        self.client = LMStudioClient(api_url, model)
        self.memory = AgentMemory(self.workspace / ".agent_memory.json")
        self.memory.load()
        self.chat_memory = ChatMemory(self.workspace / ".agent_chat.json")
        self.chat_memory.load()
        self.skills = self._load_skills()
        self.allowed_commands = self._load_commands()

    def log(self, action: str, detail: str) -> None:
        print(f"[AI] {action}: {detail}")
        self.memory.add(action, detail)

    def _load_skills(self) -> dict[str, str]:
        skills: dict[str, str] = {}
        directory = ROOT / "skills"
        for path in directory.glob("*.md"):
            try:
                skills[path.stem] = path.read_text(encoding="utf-8")
            except OSError as error:
                print(f"[Warning] Could not load skill {path.name}: {error}")
        return skills

    def _load_commands(self) -> set[str]:
        path = ROOT / "commands.txt"
        try:
            return {line.strip() for line in path.read_text(encoding="utf-8").splitlines()
                    if line.strip() and not line.lstrip().startswith("#")}
        except OSError:
            return set()

    def status(self) -> None:
        print(f"Workspace: {self.workspace}")
        print(f"Skills: {', '.join(self.skills) or 'none'}")
        print(f"Allowed actions: {', '.join(sorted(self.allowed_commands))}")
        print(f"LM Studio: {self.client.api_url}")

    def execute_action(self, action: dict[str, Any]) -> str:
        name = str(action.get("tool", ""))
        args = action.get("arguments", {})
        if name not in self.allowed_commands:
            return f"Denied: '{name}' is not listed in commands.txt."
        if not isinstance(args, dict):
            return "Invalid action arguments: expected an object."
        try:
            if name == "list_files":
                self.log("Reading", str(args.get("path", ".")))
                return self.files.list_files(**args)
            if name == "read_file":
                self.log("Reading", str(args.get("path")))
                return self.files.read_file(**args)
            if name == "write_file":
                result = self.files.write_file(**args)
                self.log("Created/updated", str(args.get("path")))
                return result
            if name == "create_folder":
                result = self.files.create_folder(**args)
                self.log("Created folder", str(args.get("path")))
                return result
            if name == "run_python":
                self.log("Executing Python", str(args.get("code", ""))[:80])
                return self.python.run(**args)
            return f"Unsupported allowed action: {name}"
        except (ToolError, TypeError, ValueError, OSError) as error:
            self.log("Error", str(error))
            return f"Action failed safely: {error}"

    def ask(self, request: str) -> None:
        prompt = self._system_prompt()
        self.log("Planning", request)
        try:
            response = self.client.chat(prompt, request, self.chat_memory.recent())
        except LMStudioError as error:
            print(f"[LM Studio error] {error}")
            return
        try:
            plan = json.loads(response)
            actions = plan.get("actions", [])
            if not isinstance(actions, list):
                raise ValueError("'actions' must be a list")
        except (json.JSONDecodeError, ValueError) as error:
            print("[AI response] " + response)
            print(f"[Notice] Model did not return executable JSON: {error}")
            return
        if plan.get("message"):
            print("[AI] " + str(plan["message"]))
        self.chat_memory.add("user", request)
        self.chat_memory.add("assistant", str(plan.get("message", "Completed requested actions.")))
        for action in actions:
            if not isinstance(action, dict):
                print("[AI] Skipped invalid action.")
                continue
            result = self.execute_action(action)
            print("[Result] " + result[:4000])

    def chat(self, message: str) -> str:
        """ChatGPT-style conversation with safe, read-only file context."""
        file_context = self._chat_file_context(message)
        system = f"""You are D_F AI Agent Studio, a concise and helpful local assistant.
You are talking about the user's workspace at {self.workspace}. In chat mode you have
read-only access to a specifically named text file when its content is supplied in the
user message. If it is supplied, you MUST explain its actual contents and must not say
you cannot access files. Suggest Run mode when the user wants workspace changes."""
        user_message = message
        history = self.chat_memory.recent()
        if file_context:
            # A fresh context prevents older model refusals from overriding a file that
            # has just been read by the application.
            user_message += "\n\nIMPORTANT: The application has already read this file. " \
                            "Explain it simply using the supplied contents.\n" + file_context
            history = []
        try:
            reply = self.client.chat(system, user_message, history)
        except LMStudioError as error:
            raise RuntimeError(str(error)) from error
        self.chat_memory.add("user", message)
        self.chat_memory.add("assistant", reply)
        return reply

    def clear_memory(self) -> None:
        """Clear the selected workspace's saved chat and activity history."""
        self.chat_memory.clear()
        self.memory.clear()

    def _chat_file_context(self, message: str) -> str:
        """Return a named workspace file as context when a user asks about one.

        This is intentionally read-only and requires a filename with an extension;
        model prompts alone cannot make chat inspect arbitrary files.
        """
        match = re.search(
            r"(?<![\w.-])((?:[A-Za-z0-9_-]+[\\/])*(?:[A-Za-z0-9_-]+\.)+[A-Za-z0-9_-]{1,10})(?![\w.-])",
            message,
        )
        if not match:
            return ""
        requested = match.group(1).strip().replace("\\", "/")
        try:
            candidate = self.files._path(requested)
            if not candidate.is_file() and "/" not in requested:
                matches = [path for path in self.workspace.rglob(requested) if path.is_file()]
                candidate = matches[0].resolve() if len(matches) == 1 else candidate
            candidate.relative_to(self.workspace)
            if not candidate.is_file():
                return f"\nThe requested file '{requested}' was not found in this workspace."
            relative = str(candidate.relative_to(self.workspace))
            self.log("Reading for chat", relative)
            content = self.files.read_file(relative)
            return f"\nRead-only file context — {relative}:\n```\n{content}\n```"
        except (ToolError, OSError, ValueError) as error:
            return f"\nThe requested file could not be read safely: {error}"

    def _system_prompt(self) -> str:
        tools = {
            "list_files": {"path": "relative directory, optional"},
            "read_file": {"path": "relative file path"},
            "write_file": {"path": "relative file path", "content": "text"},
            "create_folder": {"path": "relative directory path"},
            "run_python": {"code": "Python source; runs in workspace"},
        }
        skills = "\n\n".join(f"## {name}\n{text}" for name, text in self.skills.items())
        return f"""You are a careful local coding agent. Workspace: {self.workspace}.
Only use actions from this allowlist: {sorted(self.allowed_commands)}.
Return ONLY valid JSON: {{\"message\": \"brief plan\", \"actions\": [{{\"tool\": \"...\", \"arguments\": {{}}}}]}}.
Never use absolute paths, shell commands, network operations, deletion, or paths containing '..'.
Available action schemas: {json.dumps(tools)}
Skills to follow:\n{skills}"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="D_F AI Agent Studio — a transparent, workspace-scoped local AI agent.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python agent.py /storage/emulated/0/MyProject
  python agent.py /storage/emulated/0/MyProject --web
  python agent.py --web --port 8080

Interactive commands:
  /status     Show workspace, LM Studio URL, skills, and enabled actions.
  /skills     List loaded skills from the skills/ folder.
  /history    Show recent recorded agent activity.
  /quit       Exit the agent.

Enabled AI actions (configured in commands.txt):
  list_files, read_file, write_file, create_folder, run_python

Start LM Studio's local server before sending requests. Browser mode is
localhost-only by default: http://127.0.0.1:8000""",
    )
    parser.add_argument("workspace", nargs="?", help="Workspace path (default: this agent folder)")
    parser.add_argument("--api-url", default=DEFAULT_API, help="LM Studio OpenAI API base URL")
    parser.add_argument("--model", help="Loaded LM Studio model identifier")
    parser.add_argument("--web", action="store_true", help="Start the browser interface instead of the terminal")
    parser.add_argument("--host", default="127.0.0.1", help="Web interface host (default: localhost only)")
    parser.add_argument("--port", type=int, default=8000, help="Web interface port")
    args = parser.parse_args()
    banner()
    selected = args.workspace
    if not selected:
        print(f"\nAgent location:\n{ROOT}\n\nEnter workspace path.\nPress ENTER to use the agent's folder.")
        selected = input("\nWorkspace path: ").strip() or str(ROOT / "workspace")
    try:
        agent = Agent(Path(selected), args.api_url, args.model)
    except (OSError, ValueError) as error:
        print(f"Cannot open workspace: {error}")
        return 1
    if args.web:
        from web import run_server
        run_server(agent, args.host, args.port)
        return 0
    agent.status()
    print("\nType a request. Commands: /status, /skills, /history, /quit")
    while True:
        try:
            request = input("\nYou > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return 0
        if not request:
            continue
        if request in {"/quit", "/exit"}:
            return 0
        if request == "/status": agent.status(); continue
        if request == "/skills": print("\n".join(agent.skills) or "No skills loaded."); continue
        if request == "/history": print(json.dumps(agent.memory.events[-20:], indent=2)); continue
        agent.ask(request)


if __name__ == "__main__":
    sys.exit(main())
