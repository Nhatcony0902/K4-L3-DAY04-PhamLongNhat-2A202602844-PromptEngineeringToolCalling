"""Smoke tests for the team-built request_account_unlock bonus tool.

Run from starter_v0/: python -m unittest tests.test_request_account_unlock
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import TOOL_FUNCTIONS, load_tool_declarations, tool_metadata
from tools.request_account_unlock import tool as unlock_tool

ROOT = Path(__file__).resolve().parents[1]
LOCKED = "EMP-1003"


class RequestAccountUnlockTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        patcher = mock.patch.object(unlock_tool, "REQUEST_DIR", Path(self.tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)
        self.users_before = (ROOT / "helpdesk_data" / "users.json").read_bytes()

    def call(self, **kwargs):
        return unlock_tool.request_account_unlock(**kwargs)

    def written(self) -> list[Path]:
        return list(Path(self.tmp.name).glob("*.json"))

    def test_invalid_and_unknown_employee(self) -> None:
        self.assertEqual(self.call(employee_id="Sales", verification_method="manager_approval")["error"], "invalid_employee_id")
        self.assertEqual(self.call(employee_id="EMP-9999", verification_method="manager_approval")["error"], "employee_not_found")

    def test_non_locked_statuses_rejected(self) -> None:
        cases = {"EMP-1001": "account_not_locked", "EMP-1007": "account_disabled_contact_hr", "EMP-1009": "use_password_reset_workflow"}
        for employee_id, error in cases.items():
            with self.subTest(employee_id=employee_id):
                result = self.call(employee_id=employee_id, verification_method="manager_approval", confirmed=True)
                self.assertEqual(result["error"], error)
        self.assertEqual(self.written(), [])

    def test_invalid_verification_method(self) -> None:
        result = self.call(employee_id=LOCKED, verification_method="mfa_code", confirmed=True)
        self.assertEqual(result["error"], "invalid_verification_method")
        self.assertIn("manager_approval", result["allowed"])

    def test_sensitive_reason_rejected(self) -> None:
        for reason in ["password=Summer2026!", "mã OTP 482913", "otp: 123456"]:
            with self.subTest(reason=reason):
                result = self.call(employee_id=LOCKED, verification_method="service_desk_callback", reason=reason, confirmed=True)
                self.assertEqual(result["error"], "restricted_sensitive_data")
        self.assertEqual(self.written(), [])

    def test_needs_confirmation_writes_nothing(self) -> None:
        result = self.call(employee_id=LOCKED, verification_method="manager_approval", reason="nhập sai nhiều lần")
        self.assertEqual(result["status"], "needs_confirmation")
        self.assertEqual(result["payload"]["sla_hours"], 4)
        self.assertEqual(self.written(), [])
        self.assertEqual(self.call(employee_id=LOCKED, verification_method="manager_approval", confirmed="true")["status"], "needs_confirmation")

    def test_confirmed_request_written_and_account_untouched(self) -> None:
        result = self.call(employee_id="emp-1003", verification_method="in_person_badge", reason="quên mật khẩu", confirmed=True)
        self.assertEqual(result["status"], "pending_verification")
        self.assertTrue(result["request_id"].startswith("UNL-"))
        [path] = self.written()
        record = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual((record["employee_id"], record["sla_hours"]), (LOCKED, 1))
        self.assertEqual((ROOT / "helpdesk_data" / "users.json").read_bytes(), self.users_before)

    def test_registry_declaration_and_metadata_match(self) -> None:
        names = {item["name"] for item in load_tool_declarations(ROOT / "artifacts" / "tools.yaml")}
        self.assertIn("request_account_unlock", names)
        self.assertIs(TOOL_FUNCTIONS["request_account_unlock"], unlock_tool.request_account_unlock)
        meta = tool_metadata("request_account_unlock")
        self.assertEqual((meta["track"], meta["side_effect"], meta["requires_confirmation"]), ("bonus", "local_file_write", True))


if __name__ == "__main__":
    unittest.main()
