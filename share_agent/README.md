# Bàn giao giữa các agent

Thư mục này lưu tài liệu thay đổi để người dùng, Codex và Claude có cùng thông tin về trạng thái dự án.

## Cách đọc

1. Mở [CHANGELOG.md](CHANGELOG.md), đọc các bản ghi mới nhất và bản ghi liên quan tới phần chuẩn bị sửa.
2. Đối chiếu [README dự án](../README.md), [kiến trúc](../docs/ARCHITECTURE.md) và source hiện tại. Bản ghi là ảnh chụp thông tin tại thời điểm bàn giao, không thay thế source mới hơn.
3. Xem mục việc còn lại và giới hạn kiểm tra trước khi tiếp tục.

## Cách ghi

- Sau mỗi lượt thay đổi file, tạo `changes/YYYY-MM-DD-<agent>-<mo-ta-ngan>.md` theo [TEMPLATE.md](TEMPLATE.md).
- Thêm liên kết ở đầu `CHANGELOG.md`. Tên agent có thể là `codex`, `claude` hoặc tên công cụ thực tế.
- Tóm tắt cả file mới, file sửa và file di chuyển; dùng đường dẫn tương đối với gốc dự án để dễ chia sẻ giữa máy.
- Ghi lệnh kiểm tra và kết quả thật, đồng thời nêu phần chưa kiểm tra.
- Không lưu mật khẩu, token, API key, địa chỉ email cá nhân hoặc dữ liệu riêng tư từ JSON.
- Không sửa/xóa bản ghi của agent khác để che lịch sử; tạo bản ghi bổ sung nếu cần đính chính.

Quy tắc bắt buộc nằm trong [AGENTS.md](../AGENTS.md); Claude có điểm dẫn vào tại [CLAUDE.md](../CLAUDE.md). Không cần tạo chat mới hay gửi tin nhắn để dùng thư mục này: agent làm việc trên dự án sẽ đọc các file bàn giao.
