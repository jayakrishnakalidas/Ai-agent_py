# D_F AI Agent Studio

A transparent local coding agent using [LM Studio](https://lmstudio.ai/)'s OpenAI-compatible server.

## Run

1. In LM Studio, load a model and start the local server (default: `http://127.0.0.1:1234`).
2. Run `python agent.py /path/to/your/project`, or run `python agent.py` and enter a workspace.
3. Give the agent a request. It prints every planned, read, write, folder, and Python-execution action.

### Browser interface

Run `python agent.py /path/to/your/project --web`, then open
`http://127.0.0.1:8000` in your browser. Choose another port with `--port 8080`.
The default host is `127.0.0.1`, so the interface is not exposed to other devices.
Use the **CHAT** button for a persistent ChatGPT-style conversation. Messages are saved
in `.agent_chat.json` inside the selected workspace. Switch back to Run mode when you
want the agent to make workspace changes. Chat can also safely read and explain a named
text file, for example: `Read index.html and explain it simply.`
Use **CLEAR** (and confirm) to permanently clear this workspace's chat and activity memory.

## Coding-agent workflow

The agent now supports project search, symbol lookup, safe exact-text edits, automatic
file backups, syntax checks, tests, and read-only Git status/diff/log tools. Existing
files are backed up under `.agent_backups/` before every write, edit, or deletion.

Choose a mode when launching: `--mode safe` permits inspection only; `--mode normal`
permits normal edits with backups; `--mode autonomous` allows up to 20 planned actions.
Put project-specific rules in `.agent/instructions.md` inside the selected workspace.
The controlled `run_command` tool permits only Python test/compile modules, `node --check`,
`npm test`/`npm run`, and read-only Git commands; it never uses a shell.

## Android MCP listener for LM Studio

`listener.py` is a local stdio MCP server. It lets an LM Studio model read/write folders
in the selected workspace and approved Android shared-storage folders through ADB. It
does **not** expose an arbitrary shell-command tool. Connect your Android device with USB
debugging enabled and authorize the computer, then configure LM Studio's `mcp.json`:

```json
{
  "mcpServers": {
    "android-workspace": {
      "command": "python",
      "args": ["D:\\software\\ai-agent\\listener.py", "D:\\software\\ai-agent\\project1"]
    }
  }
}
```

In LM Studio, open the Program panel, choose **Install → Edit mcp.json**, paste the
server entry, then enable it. The allowed Android folders are in `android_paths.txt`;
restart/reconnect the MCP server after changing that file. Test ADB separately with
`adb devices` before using the Android tools.

`commands.txt` is the action allowlist. Add skills as `.md` files in `skills/`. The agent only accepts paths inside the selected workspace, blocks `..` traversal, and keeps a local `.agent_memory.json` activity history in that workspace.

## Configuration

Use `--api-url http://host:port/v1` or set `LM_STUDIO_URL`. Use `--model model-id` if your LM Studio server requires a specific model identifier.
Large generations can take time on local models. The default LM Studio request timeout is
100 seconds; set a longer value with `--timeout 900` if necessary.
For substantial files, the agent now uses a small JSON plan first and requests the file
contents in a separate generation. Normal questions in Run mode are shown as replies,
not JSON parsing errors.
