from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from tools._shared import ROOT, err
from tools.create_ticket.tool import SENSITIVE_DATA_PATTERN


USER_FILE = ROOT / "helpdesk_data" / "users.json"
RULES_FILE = ROOT / "helpdesk_data" / "account_unlock_rules.json"
REQUEST_DIR = ROOT / "unlock_requests"
EMPLOYEE_ID_PATTERN = re.compile(r"^EMP-\d{4}$")
# Numeric codes (OTP/MFA) are never valid unlock evidence.
NUMERIC_CODE_PATTERN = re.compile(r"\b\d{6,8}\b")


def request_account_unlock(
    employee_id: str = "",
    verification_method: str = "",
    reason: str = "",
    confirmed: bool = False,
) -> dict[str, Any]:
    tool = "request_account_unlock"
    try:
        wanted_id = (employee_id or "").strip().upper()
        if not EMPLOYEE_ID_PATTERN.fullmatch(wanted_id):
            return {"tool": tool, "error": "invalid_employee_id", "message": "Expected an employee ID like EMP-1003."}
        users = json.loads(USER_FILE.read_text(encoding="utf-8"))["users"]
        employee = next((item for item in users if item["employee_id"] == wanted_id), None)
        if employee is None:
            return {"tool": tool, "employee_id": wanted_id, "error": "employee_not_found"}

        rules = json.loads(RULES_FILE.read_text(encoding="utf-8"))
        status = employee["account_status"]
        if status not in rules["unlockable_status"]:
            return {
                "tool": tool,
                "employee_id": wanted_id,
                "account_status": status,
                "error": rules["status_errors"].get(status, "account_not_unlockable"),
            }

        methods = rules["verification_methods"]
        method = (verification_method or "").strip().lower()
        if method not in methods:
            return {"tool": tool, "error": "invalid_verification_method", "allowed": sorted(methods)}

        reason_text = (reason or "").strip()
        if SENSITIVE_DATA_PATTERN.search(reason_text) or NUMERIC_CODE_PATTERN.search(reason_text):
            return {
                "tool": tool,
                "error": "restricted_sensitive_data",
                "message": "Never include passwords, MFA/OTP codes or recovery codes in an unlock request.",
            }

        payload = {
            "employee_id": wanted_id,
            "verification_method": method,
            "reason": reason_text,
            "sla_hours": methods[method]["sla_hours"],
        }
        if confirmed is not True:
            return {
                "tool": tool,
                "status": "needs_confirmation",
                "payload": payload,
                "message": "Submit the unlock request only after explicit user confirmation.",
            }

        now = datetime.now(timezone.utc)
        request_id = "UNL-" + hashlib.sha256(f"{now.isoformat()}|{wanted_id}|{method}".encode("utf-8")).hexdigest()[:8].upper()
        record = {
            "request_id": request_id,
            **payload,
            "status": "pending_verification",
            "created_at": now.isoformat(),
            "note": rules["after_submit"],
            "source": "educational_local_mock",
        }
        REQUEST_DIR.mkdir(parents=True, exist_ok=True)
        path = REQUEST_DIR / f"{request_id}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "tool": tool,
            "status": "pending_verification",
            "request_id": request_id,
            "sla_hours": payload["sla_hours"],
            "account_status": status,
            "path": str(path),
        }
    except Exception as exc:
        return err(tool, exc)
