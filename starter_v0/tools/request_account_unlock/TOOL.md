---
name: request_account_unlock
track: bonus
kind: action
provider: local_unlock_request_store
requires_env: []
inputs: [employee_id, verification_method, reason, confirmed]
outputs: [status, request_id, sla_hours, account_status, path]
side_effect: local_file_write
requires_confirmation: true
---
# request_account_unlock

Team-built bonus tool. Submits a mock account-unlock request for a **locked**
fictional employee under `unlock_requests/` (gitignored). It never changes
`users.json`: the account stays locked until the chosen verification finishes.

Rules come from `helpdesk_data/account_unlock_rules.json`:

- `employee_id` must match `EMP-NNNN` and exist → else `invalid_employee_id` / `employee_not_found`.
- Only `locked` accounts are unlockable; `active`, `disabled`, `password_expired` return a specific error.
- `verification_method` must be an approved method (`manager_approval`, `service_desk_callback`, `in_person_badge`) → else `invalid_verification_method`.
- `reason` containing passwords, tokens, MFA/OTP/recovery codes or 6–8 digit codes → `restricted_sensitive_data`.
- Writes nothing and returns `needs_confirmation` with the payload unless `confirmed` is exactly `true`.

Smoke test: `python -m unittest tests.test_request_account_unlock` from `starter_v0/`.
