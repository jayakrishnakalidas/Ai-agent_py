#!/usr/bin/env python3
"""D_F AI Agent Studio — a transparent, workspace-scoped local AI agent.

Works with LM Studio's OpenAI-compatible local server (usually port 1234).
Start LM Studio's server, then run: python agent.py [workspace_path]
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any

from tools.file_tools import FileTools, ToolError
from tools.dev_tools import DevTools
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
    def __init__(self, workspace: Path, api_url: str, model: str | None = None,
                 timeout: int | None = None, mode: str = "normal") -> None:
        self.workspace = workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.files = FileTools(self.workspace)
        self.dev = DevTools(self.workspace)
        self.python = PythonTools(self.workspace)
        self.client = LMStudioClient(api_url, model, timeout)
        self.memory = AgentMemory(self.workspace / ".agent_memory.json")
        self.memory.load()
        self.chat_memory = ChatMemory(self.workspace / ".agent_chat.json")
        self.chat_memory.load()
        self.operation_lock = RLock()
        self.skills = self._load_skills()
        self.allowed_commands = self._load_commands()
        self.mode = mode
        self.max_actions = 5 if mode == "safe" else (20 if mode == "autonomous" else 10)

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
        print(f"Mode: {self.mode} (maximum actions per request: {self.max_actions})")
        print(f"LM Studio: {self.client.api_url}")

    def execute_action(self, action: dict[str, Any]) -> str:
        name = str(action.get("tool", ""))
        args = action.get("arguments", {})
        if name not in self.allowed_commands:
            return f"Denied: '{name}' is not listed in commands.txt."
        if not isinstance(args, dict):
            return "Invalid action arguments: expected an object."
        read_only = {"list_files", "read_file", "search_files", "find_symbol", "check_syntax", "git_status", "git_diff", "git_log", "list_backups"}
        if self.mode == "safe" and name not in read_only:
            return f"Denied: '{name}' is disabled in Safe mode."
        try:
            if name == "list_files":
                self.log("Reading", str(args.get("path", ".")))
                return self.files.list_files(**args)
            if name == "read_file":
                self.log("Reading", str(args.get("path")))
                return self.files.read_file(**args)
            if name == "write_file":
                path = str(args.get("path", ""))
                instructions = args.get("instructions")
                content = args.get("content")
                if isinstance(instructions, str) and instructions.strip() and (not isinstance(content, str) or not content.strip()):
                    self.log("Generating file", path)
                    result = self.files.write_file(path, self._generate_file(path, instructions))
                elif isinstance(content, str):
                    result = self.files.write_file(path, content)
                else:
                    raise ToolError("write_file needs either 'content' or 'instructions'.")
                self.log("Created/updated", str(args.get("path")))
                return result
            if name == "create_folder":
                result = self.files.create_folder(**args)
                self.log("Created folder", str(args.get("path")))
                return result
            if name == "delete_file":
                result = self.files.delete_file(**args)
                self.log("Deleted with backup", str(args.get("path")))
                return result
            if name == "list_backups":
                self.log("Listing backups", str(args.get("path", "all")))
                return self.files.list_backups(**args)
            if name == "restore_backup":
                result = self.files.restore_backup(**args)
                self.log("Restored backup", str(args.get("path")))
                return result
            if name == "search_files":
                self.log("Searching", str(args.get("query")))
                return self.files.search_files(**args)
            if name == "find_symbol":
                self.log("Finding symbol", str(args.get("symbol")))
                return self.files.find_symbol(**args)
            if name == "replace_text":
                result = self.files.replace_text(**args)
                self.log("Edited with backup", str(args.get("path")))
                return result
            if name == "insert_text":
                result = self.files.insert_text(**args)
                self.log("Edited with backup", str(args.get("path")))
                return result
            if name == "delete_text":
                result = self.files.delete_text(**args)
                self.log("Edited with backup", str(args.get("path")))
                return result
            if name == "patch_file":
                result = self.files.patch_file(**args)
                self.log("Patched with backup", str(args.get("path")))
                return result
            if name == "check_syntax":
                self.log("Checking syntax", str(args.get("path")))
                return self.dev.check_syntax(**args)
            if name == "run_tests":
                self.log("Running tests", "pytest -q")
                return self.dev.run_tests()
            if name == "run_command":
                self.log("Running command", str(args.get("program")))
                return self.dev.run_command(**args)
            if name == "git_status": return self.dev.git_status()
            if name == "git_diff": return self.dev.git_diff()
            if name == "git_log": return self.dev.git_log()
            if name == "git_add": return self.dev.git_add(**args)
            if name == "git_commit": return self.dev.git_commit(**args)
            if name == "run_python":
                self.log("Executing Python", str(args.get("code", ""))[:80])
                return self.python.run(**args)
            return f"Unsupported allowed action: {name}"
        except (ToolError, TypeError, ValueError, OSError) as error:
            self.log("Error", str(error))
            return f"Action failed safely: {error}"

    def _parse_json_plan(self, response: str) -> dict[str, Any]:
        text = response.strip()
        if "```" in text:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if match:
                text = match.group(1).strip()
            else:
                text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
        
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start:end+1]
        
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            pass

        if text.endswith("}}"):
            try:
                data = json.loads(text[:-1])
                if isinstance(data, dict):
                    return data
            except (json.JSONDecodeError, ValueError):
                pass

        raise ValueError("Response is not valid JSON")

    def ask(self, request: str) -> None:
        self.log("Planning", request)
        system_prompt = self._system_prompt()
        loop_history: list[dict[str, str]] = list(self.chat_memory.recent())
        current_request = request
        executed_count = 0
        max_iterations = 5  # Max multi-turn rounds (not individual actions)
        iteration = 0
        previous_actions: list[str] = []  # Track action signatures to detect loops

        while executed_count < self.max_actions and iteration < max_iterations:
            iteration += 1
            try:
                response = self.client.chat(system_prompt, current_request, loop_history)
            except LMStudioError as error:
                print(f"[LM Studio error] {error}")
                return

            try:
                plan = self._parse_json_plan(response)
                actions = plan.get("actions", [])
                if not isinstance(actions, list):
                    actions = []
            except (json.JSONDecodeError, ValueError):
                # Model returned plain text instead of JSON — retry once
                if iteration == 1:
                    print("[AI] Model did not return JSON. Retrying...")
                    loop_history = []  # Clear history to prevent hallucination from old chats
                    current_request = (request + '\n\nYou MUST respond with JSON only: {"message": "...", "actions": [...]}'
                                       '\nDo NOT respond in plain text. Use the tool actions to answer.')
                    continue
                # Second failure — print warning but do NOT save hallucinated text to memory
                print("[AI] (Model could not follow JSON format)")
                print("[AI] " + response[:500])
                return

            msg = plan.get("message", "")
            if msg:
                print("[AI] " + str(msg))

            if not actions:
                self.chat_memory.add("user", request)
                self.chat_memory.add("assistant", msg or "Finished task.")
                break

            # Detect repeated/looping actions
            current_signatures = [json.dumps(a, sort_keys=True) for a in actions if isinstance(a, dict)]
            if current_signatures and current_signatures == previous_actions:
                print("[AI] Detected repeated actions — stopping to prevent infinite loop.")
                self.chat_memory.add("user", request)
                self.chat_memory.add("assistant", msg or "Task stopped due to repeated actions.")
                break
            previous_actions = current_signatures

            read_only_tools = {"list_files", "read_file", "search_files", "find_symbol",
                               "check_syntax", "git_status", "git_diff", "git_log", "list_backups"}
            action_results = []
            has_errors = False
            all_read_only = True
            for action in actions:
                if not isinstance(action, dict):
                    continue
                executed_count += 1
                result = self.execute_action(action)
                tool_name = action.get("tool", "unknown")
                print(f"[Result: {tool_name}] " + result[:4000])
                action_results.append(f"Tool `{tool_name}` output:\n{result}")
                if "failed safely" in result or "Denied" in result:
                    has_errors = True
                if tool_name not in read_only_tools:
                    all_read_only = False

                if executed_count >= self.max_actions:
                    print(f"[AI] Action limit ({self.max_actions}) reached for this turn.")
                    break

            # Read-only operations: done after one round, no need to loop back
            if all_read_only and not has_errors:
                self.chat_memory.add("user", request)
                self.chat_memory.add("assistant", msg or "Done.")
                break

            loop_history.append({"role": "assistant", "content": response})

            if has_errors:
                current_request = ("Tool execution results:\n" + "\n\n".join(action_results)
                    + "\n\nSome tools returned errors. Report these errors to the user clearly and STOP."
                    " Do NOT retry the failed tools. Return JSON with an empty actions list and a message explaining what went wrong.")
            else:
                current_request = ("Tool execution results:\n" + "\n\n".join(action_results)
                    + "\n\nIf more actions are needed to complete the task, return the next JSON plan."
                    " If the task is done, return JSON with an empty actions list and a final message."
                    " Do NOT repeat any action you already executed.")

        self.chat_memory.add("user", request)


    def _generate_file(self, path: str, instructions: str) -> str:
        """Generate file contents separately, avoiding giant JSON action responses."""
        prompt = f"""Generate the complete contents for the workspace file '{path}'.
Return only the file contents: no Markdown fences, no explanation, and no JSON.
Follow this specification exactly:\n{instructions}"""
        try:
            content = self.client.chat("You are a careful code generator.", prompt)
        except LMStudioError as error:
            raise ToolError(f"Could not generate {path}: {error}") from error
        if content.startswith("```"):
            lines = content.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)
        if not content.strip():
            raise ToolError(f"Model returned an empty file for {path}.")
        return content

    def chat(self, message: str) -> str:
        """ChatGPT-style conversation with safe, read-only file & workspace context."""
        msg_lower = message.lower().strip()
        
        # Direct handler for file/folder listing in Chat mode to prevent LLM hallucinations
        if any(w in msg_lower for w in ["list files", "show files", "show me files", "show folders", "show me folders", "show directory", "ls", "what files"]):
            try:
                listing = self.files.list_files(".")
                reply = f"Workspace directory (`{self.workspace}`):\n```\n{listing}\n```"
                self.chat_memory.add("user", message)
                self.chat_memory.add("assistant", reply)
                return reply
            except (ToolError, OSError) as error:
                reply = f"Could not list workspace files: {error}"
                return reply

        file_context = self._chat_file_context(message)
        system = f"""You are D_F AI Agent Studio, a concise and helpful local assistant.
You are talking about the user's workspace at {self.workspace}.

CHAT MODE RULES:
- You have read-only access to workspace files and directory listings automatically attached below.
- If file content or directory listing is supplied in the context below, analyze it, explain it, or answer the user's questions about it accurately.
- NEVER invent or guess file contents or file structures that are not provided in the context.
- If the user asks you to modify code, edit files, or run system commands, suggest switching to Run mode."""
        user_message = message
        history = self.chat_memory.recent()
        if file_context:
            user_message += "\n\nIMPORTANT: Real workspace data attached for this request:\n" + file_context
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
        """Return named workspace file content, fuzzy match, or directory list as context in chat mode."""
        msg_lower = message.lower().strip()
        
        # 1. If user asks to list/show files or directory in chat mode, supply actual file list
        if any(w in msg_lower for w in ["list files", "show files", "show directory", "ls", "what files", "all files"]):
            try:
                listing = self.files.list_files(".")
                return f"\nReal Workspace Files & Directories:\n{listing}\n"
            except (ToolError, OSError):
                pass

        # 2. Extract potential file path mentioned in message
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

            if not candidate.is_file():
                # Try fuzzy matching against relative paths in the workspace
                all_files = [str(p.relative_to(self.workspace)).replace("\\", "/")
                             for p in self.workspace.rglob("*") if p.is_file() and not p.name.startswith(".")]
                close = difflib.get_close_matches(requested, all_files, n=1, cutoff=0.5)
                if not close:
                    close_base = difflib.get_close_matches(
                        Path(requested).name,
                        [Path(f).name for f in all_files],
                        n=1, cutoff=0.5
                    )
                    if close_base:
                        target_name = close_base[0]
                        close = [f for f in all_files if Path(f).name == target_name][:1]

                if close:
                    matched_rel = close[0]
                    candidate = self.workspace / matched_rel
                    relative = str(matched_rel)
                    self.log("Reading for chat (fuzzy match)", relative)
                    content = self.files.read_file(relative)
                    return f"\nRead-only file context (auto-matched '{requested}' to '{relative}'):\n```\n{content}\n```"

                return f"\nThe requested file '{requested}' was not found in this workspace."

            candidate.relative_to(self.workspace)
            relative = str(candidate.relative_to(self.workspace))
            self.log("Reading for chat", relative)
            content = self.files.read_file(relative)
            return f"\nRead-only file context — {relative}:\n```\n{content}\n```"
        except (ToolError, OSError, ValueError) as error:
            return f"\nThe requested file could not be read safely: {error}"

    def _system_prompt(self) -> str:
        tools = {
            "list_files": {"path": "relative directory, optional"},
            "read_file": {"path": "relative file path", "start_line": "optional integer", "end_line": "optional integer"},
            "write_file": {"path": "relative file path", "content": "text for a short file", "instructions": "specification for a generated file"},
            "create_folder": {"path": "relative directory path"},
            "delete_file": {"path": "relative file path"},
            "list_backups": {"path": "optional relative file path"},
            "restore_backup": {"path": "relative file path", "backup_stamp": "optional timestamp string"},
            "search_files": {"query": "text", "path": "relative directory, optional"},
            "find_symbol": {"symbol": "function, class, or variable name", "path": "relative directory, optional"},
            "replace_text": {"path": "relative file", "old": "exact existing text", "new": "replacement"},
            "insert_text": {"path": "relative file", "marker": "exact existing text", "text": "text to insert", "position": "before or after"},
            "delete_text": {"path": "relative file", "text": "exact existing text"},
            "patch_file": {"path": "relative file", "old": "exact existing block", "new": "replacement block"},
            "check_syntax": {"path": "relative code, html, css, or JSON file"},
            "run_tests": {},
            "run_command": {"program": "python, node, npm, or git", "args": "array of allowed arguments"},
            "git_status": {}, "git_diff": {}, "git_log": {},
            "git_add": {"path": "relative file or path, default '.'"},
            "git_commit": {"message": "commit message"},
            "run_python": {"code": "Python source; runs in workspace"},
        }
        skills = "\n\n".join(f"## {name}\n{text}" for name, text in self.skills.items())
        instructions = self._project_instructions()
        return f"""You are a coding agent. RESPOND WITH EXACTLY THE TOOLS THE USER ASKED FOR — NOTHING MORE.
Workspace: {self.workspace}. Mode: {self.mode}.
Return ONLY valid JSON: {{\"message\": \"...\", \"actions\": [{{\"tool\": \"...\", \"arguments\": {{}}}}]}}

STRICT RULES:
- "ls" or "list files" → actions: [{{\"tool\": \"list_files\", \"arguments\": {{}}}}] — that is ALL. Do NOT add read_file or search_files.
- "read X" → actions: [{{\"tool\": \"read_file\", \"arguments\": {{\"path\": \"X\"}}}}] — that is ALL.
- "git status" → actions: [{{\"tool\": \"git_status\", \"arguments\": {{}}}}] — that is ALL.
- NEVER read files the user did not ask to read.
- NEVER invent or guess file names or contents. Use tools to get real data.
- If a tool returns an error, report it and STOP. Do NOT retry.
- NEVER repeat a tool call you already made.
- Only use search/inspect/verify workflows when the user asks to CREATE, MODIFY, FIX, or DELETE code.

Allowed actions: {sorted(self.allowed_commands)}
Action schemas: {json.dumps(tools)}

{f"Project instructions: {instructions}" if instructions != "(none)" else ""}

Skills (apply ONLY during modification tasks):
{skills}

REMEMBER: Do exactly what the user asked. Nothing more. If they said "ls", return ONE list_files action and STOP."""


    def _project_instructions(self) -> str:
        path = self.workspace / ".agent" / "instructions.md"
        try:
            return path.read_text(encoding="utf-8")[:20_000] if path.is_file() else "(none)"
        except (OSError, UnicodeDecodeError):
            return "(could not read project instructions)"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="D_F AI Agent Studio — a transparent, workspace-scoped local AI agent.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python agent.py /storage/emulated/0/MyProject
  python agent.py /storage/emulated/0/MyProject --web
  python agent.py --web --port 8080
  python agent.py /storage/emulated/0/MyProject --timeout 900

Interactive commands:
  /status     Show workspace, LM Studio URL, skills, and enabled actions.
  /skills     List loaded skills from the skills/ folder.
  /history    Show recent recorded agent activity.
  /mode       Show the current permission mode.
  /quit       Exit the agent.

Enabled AI actions (configured in commands.txt):
  list_files, read_file, search_files, find_symbol, write_file, replace_text,
  insert_text, delete_text, patch_file, create_folder, delete_file, check_syntax,
  run_tests, git_status, git_diff, git_log, run_python

Start LM Studio's local server before sending requests. Browser mode is
localhost-only by default: http://127.0.0.1:8000""",
    )
    parser.add_argument("workspace", nargs="?", help="Workspace path (default: this agent folder)")
    parser.add_argument("--api-url", default=DEFAULT_API, help="LM Studio OpenAI API base URL")
    parser.add_argument("--model", help="Loaded LM Studio model identifier")
    parser.add_argument("--timeout", type=int, default=100, help="LM Studio response timeout in seconds (default: 100)")
    parser.add_argument("--web", action="store_true", help="Start the browser interface instead of the terminal")
    parser.add_argument("--host", default="127.0.0.1", help="Web interface host (default: localhost only)")
    parser.add_argument("--port", type=int, default=8000, help="Web interface port")
    parser.add_argument("--mode", choices=("safe", "normal", "autonomous"), default="normal", help="Agent permission mode")
    args = parser.parse_args()
    banner()
    selected = args.workspace
    if not selected:
        print(f"\nAgent location:\n{ROOT}\n\nEnter workspace path.\nPress ENTER to use the agent's folder.")
        selected = input("\nWorkspace path: ").strip() or str(ROOT / "workspace")
    try:
        if args.timeout < 10:
            parser.error("--timeout must be at least 10 seconds")
        agent = Agent(Path(selected), args.api_url, args.model, args.timeout, args.mode)
    except (OSError, ValueError) as error:
        print(f"Cannot open workspace: {error}")
        return 1
    if args.web:
        from web import run_server
        run_server(agent, args.host, args.port)
        return 0
    agent.status()
    print("\nType a request. Commands: /status, /skills, /history, /mode, /quit")
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
        if request == "/mode": print(f"Mode: {agent.mode}"); continue
        agent.ask(request)


if __name__ == "__main__":
    sys.exit(main())
