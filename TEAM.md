# TEAM — Day04, K4-L3B

**Làm nhóm.** Mỗi người tự viết và commit phần INDIVIDUAL của mình.

## Thông tin bài nộp

- Tên nhóm: Làm cá nhân (1 thành viên)
- Người đại diện / MSSV: Phạm Long Nhật / 2A202602844
- Tên repo: `K4-L3B-DAY04-PhamLongNhat-2A202602844-Prompt-Engineering-Tool-Calling-Labs`
- URL repo, nhánh nộp, commit chốt: https://github.com/Nhatcony0902/K4-L3B-DAY04-PhamLongNhat-2A202602844-Prompt-Engineering-Tool-Calling-Labs · nhánh `main` · commit chốt: _(điền sau commit cuối)_
- Deadline áp dụng và link thông báo đổi hạn nếu có: 23:59 ngày làm lab, Asia/Ho_Chi_Minh (mặc định); chưa có thông báo đổi hạn

## Thành viên

| Họ và tên | MSSV | GitHub | Vai trò và công việc | File/commit/PR |
|---|---|---|---|---|
| Phạm Long Nhật | 2A202602844 | [Nhatcony0902](https://github.com/Nhatcony0902) | Toàn bộ: chạy eval v0–v3, phân tích lỗi, sửa `system_prompt.md` và `tools.yaml`, version log, report | `3cc92c1`, `66fe80e`, `37956c2`, `1d344fa`, `41e30bd`, `26d69f0` |

## Nhận xét chung

- Kết quả và bằng chứng: bộ base 30 case, case_accuracy 0.70 (v0) → 0.767 (v1) → 0.867 (v2) → 1.0 (v3); mọi run `provider_error_cases = 0`, `measured_cases = 30`. Run trong `starter_v0/runs/`, bảng so sánh ở [REPORT.md § B1](starter_v0/artifacts/REPORT.md#b1-version-evidence), log ở [version_log.csv](starter_v0/artifacts/version_log.csv).
- Thay đổi hiệu quả nhất: v3 — làm rõ mô tả tham số trong `tools.yaml` sửa được H04/H19 mà quy tắc chung trong prompt v2 không sửa được (trace v1 và v2 giống hệt).
- Giới hạn còn lại: 30/30 là một lần chạy trên đúng bộ dùng để tìm lỗi (rủi ro overfit); M06/H17 dao động giữa các version; `create_ticket` vẫn tin cờ `confirmed` do model gửi (v0 đã ghi ticket thật ở H12).
- Cách phân công và tích hợp: làm cá nhân; mỗi version tách commit artifact và commit evidence để đối chiếu hash.

## INDIVIDUAL

### Phạm Long Nhật — 2A202602844

- Phần việc và file/commit/PR: chạy v0–v3 và phân tích 9 case fail của v0 (`3cc92c1`, `1d344fa`, `26d69f0`); prompt v1 xác nhận write action (`66fe80e`); prompt v2 không đoán ID/enum (`37956c2`); `tools.yaml` v3 (`41e30bd`); `version_log.csv`, `REPORT.md`.
- Quyết định, khó khăn và cách xử lý:
  - Lỗi 401 khi preflight: key trong `OPENROUTER_API_KEY` không phải key OpenRouter → thay key đúng.
  - Thứ tự sửa: ưu tiên an toàn (boundary ticket) ở v1 trước các lỗi routing.
  - v1 làm M06 regress; v2 không sửa được H04/H19 → chuyển hướng dẫn vào mô tả tham số ở v3.
  - _(tự bổ sung/chỉnh theo trải nghiệm của bạn)_
- Điều đã học: _(tự viết — RULES.md không cho dùng AI viết phần tự đánh giá)_
- AI/công cụ đã dùng và cách kiểm tra: Claude Code (Claude Opus 5) hỗ trợ đọc trace JSON, phân loại lỗi, soạn thay đổi prompt/tools và report. Tự kiểm tra: tự chạy mọi run; so `prompt_hash`/`tools_hash` trong run với file đã commit; đọc `tool_results` và thư mục `tickets/`; đối chiếu giá trị `check`/`category` kỳ vọng trước khi sửa `tools.yaml`.
- Thời điểm đã tự nộp URL repo chung trên VLearn: _(điền sau khi nộp)_
