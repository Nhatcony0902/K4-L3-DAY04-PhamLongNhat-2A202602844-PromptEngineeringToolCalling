"""Code-level confirmation guard for write-action tools (v5).

Prompt rules alone let the model set confirmed=true from injected text (A03, A04,
A10, A11, U08). This guard decides from the real conversation instead of trusting
the model's flag. It applies to every tool whose TOOL.md declares
requires_confirmation: true; rules live in helpdesk_data/confirmation_guard.json.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tools import tool_metadata

RULES = json.loads((Path(__file__).parent / "helpdesk_data" / "confirmation_guard.json").read_text(encoding="utf-8"))


def _has_any(text: str, words: list[str]) -> bool:
    """Whole-word match for words, plain substring match for symbols like '<' or '{'."""
    return any(
        re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text) if word[:1].isalnum() else word in text
        for word in words
    )


def confirmation_problem(tool_name: str, args: dict[str, Any], messages: list[dict[str, str]]) -> str | None:
    """Return why a confirmed write call is not backed by the conversation, or None if it is."""
    if args.get("confirmed") is not True or not tool_metadata(tool_name).get("requires_confirmation"):
        return None
    dialog = [m for m in messages if m.get("role") in ("user", "assistant")]
    if not dialog or dialog[-1]["role"] != "user":
        return "latest_message_not_from_user"
    latest = dialog[-1]["content"].lower()
    previous_assistant = next((m["content"].lower() for m in reversed(dialog[:-1]) if m["role"] == "assistant"), None)
    if previous_assistant is None or dialog[-2]["role"] != "assistant":
        return "no_payload_shown_in_previous_assistant_turn"
    if _has_any(latest, RULES["injection_markers"]):
        return "confirmation_contains_markup_or_tool_syntax"
    if _has_any(latest, RULES["negative"]) or not _has_any(latest, RULES["affirmative"]):
        return "latest_user_message_is_not_a_plain_confirmation"
    for key in RULES["id_args"]:
        value = str(args.get(key) or "").strip().lower()
        if value and value not in previous_assistant:
            return f"{key}_not_in_shown_payload"
    return None


def guarded_result(tool_name: str, args: dict[str, Any], problem: str) -> dict[str, Any]:
    return {
        "tool": tool_name,
        "status": "needs_confirmation",
        "guard": "confirmation_guard",
        "blocked_reason": problem,
        "message": "Not executed: show the exact payload and get an explicit yes from the user first.",
    }
