# Bảo vệ bằng mã Gmail, bỏ mã cục bộ khỏi UI, thiết kế lại giao diện

- Ngày: 2026-11-19 (múi giờ người dùng)
- Agent: Claude
- Trạng thái: phần code hoàn thành và có test; **chưa gửi/nhận thư Gmail thật**; đổi ngôn ngữ mới có khung, chưa gắn vào giao diện

## Yêu cầu (người dùng nói trong phiên, hướng sản phẩm để bán)

1. Người dùng chỉ nhập Gmail; khi muốn dùng app hoặc cho con dùng, app gửi mã tới Gmail đó. Không muốn mã/mật khẩu cục bộ hiện ra.
2. Giao diện: danh sách task xấu, bố cục chữ không đẹp, tab 記録 khó nhìn, tab AIコーチ toàn chữ và thiếu chuyên nghiệp, cần bố trí biểu đồ.
3. Bỏ ô "mục tiêu học mỗi ngày" ở Cài đặt (việc đó là của AI/tab 集中); bỏ dòng trạng thái kỹ thuật của Screen AI.
4. Thêm đổi ngôn ngữ (mới làm khung).

## Thay đổi thực tế

**Luồng Gmail** (`evolock/ui/app.py`, `evolock/storage/config.py`)
- Khóa mới `gmail_protection_enabled`. `_gmail_mode()` chỉ đúng khi cờ bật **và** đã có nguồn gửi; dùng `is True` để các test mock `cfg` không vô tình bật.
- `_enter_studying`: ở chế độ Gmail gọi `_send_session_code_then_start` (mã mới mỗi lần học). Gửi lỗi → thử lại / hủy / `保護なしで開始` (bỏ lựa chọn "mật khẩu cục bộ"; ai cũng chọn được lựa chọn này nên đây là điểm yếu có chủ đích để tránh khóa người dùng).
- Dừng sớm/thoát khi học: nếu chế độ Gmail và có mã phiên → hộp thoại mã + lý do (code cũ), ghi override log. Mã cục bộ cũ giữ nguyên hành vi (bài test `test_protected_session_uses_code_not_legacy_mail_hash` vẫn đúng).
- `_check_password` ở chế độ Gmail → `_verify_emailed_code`: gửi mã mới tới Gmail **hiện tại** (`_send_code_blocking`, UI không đứng), 3 lần nhập. Dùng cho việc quản lý khi rảnh: đổi Gmail nhận mã (`change_gmail`), tắt bảo vệ (`disable_gmail`), sửa danh sách chặn.
- Không đổi/tắt được bảo vệ khi đang học. Mã phiên bị xóa khi `_enter_idle`/`_enter_unlocked`.
- `ask_password` có tham số `hint`/`masked`; câu "設定で決めたEvoLockのコード…Gmailのパスワードではありません" không còn hiển thị. Địa chỉ trong hộp thoại bị che (`pa****@gmail.com`).
- Cài đặt: một ô Gmail + 保存/テスト送信/解除; "送信元の設定（初回のみ）" (thu gọn) chứa Client ID/Secret, `Googleでログイン`, App Password. Lưu địa chỉ xong, nếu có nguồn gửi thì bật bảo vệ và tự gửi thử. Mã cục bộ cũ: các widget còn tồn tại nhưng nằm trong frame không pack (để `_refresh_settings` và các test cũ chạy).
- Sửa gửi mail ở lượt trước: `gmail_oauth.py`, `session_code.py` (xem `2026-11-19-claude-gmail-oauth-sending.md`).

**Giao diện**
- Tab タスク: thẻ có vạch màu theo loại, nhãn loại, tên lớn tự xuống dòng, nút ✕ nhạt và `✓ 完了` luôn nằm bên phải; hover; trạng thái rỗng; mục "本日の完了" dạng dòng. Bỏ khung cuộn lồng (tab đã cuộn).
- Tab 記録: thẻ cấp độ + thanh EXP tự vẽ, lưới 2×2 ô số liệu, biểu đồ học 7 ngày, lưới thành tích 2 cột.
- Tab AIコーチ: tiêu đề + nút phân tích, ô số liệu, "コーチのコメント" (ngắn), 4 biểu đồ (học theo ngày có đường mục tiêu, học theo khung giờ, giờ mất tập trung, app hay mở), danh sách phát hiện kèm gợi ý. Biểu đồ tính bằng code và làm mới trước khi gọi AI.
- `evolock/ui/charts.py` (mới): `BarChart`, `HBarChart`, `ProgressBar` bằng Canvas, tự vẽ lại khi đổi kích thước.
- Bỏ ô nhập mục tiêu ngày (giá trị nội bộ `daily_goal_minutes`=120 vẫn dùng cho tab 集中 và Coach). Dòng trạng thái Screen AI chỉ hiện cảnh báo khi ảnh gửi ra dịch vụ ngoài (Anthropic); ẩn khi dùng Ollama cục bộ.
- Kiểu tiêu đề các mục Cài đặt thống nhất.

**AI Coach** (`evolock/services/ai_coach.py`)
- `compute_chart_data` (dữ liệu biểu đồ), `clean_coach_text` (bỏ markdown/đánh số/tiêu đề thừa, bỏ câu lặp; chỉ tách bằng "。！？：" để không phá giờ `10:30`), prompt mới: nhận xét ≤ 250 chữ, không markdown, không lặp, gọi kỳ phân tích là "この週/この期間".

**Khung đa ngôn ngữ** (`evolock/i18n.py`, `evolock/locales/__init__.py`): `tr()` với tiếng Nhật làm mặc định và gốc; thiếu bản dịch thì giữ nguyên. Chưa có bảng dịch vi/en, chưa gắn `tr` vào chuỗi nào, chưa có ô chọn ngôn ngữ.

| File | Thao tác |
| --- | --- |
| `evolock/ui/app.py` | Sửa lớn (luồng Gmail, 4 tab, Cài đặt) |
| `evolock/ui/charts.py` | Tạo |
| `evolock/services/ai_coach.py` | Sửa (chart data, làm sạch văn bản, prompt) |
| `evolock/storage/config.py` | Thêm khóa `gmail_protection_enabled` |
| `evolock/i18n.py`, `evolock/locales/__init__.py` | Tạo (khung, chưa dùng) |
| `tests/test_gmail_protection.py`, `test_charts.py`, `test_i18n.py` | Tạo; `test_ai_coach_findings.py` thêm 7 test |
| `README.md` | Mô tả luồng Gmail, các tab mới |

## Kiểm tra

| Lệnh hoặc cách kiểm tra | Kết quả |
| --- | --- |
| `.\venv\Scripts\python.exe -B -m unittest discover -s tests` | 125/125 đạt (gồm 15 test bảo vệ Gmail, 6 biểu đồ, 4 i18n, 7 Coach mới) |
| Dựng thật các tab bằng Tk với dữ liệu thật rồi chụp ảnh (DPI-aware) | Bố cục đúng: task, cài đặt, 記録, AIコーチ |
| Gửi/nhận thư Gmail thật, đăng nhập Google thật | **Chưa chạy** |
| Chạy toàn app GUI từ đầu | **Chưa chạy**; chỉ dựng từng tab với stub |

## Giới hạn và việc còn lại

- **Để bán được:** người dùng cuối không thể tự tạo OAuth Client ID. Cần dịch vụ gửi mã của nhà phát triển (server hoặc dịch vụ email, ví dụ Render sau này); app chỉ cần gọi một endpoint. Hiện luồng gửi nằm trong `session_code.send_code_email`; thay backend ở đó. Còn cần xem xét pháp lý quyền riêng tư (đọc màn hình, trẻ em), giấy phép thư viện, cơ chế license/cập nhật.
- `保護なしで開始` và việc con có thể tắt mạng để gửi mã thất bại là điểm có thể bị lách; cần quyết định chính sách (fail-closed hay cho phép).
- Đổi ngôn ngữ: **đã làm tiếp ở `2026-11-19-claude-language-switch.md`** (bản ghi này chỉ nói về khung ban đầu).
- Tab AIコーチ: chưa chạy với model Ollama thật; chất lượng nhận xét vẫn phụ thuộc model. Khi phân tích bằng offline, văn bản dài (báo cáo cũ) vẫn hiện trong ô nhận xét.
- Tab 集中 chưa được thiết kế lại; chưa kiểm tra giao diện ở cửa sổ rất hẹp.
- Các việc cũ của audit Codex chưa liên quan lượt này vẫn như trước (Title AI hỏng do `torch`, nhiều request Coach đã được Codex xử lý).

## Hướng dẫn tiếp tục / phục hồi

- Điểm vào: `app.py` (`_gmail_mode`, `_verify_emailed_code`, `_check_override`, `_build_coach_tab`, `_refresh_coach_dashboard`), `charts.py`, `ai_coach.compute_chart_data`.
- Bản sao `app.py` trước các lần thay lớn (chỉ trong thư mục tạm của phiên Claude, có thể mất): `app.py.before_settings_splice`, `app.py.before_dashboard_splice`. Không có git trong dự án; nếu cần quay lại hãy dùng `archive/before_restructure/` hoặc OneDrive version history.
- Khi ghi file có tiếng Nhật/Việt từ shell: không dùng heredoc qua stdin của Python trên Windows; dùng Write/Edit hoặc ghi script ra file.
