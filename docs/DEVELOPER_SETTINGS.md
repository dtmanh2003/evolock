# Cấu hình nội bộ

Các điều khiển model/API key/watchdog/whitelist đã bỏ khỏi trang Cài đặt người dùng. Việc ẩn UI không tự thiết lập backend và không thay đổi cấu hình đã lưu.

Thoát EvoLock trước khi chỉnh cấu hình. Sao lưu và chỉ sửa các khóa cần thiết trong `data/config.json`, giữ các khóa khác:

- `smart_enabled`: bật phân loại tiêu đề trình duyệt.
- `screen_enabled`: lựa chọn bật phân tích ảnh; chỉ hoạt động khi có backend.
- `ollama_model`: model nhận ảnh đã cài trên Ollama local.
- `coach_ollama_model`: model văn bản cho Coach; trống thì dùng model chung.
- `anthropic_api_key`: credential backend ngoài; không commit/chia sẻ file này. Không đưa giá trị thật vào báo cáo.

`data/blocked.json` chứa `apps` là danh sách process; `data/whitelist.json` chứa `channels`. Watchdog vẫn chạy riêng bằng Python môi trường dự án và `watchdog.py`, không tự bật do đổi UI.

Khi phân phối cho người khác, cần bước thiết lập và kiểm tra backend phù hợp; không đóng gói API key của nhà phát triển trong client. Nếu bật chụp màn hình/gửi ảnh ra dịch vụ ngoài, cần giải thích ngắn gọn và cho người dùng kiểm soát quyền riêng tư; ẩn chi tiết kỹ thuật không thay thế thông báo đó.
