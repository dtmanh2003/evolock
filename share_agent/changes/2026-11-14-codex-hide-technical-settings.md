# Bỏ cấu hình kỹ thuật khỏi UI và tổng hợp việc còn lại

- Ngày: 2026-11-14 (Asia/Tokyo)
- Agent: Codex
- Trạng thái: Hoàn thành chỉnh UI đã yêu cầu ở lượt trước và bàn giao bổ sung.

## Yêu cầu
Người dùng muốn model/API key/watchdog/cài đặt AI chỉ dành cho người phát triển; sau đó hỏi còn vấn đề gì.

## Thay đổi thực tế
- `evolock/ui/app.py`: bỏ khối nâng cao gồm whitelist, Smart Block, watchdog, model Ollama, API key và Screen AI khỏi builder; bỏ refresh widget whitelist khi khởi tạo. Giữ mục tiêu ngày và các cài đặt thông thường. Các hàm quản lý cũ còn trong source nhưng không có nút gọi trên UI.
- `docs/DEVELOPER_SETTINGS.md`: thêm hướng dẫn cấu hình nội bộ, không chứa credential.
- `README.md`: dẫn đến tài liệu mới.
- `share_agent/CHANGELOG.md`: thêm bản ghi.

Không đổi model, credential, whitelist hoặc dữ liệu cá nhân. Runtime vẫn nạp cấu hình đã lưu.

## Kiểm tra
Sau sửa source ở lượt trước đã chạy unittest: 60/60 đạt. Lượt này đối chiếu source xác nhận khối kỹ thuật không còn trong builder; chưa kiểm tra trực quan toàn bộ GUI.

## Giới hạn và việc còn lại
1. Backend AI/danh sách chặn vẫn cần thiết lập nội bộ; ẩn UI không làm ứng dụng tự cấu hình được trên máy mới.
2. Chưa có dịch vụ email chỉ nhập Gmail; luồng học hiện không phụ thuộc SMTP.
3. Chưa có luồng phục hồi mã bảo vệ bị quên.
4. AI Coach có nguy cơ kết quả về sai thứ tự và còn tự chuyển tab khi phân tích tự động xong; đã đối chiếu source, chưa tái hiện race đầu-cuối.
5. Thời lượng nhập sai được thay bằng mặc định mà không giải thích; phiên qua nửa đêm chưa chia phút theo ngày.
6. Còn kiểm thử sleep/resume, restart giữa phiên, GUI DPI và lỗi backend thực tế. Những mục này là khoảng trống kiểm thử, chưa kết luận chắc có lỗi.
7. Thông báo/quyền kiểm soát chụp màn hình và gửi ảnh ra dịch vụ ngoài cần thiết kế cho người dùng; chỉ chi tiết model/API mới thuộc cấu hình nhà phát triển.

## Hướng dẫn tiếp tục
Mở lại app để nạp UI mới. Ưu tiên trải nghiệm khi thiếu backend, phản hồi trạng thái và phục hồi mã; không khôi phục cả thư mục data hoặc đưa credential vào tài liệu.
