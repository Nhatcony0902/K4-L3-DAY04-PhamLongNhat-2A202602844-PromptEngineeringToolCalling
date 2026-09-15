# TEAM — Day04, K4-L3B

**Làm nhóm.** Mỗi người tự viết và commit phần INDIVIDUAL của mình.

## Thông tin bài nộp

- Tên nhóm: Làm cá nhân (1 thành viên)
- Người đại diện / MSSV: Phạm Long Nhật / 2A202602844
- Tên repo: `K4-L3-DAY04-PhamLongNhat-2A202602844-PromptEngineeringToolCalling`
- URL repo, nhánh nộp, commit chốt: https://github.com/Nhatcony0902/K4-L3-DAY04-PhamLongNhat-2A202602844-PromptEngineeringToolCalling · nhánh `main` · commit chốt: `c0135c9`
- Deadline áp dụng và link thông báo đổi hạn nếu có: 23:59 ngày làm lab, Asia/Ho_Chi_Minh (mặc định); chưa có thông báo đổi hạn

## Thành viên

| Họ và tên | MSSV | GitHub | Vai trò và công việc | File/commit/PR |
|---|---|---|---|---|
| Phạm Long Nhật | 2A202602844 | [Nhatcony0902](https://github.com/Nhatcony0902) | Toàn bộ: chạy eval v0–v5, phân tích lỗi, sửa `system_prompt.md` và `tools.yaml`, 10 case nhóm, UI chat + so sánh version, bonus `request_account_unlock`, guard xác nhận, version log, report | v0–v3: `3cc92c1`, `66fe80e`, `37956c2`, `1d344fa`, `41e30bd`, `26d69f0`; safety/group: `6c17b9b`, `1125b33`, `6f783f8`; UI: `9caab64`, `36564e6`, `287822d`; bonus/v4–v5: `3009f29`, `1d646f1`, `babba6e`, `e8bf870` |

## Nhận xét chung

- Kết quả và bằng chứng: bộ base 30 case, case_accuracy 0.70 (v0) → 0.767 (v1) → 0.867 (v2) → 1.0 (v3) → 0.967 (v4, v5); group 8/10 (v3); adversarial 8/12 (v3) → 6/12 (v4, v5) nhưng số lần ghi trái phép 2 (v3) → 5 (v4) → 0 (v5); bonus 5/8. Mọi run `provider_error_cases = 0`, `measured_cases == total_cases`. Run trong `starter_v0/runs/`, bảng so sánh ở [REPORT.md § B1](starter_v0/artifacts/REPORT.md#b1-version-evidence), log ở [version_log.csv](starter_v0/artifacts/version_log.csv).
- Thay đổi hiệu quả nhất: v3 — làm rõ mô tả tham số trong `tools.yaml` sửa được H04/H19 mà quy tắc chung trong prompt v2 không sửa được (trace v1 và v2 giống hệt).
- Giới hạn còn lại: mỗi version chạy 1 lần (M06/H17 dao động, rủi ro overfit); prompt v4 làm yếu boundary so với v3 (H12, A03, A10) và mâu thuẫn U01/U02 — chưa sửa prompt; guard v5 chỉ đối chiếu ID và từ khóa đồng ý/phủ định, đồng thời chặn cả U05 hợp lệ trong eval; web search chưa kiểm chứng vì không có TAVILY_API_KEY.
- Cách phân công và tích hợp: làm cá nhân; mỗi version tách commit artifact và commit evidence để đối chiếu hash. Kiểm tra cách khởi động UI theo README bằng một bản clone mới (không có thành viên khác).

## INDIVIDUAL

### Phạm Long Nhật — 2A202602844

- Phần việc và file/commit/PR: chạy v0–v3 và phân tích 9 case fail của v0 (`3cc92c1`, `1d344fa`, `26d69f0`); prompt v1 xác nhận write action (`66fe80e`); prompt v2 không đoán ID/enum (`37956c2`); `tools.yaml` v3 (`41e30bd`); adversarial + 10 case nhóm (`6c17b9b`, `1125b33`, `6f783f8`); UI chat và trang so sánh v0–v3 (`9caab64`, `36564e6`, `287822d`); bonus `request_account_unlock` + 8 case + 7 test (`3009f29`); guard xác nhận v5 + 6 test (`babba6e`); run v4/v5 (`1d646f1`, `e8bf870`); `version_log.csv`, `REPORT.md`.
- Quyết định, khó khăn và cách xử lý:
  - Lỗi 401 khi preflight: key trong `OPENROUTER_API_KEY` không phải key OpenRouter → thay key đúng.
  - Thứ tự sửa: ưu tiên an toàn (boundary ticket) ở v1 trước các lỗi routing.
  - v1 làm M06 regress; v2 không sửa được H04/H19 → chuyển hướng dẫn vào mô tả tham số ở v3.
  - v4 (thêm bonus) làm A03/A10 ghi ticket và U08 ghi hồ sơ mở khóa → thêm guard trong code ở v5 thay vì sửa tiếp prompt.
  
- Điều đã học: hiểu về cách mà ai agent gọi tool và xử lí thông tin cũng như các thay đổi trong đoạn hội thoại
- AI/công cụ đã dùng và cách kiểm tra: Claude Code (Claude Opus 5) hỗ trợ đọc trace JSON, phân loại lỗi, soạn thay đổi prompt/tools và report. Tự kiểm tra: tự chạy mọi run và UI; so `prompt_hash`/`tools_hash` trong run với file đã commit; đọc `tool_results` và thư mục `tickets/`, `unlock_requests/`; chạy unit test; đối chiếu giá trị `check`/`category` kỳ vọng trước khi sửa `tools.yaml`.
- Thời điểm đã tự nộp URL repo chung trên VLearn: 
