# Hướng dẫn cho Claude trong dự án EvoLock

Đọc và tuân thủ quy tắc dùng chung tại `AGENTS.md`.

Trước khi sửa, đọc `README.md`, `docs/ARCHITECTURE.md` và các bản ghi gần nhất trong `share_agent/CHANGELOG.md`. Source đang dùng nằm trong `evolock/`; bản sao lịch sử nằm trong `archive/`.

Sau mỗi lượt có sửa file, tạo tài liệu bàn giao mới trong `share_agent/changes/` theo `share_agent/TEMPLATE.md`, rồi cập nhật `share_agent/CHANGELOG.md` trước khi trả lời người dùng. Ghi đúng file đã đổi, lý do, kiểm tra/kết quả, giới hạn và việc còn lại; không ghi credential hoặc dữ liệu cá nhân. Không ghi đè tài liệu của agent khác.

Quy tắc chi tiết và ngoại lệ nằm trong `AGENTS.md`. Thư mục dùng chung này giúp Codex và Claude đọc lại thay đổi của nhau; không phải cơ chế tự gửi thông báo giữa các ứng dụng.
