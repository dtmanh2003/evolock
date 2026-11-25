# AI Coach: findings do code tính, cửa sổ phân tích có fallback

- Ngày: 2026-11-13 (múi giờ người dùng)
- Agent: Claude
- Trạng thái: hoàn thành (chưa kiểm tra với model Ollama/Anthropic thật)

## Yêu cầu

Người dùng muốn tập trung vào phần AI phân tích và đồng ý hướng: code tự tính các phát hiện, model chỉ diễn đạt; khi 7 ngày gần nhất trống thì dùng dữ liệu tuần học gần nhất; số liệu phải đáng tin.

## Thay đổi thực tế

Trước: `app.py` gom log thô (mỗi dòng là một lần quét 3 giây, ví dụ 460 sự kiện) đưa cho model nhỏ `qwen2.5vl:3b` tự diễn giải, nên hay đọc sai số hoặc bịa nguyên nhân. Nếu 7 ngày gần nhất không có phiên nào thì báo "không có dữ liệu" dù lịch sử vẫn còn.

Sau:

- `select_window`: nếu 7 ngày gần nhất không có phiên, dùng 7 ngày kết thúc ở phiên cuối cùng (`stale=True`, kèm `days_ago`).
- `_episodes`: gộp sự kiện warn/kill liên tiếp (cách nhau ≤ 3 phút) của cùng ứng dụng thành một lần mất tập trung.
- `compute_findings`: trả về danh sách `{fact, hint}` (staleness, so với tuần trước, khung giờ tập trung, đạt mục tiêu, lần mất tập trung, dừng học sớm). Mọi con số do code tính.
- Prompt mới (`COACH_SYSTEM_PROMPT` và `_build_coach_user_prompt`): chỉ dùng "事実", cấm suy đoán, tối đa 400 chữ. Nhiệt độ 0.3. Báo cáo offline cũng in các phát hiện này.
- Đã xóa `summarize_activity`, `summarize_overrides` và các hàm prompt cũ (chỉ `app.py` dùng).
- Khi số lần dừng sớm lớn hơn số phiên học, fact không in mẫu số "N lần trong M phiên" (tránh 17/12 mâu thuẫn).
- Dữ liệu: `data/activity_log.json` chỉ có bản cũ 2 sự kiện (17/09) còn bản đầy đủ 470 sự kiện (17–24/09) nằm trong `archive/sync_conflicts/activity_log-WIN-4CQG3NF4TVJ.json`. `data/overrides.json` chỉ có 2 bản ghi, bản đủ 19 bản ghi nằm cạnh file đó. Đã sao chép bản đủ vào `data/` sau khi backup bản cũ. Lưu ý: không dedupe `activity_log` theo nội dung, vì các sự kiện trùng nhau hoàn toàn là hợp lệ (dấu thời gian chỉ tới phút).

| File/thư mục | Thao tác | Nội dung |
| --- | --- | --- |
| `evolock/services/ai_coach.py` | Sửa | Thêm `select_window`, `in_window`, `_episodes`, `compute_findings`, prompt mới, `analyze(window=, findings=)`; xóa hàm tóm tắt log cũ |
| `evolock/ui/app.py` | Sửa | `_run_analysis` tính cửa sổ và findings rồi truyền cho `analyze`; không gửi tóm tắt mật khẩu khi cửa sổ cũ |
| `tests/test_ai_coach_findings.py` | Tạo | 15 test cho cửa sổ, gộp đợt, findings, fallback offline, nội dung prompt |
| `README.md` | Sửa | Mục AI Coach mô tả cách tạo nội dung |
| `data/activity_log.json`, `data/overrides.json` | Ghi đè bằng bản đầy đủ | 470 sự kiện và 19 bản ghi; bản cũ ở `archive/data_backup_2026-11-13/` |
| `archive/data_backup_2026-11-13/` | Tạo | Backup 2 file data cũ |

## Kiểm tra

| Lệnh hoặc cách kiểm tra | Kết quả |
| --- | --- |
| `python -B -m py_compile evolock/ui/app.py evolock/services/ai_coach.py` | Đạt |
| `.\venv\Scripts\python.exe -B -m unittest discover -s tests -v` | 43/43 đạt (gồm 15 test mới) |
| Chạy `select_window` + `compute_findings` trên dữ liệu thật trong `data/` | Cửa sổ 2026-09-18..24 (stale, 50 ngày trước), 14 phiên; 470 sự kiện thô thành 12 lần mất tập trung; 17 lần dừng sớm, lý do nhiều nhất là 急用 |

## Giới hạn và việc còn lại

- Chưa gọi model thật (Ollama `qwen2.5vl:3b` hoặc Anthropic) với prompt mới; cần bấm `今すぐ分析` trong app để xem chất lượng văn bản và thời gian phản hồi.
- Chưa mở GUI để kiểm tra bằng mắt; chỉ kiểm tra compile, test và chạy hàm trên dữ liệu thật.
- Ngưỡng của findings (chênh lệch ≥ 10 phút, tập trung ≥ 50%, gộp 3 phút) là giá trị tự chọn, có thể chỉnh sau khi xem dữ liệu thực tế.
- Chưa xử lý: nội dung hint là mẫu cố định theo lý do (`_OVERRIDE_HINTS` chỉ có 3 lý do); lý do khác dùng gợi ý chung.
- Các file `*-WIN-4CQG3NF4TVJ.json` còn lại trong `archive/sync_conflicts/` (history, tasks, config, stats...) chưa được đối chiếu; chỉ activity_log và overrides đã dùng.

## Hướng dẫn tiếp tục / phục hồi

- Điểm vào: `evolock/services/ai_coach.py` (phần "Cửa sổ phân tích và các phát hiện do code tính") và `_run_analysis` trong `evolock/ui/app.py`.
- Thêm loại phát hiện mới: thêm một khối `add(fact, hint)` trong `compute_findings` và một test trong `tests/test_ai_coach_findings.py`.
- Khôi phục data cũ nếu cần: copy lại từ `archive/data_backup_2026-11-13/`.
