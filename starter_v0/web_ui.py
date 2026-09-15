"""Local web chat UI for the Helpdesk agent (stdlib only).

Two pages share the agent/tool loop and transcript format of chat.py:
- "/"        chat with the current artifacts;
- "/compare" send one message to several logged versions (v0-v3...) side by side,
             rebuilt from git by version_catalog.py. Write actions are dry-run there.
"""
from __future__ import annotations

import argparse
import json
import os
import threading
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from chat import ARTIFACTS_DIR, ROOT, execute_tool_call, now_iso, run_model_tool_loop, safe_slug, trim_history, write_transcript
from providers import make_provider
from providers.base import ToolCall
from tools import load_tool_declarations, to_openai_tools, tool_metadata
from version_catalog import load_catalog
from versioning import ArtifactVersion, artifact_version_dict, build_artifact_version

STATIC = {"/": ("web_ui.html", "text/html"), "/compare": ("web_compare.html", "text/html"), "/web-ui.js": ("web-ui.js", "text/javascript"), "/web_ui.css": ("web_ui.css", "text/css")}


def dry_run_executor(call: ToolCall) -> dict[str, Any]:
    """Execute read tools normally; never perform a confirmed side-effect tool call."""
    side_effect = tool_metadata(call.name).get("side_effect")
    if side_effect and call.args.get("confirmed") is True:
        result = {"tool": call.name, "status": "dry_run_not_executed", "dry_run": True,
                  "message": f"Compare mode: {side_effect} skipped; the real UI would execute this call."}
        return {"tool": call.name, "args": call.args, "result": result}
    return execute_tool_call(call)


class Conversation:
    """One conversation thread for one artifact version."""

    def __init__(self, args: argparse.Namespace, provider: Any, version: ArtifactVersion,
                 system_prompt: str, declarations: list[dict[str, Any]], executor: Any = None) -> None:
        self.args, self.provider, self.version = args, provider, version
        self.system_prompt = system_prompt
        self.tools = to_openai_tools(declarations)
        self.executor = executor
        self.history: list[dict[str, str]] = []

    def send(self, user_text: str, turn_index: int) -> dict[str, Any]:
        turn: dict[str, Any] = {"turn_index": turn_index, "started_at": now_iso(), "user": user_text,
                                "artifact_version": self.version.artifact_version,
                                "status": "started", "assistant_text": None, "rounds": [], "tool_events": []}
        messages = [{"role": "system", "content": self.system_prompt},
                    *trim_history(self.history, self.args.history_window), {"role": "user", "content": user_text}]
        try:
            result = run_model_tool_loop(provider=self.provider, messages=messages, tools=self.tools, model=self.args.model,
                                         max_tool_rounds=self.args.max_tool_rounds, executor=self.executor)
            turn.update(result)
            self.history += [{"role": "user", "content": user_text}, {"role": "assistant", "content": result["assistant_text"]}]
        except Exception as exc:  # surface provider errors in the UI, never hide them
            turn.update({"status": "provider_error", "error": f"{type(exc).__name__}: {exc}"})
        turn["ended_at"] = now_iso()
        return turn


class App:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.provider = make_provider(args.provider)
        self.model = args.model or getattr(self.provider, "default_model", None)
        self.version = build_artifact_version(args.version, args.system_prompt, args.tools)
        self.lock = threading.Lock()
        self.reset_chat()
        self.reset_compare()

    def _transcript(self, kind: str, label: str, extra: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
        transcript_id = "_".join([kind, safe_slug(label), safe_slug(self.args.provider), datetime.now().strftime("%Y%m%dT%H%M%S%f")])
        body = {"transcript_id": transcript_id, **extra, "provider": self.args.provider, "model": self.model,
                "history_window": self.args.history_window, "max_tool_rounds": self.args.max_tool_rounds,
                "created_at": now_iso(), "updated_at": now_iso(), "turns": []}
        return self.args.transcripts_dir / f"{transcript_id}.transcript.json", body

    def _rel(self, path: Path) -> str:
        return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)

    def reset_chat(self) -> None:
        self.chat = Conversation(self.args, self.provider, self.version, self.args.system_prompt.read_text(encoding="utf-8"),
                                 load_tool_declarations(self.args.tools))
        self.chat_path, self.chat_transcript = self._transcript("ui", self.args.version, {
            **artifact_version_dict(self.version), "system_prompt": str(self.args.system_prompt),
            "tools": str(self.args.tools), "interface": "web_ui"})

    def reset_compare(self, selected: list[str] | None = None) -> None:
        catalog, self.catalog_errors = load_catalog()
        self.catalog = {item.version.version: item for item in catalog}
        chosen = [name for name in (selected or list(self.catalog)) if name in self.catalog]
        self.compare = {name: Conversation(self.args, self.provider, self.catalog[name].version, self.catalog[name].system_prompt,
                                           self.catalog[name].tool_declarations, dry_run_executor) for name in chosen}
        self.compare_path, self.compare_transcript = self._transcript("compare", "-".join(chosen) or "none", {
            "interface": "web_compare", "write_actions": "dry_run",
            "versions": {name: {**artifact_version_dict(self.catalog[name].version), "prompt_commit": self.catalog[name].prompt_commit,
                                "tools_commit": self.catalog[name].tools_commit} for name in chosen}})

    def info(self) -> dict[str, Any]:
        key_env = getattr(self.provider, "api_key_env", None)
        return {"artifact_version": self.version.artifact_version, "provider": self.args.provider, "model": self.model,
                "api_key_env": key_env, "api_key_present": bool(key_env and os.getenv(key_env)),
                "transcript": self._rel(self.chat_path), "compare_transcript": self._rel(self.compare_path)}

    def versions(self) -> dict[str, Any]:
        return {"versions": [{"version": name, "artifact_version": item.version.artifact_version, "prompt_commit": item.prompt_commit,
                              "tools_commit": item.tools_commit, "selected": name in self.compare} for name, item in self.catalog.items()],
                "errors": self.catalog_errors}

    def send_chat(self, text: str) -> dict[str, Any]:
        turn = self.chat.send(text, len(self.chat_transcript["turns"]) + 1)
        self.chat_transcript["turns"].append(turn)
        write_transcript(self.chat_path, self.chat_transcript)
        return turn

    def send_compare(self, text: str) -> dict[str, Any]:
        index = len(self.compare_transcript["turns"]) + 1
        with ThreadPoolExecutor(max_workers=max(1, len(self.compare))) as pool:
            futures = {name: pool.submit(conv.send, text, index) for name, conv in self.compare.items()}
            results = {name: future.result() for name, future in futures.items()}
        self.compare_transcript["turns"].append({"turn_index": index, "user": text, "results": results})
        write_transcript(self.compare_path, self.compare_transcript)
        return results


def make_handler(app: App) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, payload: Any, status: int = 200) -> None:
            self._send(status, json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"), "application/json")

        def do_GET(self) -> None:
            if self.path in STATIC:
                name, content_type = STATIC[self.path]
                self._send(200, (Path(__file__).parent / name).read_bytes(), content_type)
            elif self.path == "/api/info":
                self._json(app.info())
            elif self.path == "/api/versions":
                self._json(app.versions())
            else:
                self._json({"error": "not_found"}, 404)

        def do_POST(self) -> None:
            try:
                payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            except json.JSONDecodeError:
                self._json({"error": "invalid_json"}, 400)
                return
            message = str(payload.get("message", "")).strip()
            with app.lock:
                if self.path in ("/api/chat", "/api/compare") and not message:
                    self._json({"error": "empty_message"}, 400)
                elif self.path == "/api/chat":
                    self._json({"turn": app.send_chat(message), "info": app.info()})
                elif self.path == "/api/reset":
                    app.reset_chat()
                    self._json({"info": app.info()})
                elif self.path == "/api/compare":
                    self._json({"results": app.send_compare(message), "info": app.info()})
                elif self.path == "/api/compare/reset":
                    app.reset_compare([str(v) for v in payload.get("versions", [])] or None)
                    self._json({"info": app.info(), **app.versions()})
                else:
                    self._json({"error": "not_found"}, 404)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Local web chat UI for the IT Helpdesk agent.")
    parser.add_argument("--provider", choices=["openrouter", "openai", "anthropic", "gemini"], required=True)
    parser.add_argument("--model", default=None)
    parser.add_argument("--version", required=True, help="Label for the current artifacts, e.g. v4.")
    parser.add_argument("--system-prompt", type=Path, default=ARTIFACTS_DIR / "system_prompt.md")
    parser.add_argument("--tools", type=Path, default=ARTIFACTS_DIR / "tools.yaml")
    parser.add_argument("--transcripts-dir", type=Path, default=ROOT / "transcripts")
    parser.add_argument("--history-window", type=int, default=5)
    parser.add_argument("--max-tool-rounds", type=int, default=4)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    app = App(args)
    url = f"http://127.0.0.1:{args.port}/"
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(app))
    except OSError as exc:
        raise SystemExit(f"Cannot listen on port {args.port} ({exc}). Try --port 8766.") from exc
    print(f"Helpdesk web UI: {url}  artifact_version={app.version.artifact_version}", flush=True)
    print(f"Compare versions: {url}compare  ({', '.join(app.catalog) or 'none'})", flush=True)
    for error in app.catalog_errors:
        print(f"WARNING: {error}", flush=True)
    if not app.info()["api_key_present"]:
        print(f"WARNING: {app.info()['api_key_env']} is not set in starter_v0/.env; every turn will show provider_error.", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
