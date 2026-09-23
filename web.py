"""Dependency-free local browser UI for D_F AI Agent Studio."""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent import Agent


PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>D_F Agent Studio</title><style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Fraunces:opsz,wght@9..144,600;9..144,700&display=swap');
:root{--ink:#17201d;--paper:#e8e4d5;--lime:#d7f264;--line:#8c9186;--muted:#67706a;--signal:#f15a39}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:'DM Mono',monospace}.shell{max-width:1160px;margin:auto;min-height:100vh;padding:25px;display:grid;grid-template-columns:265px 1fr;gap:18px}.side{border:1px solid var(--ink);padding:21px;display:flex;flex-direction:column;background:#dedacb}.mark{font-family:Fraunces,serif;font-size:29px;line-height:.9}.mark small{font:11px 'DM Mono';display:block;margin-top:13px;letter-spacing:.1em}.rule{border:0;border-top:1px solid var(--line);width:100%;margin:29px 0}.meta{font-size:11px;color:var(--muted);line-height:1.75}.dot{color:var(--signal);font-size:18px}.hint{margin-top:auto;font-size:10px;line-height:1.65;color:var(--muted)}.main{display:flex;flex-direction:column;min-height:calc(100vh - 50px);border:1px solid var(--ink);background:#f3f0e5}.top{display:flex;justify-content:space-between;align-items:center;padding:15px 18px;border-bottom:1px solid var(--ink);font-size:11px}.live{padding:5px 8px;background:var(--lime);border:1px solid var(--ink);font-size:10px}.feed{padding:25px;flex:1;min-height:420px;max-height:calc(100vh - 207px);overflow:auto}.intro{max-width:640px;animation:rise .55s both}.eyebrow{font-size:11px;letter-spacing:.13em;color:var(--muted)}h1{font:600 clamp(34px,5vw,65px)/.98 Fraunces,serif;letter-spacing:-.04em;margin:15px 0 18px}.intro p{font-size:13px;line-height:1.7;max-width:540px}.examples{display:flex;flex-wrap:wrap;gap:8px;margin-top:25px}.examples button{font:11px 'DM Mono';padding:9px;border:1px solid var(--line);background:transparent;color:var(--ink);cursor:pointer;text-align:left}.examples button:hover{background:var(--lime);border-color:var(--ink)}.event{border-left:3px solid var(--ink);padding:7px 11px;margin-bottom:12px;font-size:12px;line-height:1.6;white-space:pre-wrap;animation:rise .25s both}.event.plan{border-left-color:var(--signal)}.event.result{border-left-color:#6c8f15}.compose{border-top:1px solid var(--ink);padding:14px;display:flex;gap:10px;background:#dedacb}textarea{font:13px/1.45 'DM Mono';color:var(--ink);background:#f6f2e7;border:1px solid var(--ink);resize:none;height:58px;padding:10px;flex:1}button.send{background:var(--ink);color:var(--paper);border:1px solid var(--ink);padding:0 19px;font:11px 'DM Mono';cursor:pointer}button.send:hover{background:var(--signal)}button:disabled{opacity:.5;cursor:wait}@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}@media(max-width:700px){.shell{padding:0;display:block}.side{min-height:auto;border:none;border-bottom:1px solid var(--ink)}.hint{display:none}.main{min-height:calc(100vh - 194px);border:none}.feed{max-height:none}.top{font-size:10px}}
</style></head><body><div class="shell"><aside class="side"><div class="mark">D_F<br>AGENT<small>STUDIO / LOCAL</small></div><hr class="rule"><div class="meta"><span class="dot">●</span> LOCAL SESSION<br><span id="workspace">Loading workspace…</span><br><br>LM STUDIO<br><span id="api">Loading…</span></div><p class="hint">Actions are workspace-scoped. The model can only use actions enabled in <code>commands.txt</code>.</p></aside><main class="main"><header class="top"><span>OPERATIONS CONSOLE</span><span class="live">● READY</span></header><section class="feed" id="feed"><div class="intro"><div class="eyebrow">YOUR LOCAL BUILD PARTNER</div><h1>What shall we make?</h1><p>Describe the result. The agent will plan its work, then report each file, folder, and Python action as it happens.</p><div class="examples"><button>Create a Python CLI calculator with tests.</button><button>Build a responsive portfolio website in a new folder.</button><button>Read this project and explain its structure.</button></div></div></section><form class="compose" id="form"><textarea id="request" required placeholder="Create something…" aria-label="Request to agent"></textarea><button class="send" id="send">RUN ↵</button></form></main></div><script>
const q=s=>document.querySelector(s),feed=q('#feed'),send=q('#send'),box=q('#request');
function event(t,c=''){let e=document.createElement('div');e.className='event '+c;e.textContent=t;feed.append(e);feed.scrollTop=feed.scrollHeight}
fetch('/api/status').then(r=>r.json()).then(x=>{q('#workspace').textContent=x.workspace;q('#api').textContent=x.api}).catch(()=>event('Cannot read agent status.','plan'));
document.querySelectorAll('.examples button').forEach(b=>b.onclick=()=>{box.value=b.textContent;box.focus()});
q('#form').onsubmit=async e=>{e.preventDefault();let request=box.value.trim();if(!request)return;event('REQUEST\n'+request,'plan');box.value='';send.disabled=true;send.textContent='WORKING…';try{let r=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request})});let x=await r.json();if(!r.ok)throw Error(x.error||'Request failed');x.output.split('\n').filter(Boolean).forEach(line=>event(line,line.includes('[Result]')?'result':''))}catch(err){event('ERROR\n'+err.message,'plan')}finally{send.disabled=false;send.textContent='RUN ↵';box.focus()}};
</script></body></html>'''


def make_handler(agent: "Agent") -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args: object) -> None:
            return  # Activity belongs in the UI, not noisy HTTP logs.

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
                self.end_headers(); self.wfile.write(body); return
            if self.path == "/api/status":
                self.send_json({"workspace": str(agent.workspace), "api": agent.client.api_url}); return
            self.send_json({"error": "Not found"}, 404)

        def do_POST(self) -> None:
            if self.path != "/api/ask": self.send_json({"error": "Not found"}, 404); return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 20_000: raise ValueError("Request must be 1–20,000 bytes.")
                request = json.loads(self.rfile.read(length))["request"]
                if not isinstance(request, str) or not request.strip(): raise ValueError("Request is required.")
                output = io.StringIO()
                with redirect_stdout(output): agent.ask(request.strip())
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
    try: server.serve_forever()
    except KeyboardInterrupt: print("\nWeb server stopped.")
    finally: server.server_close()
