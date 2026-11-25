# Gọn giao diện: bỏ ghi chú mật khẩu và danh sách process

- Ngày: 2026-11-13 (Asia/Tokyo)
- Agent: Codex
- Trạng thái: Hoàn thành chỉnh UI theo yêu cầu mới nhất; dịch vụ gửi mã email còn chờ thiết lập.

## Yêu cầu

Người dùng thấy ô ghi chú mật khẩu không cần thiết. Sau đó chỉ rõ danh sách `.exe`/bộ chọn process không dành cho người dùng, rồi xác nhận chỉ cần bộ xử lý biết là đủ. Vì vậy bỏ vùng danh sách và nút chọn, thay vì thiết kế lại danh sách với tên dễ hiểu.

## Thay đổi thực tế

| File | Thao tác | Nội dung |
| --- | --- | --- |
| `evolock/ui/app.py` | Sửa | Bỏ ô memo mật khẩu và các nút/handler đi kèm; bỏ vùng blocked-app trên màn hình chính và đường vào picker. Refresh danh sách trả về khi không có widget. |
| `README.md` | Sửa | Mô tả cấu hình chặn nội bộ và giao diện mới. |
| `share_agent/CHANGELOG.md` | Sửa | Thêm bản ghi này. |

Giữ logic chặn, các nút mật khẩu dự phòng và `data/blocked.json`. Không tự xóa `password_note` đã lưu. Hàm picker cũ còn trong source nhưng không có nút mở trong giao diện. Chưa bổ sung cơ chế tự nhận diện mọi app mới: blocker vẫn theo danh sách nội bộ hiện có và logic AI hiện có.

## Kiểm tra

`.\venv\Scripts\python.exe -B -m unittest discover -s tests -q`: 52/52 đạt. Tìm tham chiếu xác nhận không còn widget memo hoặc nút mở danh sách process. Chưa mở GUI để kiểm tra trực quan.

## Giới hạn và việc còn lại

Người dùng đồng thời yêu cầu chỉ nhập Gmail để nhận mã, đã trả lời chưa có máy chủ/API gửi email và cần thiết lập dịch vụ. Đây là yêu cầu còn mở, chưa triển khai trong thay đổi UI này: SMTP/App Password hiện tại vẫn giữ nguyên. Cần chuẩn bị dịch vụ gửi mã và cấu hình tài khoản gửi phía máy chủ; không thể chỉ ẩn App Password rồi tuyên bố gửi được. Không ghi credential vào source/client.

## Hướng dẫn tiếp tục

Thoát app rồi mở lại để nạp UI mới. Tiếp tục phần dịch vụ email theo yêu cầu còn mở; bảo toàn chỉnh sửa AI Coach của Claude. Không phục hồi dữ liệu cũ chỉ để đổi UI.
