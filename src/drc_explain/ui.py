"""Loopback-only UI for public layouts and the existing grounded agent."""

from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .agent import Agent
from .common import ROOT, read_json
from .local_provider import OllamaClient

STATIC = Path(__file__).with_name("web")


def public_cases():
    return read_json(ROOT / "eval/public/cases.json") + read_json(ROOT / "eval/public/probes.json")


def run_request(payload, agent_factory=None):
    if not isinstance(payload, dict) or set(payload) != {"case_id", "question"}:
        raise ValueError("Expected case_id and question.")
    case = next((case for case in public_cases() if case["case_id"] == payload["case_id"]), None)
    if case is None:
        raise ValueError("Unknown public case.")
    question = payload["question"]
    if not isinstance(question, str) or not question.strip() or len(question) > 8000:
        raise ValueError("Question must contain 1 to 8000 characters.")
    agent = agent_factory() if agent_factory else Agent(OllamaClient())
    result = agent.run(question, case.get("gds_path"), case.get("layout", {}).get("top_cell", "TOP"))
    trace_path = Path(result["result_path"]).with_name("tool_calls.jsonl")
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()] if trace_path.exists() else []
    return {"result": result, "tool_trace": trace}


class Handler(BaseHTTPRequestHandler):
    def send_data(self, status, value, content_type="application/json"):
        body = json.dumps(value).encode() if content_type == "application/json" else value
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def do_GET(self):
        if not self.valid_host():
            self.send_data(403, {"error": "Loopback host required."})
            return
        if self.path == "/api/cases":
            self.send_data(200, public_cases())
        elif self.path in {"/", "/app.js", "/style.css"}:
            name = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}[self.path]
            content_type = {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript; charset=utf-8", "style.css": "text/css; charset=utf-8"}[name]
            self.send_data(200, (STATIC / name).read_bytes(), content_type)
        else:
            self.send_data(404, {"error": "Not found."})

    def do_POST(self):
        origin = f"http://127.0.0.1:{self.server.server_port}"
        if not self.valid_host() or self.headers.get("Origin") != origin:
            self.send_data(403, {"error": "Same-origin request required."})
            return
        if self.path != "/api/run":
            self.send_data(404, {"error": "Not found."})
            return
        if self.headers.get("Content-Type") != "application/json":
            self.send_data(415, {"error": "JSON required."})
            return
        acquired = False
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 32768:
                raise ValueError("Invalid request size.")
            payload = json.loads(self.rfile.read(size))
            acquired = self.server.run_lock.acquire(blocking=False)
            if not acquired:
                self.send_data(409, {"error": "An agent run is already active."})
                return
            self.send_data(200, run_request(payload))
        except (ValueError, UnicodeDecodeError) as exc:
            self.send_data(400, {"error": str(exc)})
        except Exception as exc:
            self.send_data(503, {"error": str(exc), "verdict": "ERROR"})
        finally:
            if acquired:
                self.server.run_lock.release()


def main():
    parser = argparse.ArgumentParser(description="Local DRC Explain UI")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.run_lock = threading.Lock()
    print(f"DRC Explain: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()