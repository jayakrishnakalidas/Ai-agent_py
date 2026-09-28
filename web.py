"""Local browser UI for D_F AI Agent Studio with an ultra-modern glassmorphism design."""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent import Agent

PAGE = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>D_F AI Agent Studio</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #0b0f19;
  --bg-gradient: radial-gradient(circle at 50% 0%, #1e293b 0%, #0b0f19 75%);
  --sidebar-bg: rgba(15, 23, 42, 0.75);
  --card-bg: rgba(30, 41, 59, 0.5);
  --card-border: rgba(255, 255, 255, 0.08);
  --card-hover-border: rgba(99, 102, 241, 0.4);
  --text-main: #f8fafc;
  --text-muted: #94a3b8;
  --accent-cyan: #06b6d4;
  --accent-indigo: #6366f1;
  --accent-emerald: #10b981;
  --accent-amber: #f59e0b;
  --accent-rose: #f43f5e;
  --font-sans: "Inter", -apple-system, BlinkMacSystemFont, sans-serif;
  --font-mono: "JetBrains Mono", monospace;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg);
  background-image: var(--bg-gradient);
  color: var(--text-main);
  font-family: var(--font-sans);
  min-height: 100vh;
  overflow-x: hidden;
}

.shell {
  display: grid;
  grid-template-columns: 290px 1fr;
  min-height: 100vh;
}

/* Sidebar */
.side {
  background: var(--sidebar-bg);
  backdrop-filter: blur(20px);
  border-right: 1px solid var(--card-border);
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}
.brand-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, var(--accent-cyan), var(--accent-indigo));
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 16px;
  color: #fff;
  box-shadow: 0 0 15px rgba(99, 102, 241, 0.4);
}
.brand-title {
  font-weight: 700;
  font-size: 18px;
  letter-spacing: -0.02em;
  background: linear-gradient(135deg, #fff, #94a3b8);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.brand-tag {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--accent-cyan);
  font-weight: 600;
}

.card {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  border-radius: 12px;
  padding: 16px;
}
.card-title {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  font-weight: 600;
  margin-bottom: 10px;
}
.meta-value {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-main);
  word-break: break-all;
}

/* Mode selector */
.mode-selector {
  display: flex;
  gap: 4px;
  background: rgba(15, 23, 42, 0.8);
  padding: 4px;
  border-radius: 8px;
  border: 1px solid var(--card-border);
}
.mode-btn {
  flex: 1;
  padding: 6px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 500;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.mode-btn.active {
  background: var(--accent-indigo);
  color: #fff;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
}
.mode-btn:hover:not(.active) {
  color: var(--text-main);
  background: rgba(255, 255, 255, 0.05);
}

.skill-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.badge {
  font-family: var(--font-mono);
  font-size: 10px;
  padding: 3px 8px;
  border-radius: 6px;
  background: rgba(6, 182, 212, 0.1);
  color: var(--accent-cyan);
  border: 1px solid rgba(6, 182, 212, 0.2);
}

/* Main Area */
.main {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.topbar {
  padding: 16px 28px;
  border-bottom: 1px solid var(--card-border);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(15, 23, 42, 0.4);
  backdrop-filter: blur(10px);
}
.topbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.console-title {
  font-weight: 600;
  font-size: 15px;
}
.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent-emerald);
  box-shadow: 0 0 10px var(--accent-emerald);
}

.nav-buttons {
  display: flex;
  gap: 8px;
}
.btn-secondary {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--card-border);
  color: var(--text-main);
  padding: 7px 14px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}
.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.2);
}
.btn-secondary.active {
  background: var(--accent-cyan);
  color: #0b0f19;
  font-weight: 600;
  border-color: var(--accent-cyan);
}

/* Feed */
.feed {
  flex: 1;
  padding: 28px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
  scroll-behavior: smooth;
}

.intro {
  max-width: 680px;
  margin: 40px auto;
  text-align: center;
  animation: fadeIn 0.6s ease;
}
.intro h1 {
  font-size: 38px;
  font-weight: 700;
  letter-spacing: -0.03em;
  margin-bottom: 12px;
  background: linear-gradient(135deg, #fff 0%, #94a3b8 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.intro p {
  color: var(--text-muted);
  font-size: 15px;
  line-height: 1.6;
  margin-bottom: 28px;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
}
.chip {
  background: rgba(30, 41, 59, 0.6);
  border: 1px solid var(--card-border);
  color: var(--text-main);
  padding: 10px 16px;
  border-radius: 20px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.chip:hover {
  border-color: var(--accent-indigo);
  transform: translateY(-2px);
  background: rgba(99, 102, 241, 0.15);
}

/* Feed Events */
.msg {
  max-width: 85%;
  animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.msg.user {
  align-self: flex-end;
}
.msg.user .msg-content {
  background: linear-gradient(135deg, var(--accent-indigo), #4f46e5);
  color: #fff;
  border-radius: 16px 16px 2px 16px;
  padding: 14px 18px;
  font-size: 14px;
  box-shadow: 0 4px 15px rgba(99, 102, 241, 0.2);
}
.msg.assistant {
  align-self: flex-start;
}
.msg.assistant .msg-content {
  background: var(--card-bg);
  border: 1px solid var(--card-border);
  backdrop-filter: blur(12px);
  border-radius: 16px 16px 16px 2px;
  padding: 16px 20px;
  font-size: 14px;
  line-height: 1.6;
}

.event-card {
  background: rgba(15, 23, 42, 0.6);
  border-left: 3px solid var(--accent-cyan);
  border-radius: 6px;
  padding: 12px 16px;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
.event-card.plan { border-left-color: var(--accent-indigo); }
.event-card.result { border-left-color: var(--accent-emerald); }
.event-card.error { border-left-color: var(--accent-rose); }

/* Compose Bar */
.compose-box {
  padding: 20px 28px;
  background: rgba(15, 23, 42, 0.6);
  border-top: 1px solid var(--card-border);
  backdrop-filter: blur(16px);
}
.compose-form {
  display: flex;
  gap: 12px;
  background: rgba(30, 41, 59, 0.7);
  border: 1px solid var(--card-border);
  border-radius: 14px;
  padding: 8px 12px;
  transition: all 0.2s ease;
}
.compose-form:focus-within {
  border-color: var(--accent-indigo);
  box-shadow: 0 0 20px rgba(99, 102, 241, 0.25);
}
textarea {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--text-main);
  font-family: var(--font-sans);
  font-size: 14px;
  outline: none;
  resize: none;
  min-height: 42px;
  max-height: 160px;
  line-height: 1.5;
  padding: 8px 4px;
}
textarea::placeholder { color: var(--text-muted); }
.btn-send {
  background: linear-gradient(135deg, var(--accent-cyan), var(--accent-indigo));
  border: none;
  color: #fff;
  font-weight: 600;
  font-size: 13px;
  padding: 0 22px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.btn-send:hover {
  opacity: 0.9;
  transform: scale(1.02);
}
.btn-send:disabled {
  opacity: 0.5;
  cursor: wait;
}

@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes slideUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }

@media (max-width: 820px) {
  .shell { grid-template-columns: 1fr; }
  .side { display: none; }
}
</style>
</head>
<body>
<div class="shell">
  <aside class="side">
    <div class="brand">
      <div class="brand-icon">D_F</div>
      <div>
        <div class="brand-title">Agent Studio</div>
        <div class="brand-tag">Autonomous Coding</div>
      </div>
    </div>

    <div class="card">
      <div class="card-title">Permission Mode</div>
      <div class="mode-selector">
        <button type="button" class="mode-btn" id="mode-safe" onclick="setMode('safe')">Safe</button>
        <button type="button" class="mode-btn active" id="mode-normal" onclick="setMode('normal')">Normal</button>
        <button type="button" class="mode-btn" id="mode-autonomous" onclick="setMode('autonomous')">Auto</button>
      </div>
    </div>

    <div class="card">
      <div class="card-title">Active Workspace</div>
      <div class="meta-value" id="workspace">Loading...</div>
    </div>

    <div class="card">
      <div class="card-title">LM Studio Engine</div>
      <div class="meta-value" id="api">Loading...</div>
    </div>

    <div class="card">
      <div class="card-title">Loaded Skills</div>
      <div class="skill-list" id="skills-list">
        <span class="badge">coding</span>
        <span class="badge">file_management</span>
      </div>
    </div>
  </aside>

  <main class="main">
    <header class="topbar">
      <div class="topbar-left">
        <div class="pulse-dot"></div>
        <div class="console-title" id="title">Operations Console</div>
      </div>
      <div class="nav-buttons">
        <button class="btn-secondary" id="chat-toggle" onclick="toggleChatMode()">Chat Mode</button>
        <button class="btn-secondary" onclick="clearMemory()">Clear Session</button>
      </div>
    </header>

    <section class="feed" id="feed">
      <div class="intro" id="hero">
        <h1>Local AI Coding Assistant</h1>
        <p>Inspect, plan, edit code safely with automatic backups, syntax checks, and testing capabilities.</p>
        <div class="chips">
          <div class="chip" onclick="usePrompt('Read this workspace and explain the structure.')">🔍 Explore workspace</div>
          <div class="chip" onclick="usePrompt('Create a Python CLI app with unit tests.')">🐍 Build Python App</div>
          <div class="chip" onclick="usePrompt('Check syntax and run tests across the workspace.')">🧪 Check Syntax & Tests</div>
        </div>
      </div>
    </section>

    <div class="compose-box">
      <form class="compose-form" id="form">
        <textarea id="request" required placeholder="Describe what to build or inspect... (Press Enter to send)" rows="1"></textarea>
        <button type="submit" class="btn-send" id="send">RUN</button>
      </form>
    </div>
  </main>
</div>

<script>
let chatMode = false;
let currentMode = "normal";
const feed = document.getElementById('feed');
const box = document.getElementById('request');
const sendBtn = document.getElementById('send');

function appendUserMsg(text) {
  const hero = document.getElementById('hero');
  if (hero) hero.remove();
  const div = document.createElement('div');
  div.className = 'msg user';
  div.innerHTML = `<div class="msg-content">${escapeHtml(text)}</div>`;
  feed.appendChild(div);
  feed.scrollTop = feed.scrollHeight;
}

function appendAssistantMsg(text) {
  const hero = document.getElementById('hero');
  if (hero) hero.remove();
  const div = document.createElement('div');
  div.className = 'msg assistant';
  div.innerHTML = `<div class="msg-content">${escapeHtml(text)}</div>`;
  feed.appendChild(div);
  feed.scrollTop = feed.scrollHeight;
}

function appendEvent(text, type = 'plan') {
  const hero = document.getElementById('hero');
  if (hero) hero.remove();
  const div = document.createElement('div');
  div.className = `event-card ${type}`;
  div.textContent = text;
  feed.appendChild(div);
  feed.scrollTop = feed.scrollHeight;
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function usePrompt(text) {
  box.value = text;
  box.focus();
}

async function loadStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    document.getElementById('workspace').textContent = data.workspace;
    document.getElementById('api').textContent = data.api;
    if (data.mode) updateModeUI(data.mode);
    if (data.skills && data.skills.length) {
      document.getElementById('skills-list').innerHTML = data.skills.map(s => `<span class="badge">${s}</span>`).join('');
    }
  } catch (err) {
    console.error('Failed to load status', err);
  }
}

async function setMode(mode) {
  try {
    const res = await fetch('/api/mode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode })
    });
    const data = await res.json();
    if (data.mode) updateModeUI(data.mode);
  } catch (err) {
    console.error('Mode switch failed', err);
  }
}

function updateModeUI(mode) {
  currentMode = mode;
  ['safe', 'normal', 'autonomous'].forEach(m => {
    const btn = document.getElementById(`mode-${m === 'autonomous' ? 'autonomous' : m}`);
    if (btn) btn.classList.toggle('active', m === mode);
  });
}

function toggleChatMode() {
  chatMode = !chatMode;
  const toggleBtn = document.getElementById('chat-toggle');
  toggleBtn.classList.toggle('active', chatMode);
  document.getElementById('title').textContent = chatMode ? 'Conversation Mode' : 'Operations Console';
  box.placeholder = chatMode ? 'Message agent in chat mode...' : 'Describe what to build or inspect...';
  sendBtn.textContent = chatMode ? 'SEND' : 'RUN';
}

async function clearMemory() {
  if (!confirm('Clear session and memory for this workspace?')) return;
  try {
    await fetch('/api/clear', { method: 'POST' });
    feed.innerHTML = '';
    appendAssistantMsg('Session memory cleared.');
  } catch (err) {
    appendEvent('Failed to clear memory: ' + err.message, 'error');
  }
}

document.getElementById('form').onsubmit = async (e) => {
  e.preventDefault();
  const request = box.value.trim();
  if (!request) return;

  appendUserMsg(request);
  box.value = '';
  sendBtn.disabled = true;
  sendBtn.textContent = 'WORKING...';

  try {
    const endpoint = chatMode ? '/api/chat' : '/api/ask';
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ request })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Execution error');

    if (chatMode) {
      appendAssistantMsg(data.reply);
    } else {
      const lines = data.output.split('\\n').filter(Boolean);
      lines.forEach(line => {
        let type = 'plan';
        if (line.includes('[Result') || line.includes('[AI]')) type = 'result';
        if (line.includes('Error') || line.includes('Denied')) type = 'error';
        appendEvent(line, type);
      });
    }
  } catch (err) {
    appendEvent('Error: ' + err.message, 'error');
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = chatMode ? 'SEND' : 'RUN';
    box.focus();
  }
};

box.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    document.getElementById('form').dispatchEvent(new Event('submit'));
  }
});

loadStatus();
</script>
</body>
</html>'''


def make_handler(agent: "Agent") -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args: object) -> None:
            return

        def send_json(self, data: object, status: int = 200) -> None:
            body = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == "/":
                body = PAGE.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path == "/api/status":
                self.send_json({
                    "workspace": str(agent.workspace),
                    "api": agent.client.api_url,
                    "mode": agent.mode,
                    "max_actions": agent.max_actions,
                    "skills": list(agent.skills.keys()),
                    "allowed_commands": sorted(list(agent.allowed_commands)),
                })
                return
            if self.path == "/api/chat/history":
                self.send_json({"messages": agent.chat_memory.messages})
                return
            self.send_json({"error": "Not found"}, 404)

        def do_POST(self) -> None:
            if self.path == "/api/clear":
                with agent.operation_lock:
                    agent.clear_memory()
                self.send_json({"cleared": True})
                return
            if self.path == "/api/mode":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    data = json.loads(self.rfile.read(length))
                    mode = data.get("mode")
                    if mode in {"safe", "normal", "autonomous"}:
                        agent.mode = mode
                        agent.max_actions = 5 if mode == "safe" else (20 if mode == "autonomous" else 10)
                        self.send_json({"mode": agent.mode, "max_actions": agent.max_actions})
                    else:
                        self.send_json({"error": "Invalid mode"}, 400)
                except Exception as err:
                    self.send_json({"error": str(err)}, 400)
                return
            if self.path not in {"/api/ask", "/api/chat"}:
                self.send_json({"error": "Not found"}, 404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 20_000:
                    raise ValueError("Request must be 1-20,000 bytes.")
                request = json.loads(self.rfile.read(length))["request"]
                if not isinstance(request, str) or not request.strip():
                    raise ValueError("Request is required.")
                if self.path == "/api/chat":
                    with agent.operation_lock:
                        reply = agent.chat(request.strip())
                    self.send_json({"reply": reply})
                else:
                    output = io.StringIO()
                    with agent.operation_lock:
                        with redirect_stdout(output):
                            agent.ask(request.strip())
                    self.send_json({"output": output.getvalue()})
            except (ValueError, KeyError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)}, 400)
            except Exception as error:
                self.send_json({"error": f"Unexpected server error: {error}"}, 500)

    return Handler


def run_server(agent: "Agent", host: str, port: int) -> None:
    try:
        server = ThreadingHTTPServer((host, port), make_handler(agent))
    except OSError as error:
        print(f"Cannot start web server on {host}:{port}: {error}")
        return
    print(f"\nD_F Agent Studio is running at http://{host}:{port}")
    print("Press Ctrl+C to stop the web server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nWeb server stopped.")
    finally:
        server.server_close()
