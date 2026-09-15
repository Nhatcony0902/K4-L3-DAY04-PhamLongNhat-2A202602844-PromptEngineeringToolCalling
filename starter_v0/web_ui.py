"""Local web chat UI for the Helpdesk agent (stdlib only).

Reuses the agent/tool loop and transcript format from chat.py and shows, for
every turn, the artifact version, each tool call, its input args and its
result or error.
"""
from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from chat import (
    ARTIFACTS_DIR,
    ROOT,
    now_iso,
    run_model_tool_loop,
    safe_slug,
    trim_history,
    write_transcript,
)
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version

PAGE_PATH = Path(__file__).parent / "web_ui.html"


class ChatSession:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.system_prompt = args.system_prompt.read_text(encoding="utf-8")
        self.tools = to_openai_tools(load_tool_declarations(args.tools))
        self.provider = make_provider(args.provider)
        self.model = args.model or getattr(self.provider, "default_model", None)
        self.version = build_artifact_version(args.version, args.system_prompt, args.tools)
        self.lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
        transcript_id = "_".join(["ui", safe_slug(self.args.version), safe_slug(self.args.provider), stamp])
        self.path = self.args.transcripts_dir / f"{transcript_id}.transcript.json"
        self.history: list[dict[str, str]] = []
        self.transcript: dict[str, Any] = {
            "transcript_id": transcript_id,
            **artifact_version_dict(self.version),
            "provider": self.args.provider,
            "model": self.model,
            "system_prompt": str(self.args.system_prompt),
            "tools": str(self.args.tools),
            "history_window": self.args.history_window,
            "max_tool_rounds": self.args.max_tool_rounds,
            "interface": "web_ui",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "turns": [],
        }

    def info(self) -> dict[str, Any]:
        return {
            "artifact_version": self.version.artifact_version,
            "provider": self.args.provider,
            "model": self.model,
            "transcript": str(self.path.relative_to(ROOT)) if self.path.is_relative_to(ROOT) else str(self.path),
        }

    def send(self, user_text: str) -> dict[str, Any]:
        turn: dict[str, Any] = {
            "turn_index": len(self.transcript["turns"]) + 1,
            "started_at": now_iso(),
            "user": user_text,
            "status": "started",
            "assistant_text": None,
            "rounds": [],
            "tool_events": [],
        }
        messages = [
            {"role": "system", "content": self.system_prompt},
            *trim_history(self.history, self.args.history_window),
            {"role": "user", "content": user_text},
        ]
        try:
            result = run_model_tool_loop(
                provider=self.provider,
                messages=messages,
                tools=self.tools,
                model=self.args.model,
                max_tool_rounds=self.args.max_tool_rounds,
            )
            turn.update(result)
            self.history.append({"role": "user", "content": user_text})
            self.history.append({"role": "assistant", "content": result["assistant_text"]})
        except Exception as exc:  # surface provider errors in the UI, never hide them
            turn.update({"status": "provider_error", "error": f"{type(exc).__name__}: {exc}"})
        turn["ended_at"] = now_iso()
        self.transcript["turns"].append(turn)
        write_transcript(self.path, self.transcript)
        return turn


def make_handler(session: ChatSession) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, payload: Any, status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            self._send(status, body, "application/json; charset=utf-8")

        def do_GET(self) -> None:
            if self.path == "/":
                self._send(200, PAGE_PATH.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/api/info":
                self._json(session.info())
            else:
                self._json({"error": "not_found"}, 404)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._json({"error": "invalid_json"}, 400)
                return
            with session.lock:
                if self.path == "/api/chat":
                    message = str(payload.get("message", "")).strip()
                    if not message:
                        self._json({"error": "empty_message"}, 400)
                        return
                    self._json({"turn": session.send(message), "info": session.info()})
                elif self.path == "/api/reset":
                    session.reset()
                    self._json({"info": session.info()})
                else:
                    self._json({"error": "not_found"}, 404)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Local web chat UI for the IT Helpdesk agent.")
    parser.add_argument("--provider", choices=["openrouter", "openai", "anthropic", "gemini"], required=True)
    parser.add_argument("--model", default=None)
    parser.add_argument("--version", required=True, help="Artifact version label, e.g. v3.")
    parser.add_argument("--system-prompt", type=Path, default=ARTIFACTS_DIR / "system_prompt.md")
    parser.add_argument("--tools", type=Path, default=ARTIFACTS_DIR / "tools.yaml")
    parser.add_argument("--transcripts-dir", type=Path, default=ROOT / "transcripts")
    parser.add_argument("--history-window", type=int, default=5)
    parser.add_argument("--max-tool-rounds", type=int, default=4)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    session = ChatSession(args)
    url = f"http://127.0.0.1:{args.port}/"
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(session))
    print(f"Helpdesk web UI: {url}  artifact_version={session.version.artifact_version}")
    print("Press Ctrl+C to stop.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print(f"Last transcript: {session.path}")


if __name__ == "__main__":
    main()
