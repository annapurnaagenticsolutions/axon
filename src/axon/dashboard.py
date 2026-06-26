"""AXON Dashboard web UI — real-time observability dashboard.

Serves a single-page web dashboard showing live metrics, traces, and
agent activity from the AXON runtime. Uses the existing metrics collector
and trace infrastructure.
"""

from __future__ import annotations

import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse, parse_qs


_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AXON Dashboard</title>
<style>
  :root {
    --bg: #0d1117; --panel: #161b22; --border: #30363d;
    --text: #c9d1d9; --muted: #8b949e; --accent: #58a6ff;
    --green: #3fb950; --red: #f85149; --yellow: #d29922;
    --font: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    --mono: 'SF Mono', 'Cascadia Code', Consolas, monospace;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: var(--bg); color: var(--text); font-family: var(--font); padding: 20px; }
  h1 { font-size: 1.5rem; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
  h1 .dot { width: 10px; height: 10px; border-radius: 50%; background: var(--green); animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; margin-bottom: 20px; }
  .card { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 16px; }
  .card h2 { font-size: 0.85rem; text-transform: uppercase; color: var(--muted); margin-bottom: 12px; letter-spacing: 0.5px; }
  .stat { display: flex; justify-content: space-between; padding: 4px 0; font-size: 0.9rem; }
  .stat .val { font-family: var(--mono); color: var(--accent); font-weight: 600; }
  .stat .val.green { color: var(--green); }
  .stat .val.red { color: var(--red); }
  .stat .val.yellow { color: var(--yellow); }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  th { text-align: left; padding: 6px 8px; color: var(--muted); border-bottom: 1px solid var(--border); }
  td { padding: 6px 8px; border-bottom: 1px solid var(--border); font-family: var(--mono); }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; }
  .badge.ok { background: rgba(63,185,80,.15); color: var(--green); }
  .badge.err { background: rgba(248,81,73,.15); color: var(--red); }
  #trace-log { max-height: 400px; overflow-y: auto; }
  .empty { color: var(--muted); text-align: center; padding: 20px; }
</style>
</head>
<body>
<h1><span class="dot"></span> AXON Runtime Dashboard</h1>
<div class="grid">
  <div class="card"><h2>Overview</h2><div id="overview"><div class="empty">Connecting…</div></div></div>
  <div class="card"><h2>Cache Stats</h2><div id="cache"><div class="empty">—</div></div></div>
  <div class="card"><h2>Provider Calls</h2><div id="providers"><div class="empty">—</div></div></div>
  <div class="card"><h2>Tool Dispatches</h2><div id="tools"><div class="empty">—</div></div></div>
</div>
<div class="card" style="margin-bottom:16px"><h2>Recent Events</h2><div id="trace-log"><div class="empty">No events</div></div></div>
<script>
async function poll() {
  try {
    const r = await fetch('/api/dashboard');
    const d = await r.json();
    let ov = '<div class="stat"><span>Uptime</span><span class="val">' + (d.uptime_s || 0).toFixed(0) + 's</span></div>';
    if (d.metrics) {
      const m = d.metrics;
      for (const [k,v] of Object.entries(m.counters || {})) {
        ov += '<div class="stat"><span>' + k + '</span><span class="val">' + v + '</span></div>';
      }
    }
    document.getElementById('overview').innerHTML = ov;
    if (d.metrics && d.metrics.provider_calls) {
      let h = '<table><tr><th>Model</th><th>Latency</th><th>Status</th></tr>';
      d.metrics.provider_calls.slice(-10).forEach(c => {
        h += '<tr><td>' + c.model + '</td><td>' + (c.latency_ms||0).toFixed(0) + 'ms</td><td><span class="badge ' + (c.success?'ok':'err') + '">' + (c.success?'OK':'ERR') + '</span></td></tr>';
      });
      h += '</table>';
      document.getElementById('providers').innerHTML = h;
    }
    if (d.metrics && d.metrics.tool_dispatches) {
      let h = '<table><tr><th>Tool</th><th>Latency</th><th>Status</th></tr>';
      d.metrics.tool_dispatches.slice(-10).forEach(t => {
        h += '<tr><td>' + t.tool_name + '</td><td>' + (t.latency_ms||0).toFixed(0) + 'ms</td><td><span class="badge ' + (t.success?'ok':'err') + '">' + (t.success?'OK':'ERR') + '</span></td></tr>';
      });
      h += '</table>';
      document.getElementById('tools').innerHTML = h;
    }
    if (d.events && d.events.length) {
      let h = '<table><tr><th>Time</th><th>Event</th><th>Detail</th></tr>';
      d.events.slice(-50).forEach(e => {
        h += '<tr><td>' + new Date(e.ts).toLocaleTimeString() + '</td><td>' + e.type + '</td><td>' + (e.detail||'') + '</td></tr>';
      });
      h += '</table>';
      document.getElementById('trace-log').innerHTML = h;
    }
  } catch(e) { document.getElementById('overview').innerHTML = '<div class="empty">Error: ' + e.message + '</div>'; }
}
poll();
setInterval(poll, 2000);
</script>
</body>
</html>"""


class DashboardServer:
    """HTTP server serving the AXON dashboard."""

    def __init__(self, port: int = 8050, host: str = "127.0.0.1") -> None:
        self.port = port
        self.host = host
        self._start_time = time.time()
        self._events: list[dict[str, Any]] = []
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def add_event(self, event_type: str, detail: str = "") -> None:
        self._events.append({"ts": time.time(), "type": event_type, "detail": detail})
        if len(self._events) > 500:
            self._events = self._events[-200:]

    def _get_dashboard_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {"uptime_s": time.time() - self._start_time, "events": self._events[-50:]}
        try:
            from axon.metrics import get_metrics_collector
            data["metrics"] = get_metrics_collector().to_dict()
        except Exception:
            pass
        return data

    def _handle(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlparse(handler.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            handler.send_response(200)
            handler.send_header("Content-Type", "text/html")
            handler.end_headers()
            handler.wfile.write(_DASHBOARD_HTML.encode())
        elif parsed.path == "/api/dashboard":
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Access-Control-Allow-Origin", "*")
            handler.end_headers()
            handler.wfile.write(json.dumps(self._get_dashboard_data()).encode())
        else:
            handler.send_response(404)
            handler.end_headers()

    def start(self) -> None:
        server = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                server._handle(self)
            def log_message(self, *args):
                pass
        self._server = HTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None


def serve_dashboard(port: int = 8050, host: str = "127.0.0.1") -> DashboardServer:
    """Start the AXON dashboard web UI server."""
    server = DashboardServer(port=port, host=host)
    server.start()
    print(f"AXON Dashboard running at http://{host}:{port}")
    return server
