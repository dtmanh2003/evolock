# Nâng cấp giao diện tập trung và khả năng truy cập nội dung

- Ngày: 2026-11-13 (Asia/Tokyo)
- Agent: Codex
- Trạng thái: Hoàn thành thay đổi giao diện trong phạm vi dưới đây.

## Yêu cầu

Nâng chất lượng giao diện và trải nghiệm sử dụng. Tiếp nối yêu cầu bỏ thông tin process khỏi UI; giữ dữ liệu và logic học/chặn hiện hành.

## Thay đổi thực tế

| File | Thao tác | Nội dung |
| --- | --- | --- |
| `evolock/ui/app.py` | Sửa | Palette xanh đen, chữ phụ sáng hơn; vùng đồng hồ/nút bắt đầu rõ ràng; chọn nhanh 25/5, 50/10, 90/15; card tiến độ ngày; lịch sử/log thu gọn; tab cuộn, cửa sổ đổi kích thước; cài đặt AI nâng cao thu gọn. |
| `README.md` | Sửa | Mô tả giao diện và nhãn tab mới. |
| `output/ui-preview.png` | Tạo | Ảnh màn hình chính từ app chạy với dữ liệu tạm và blocker giả. |
| `share_agent/CHANGELOG.md` | Sửa | Thêm liên kết bàn giao. |

Cửa sổ mặc định 640×820, tối thiểu 560×620. Đổi nhãn tab ロック thành 集中, Stats thành 記録. Mục tiêu ngày vẫn hiển thị ngoài cài đặt nâng cao. Không đổi ngôn ngữ toàn app, source AI Coach, SMTP, credential hay dữ liệu cá nhân. Chọn preset trong khi đang học không thay thời gian phiên đang chạy.

## Kiểm tra

- `.\venv\Scripts\python.exe -B -m unittest discover -s tests -q`: 52/52 đạt sau thay giao diện chính.
- Dựng Tk thật với manager dùng thư mục tạm, Blocker/tray/startup/keyring được mock: cả 5 tab dựng được ở 640×820 và 560×620.
- Kiểm tra preset: ở idle chọn 25/5 cập nhật hai trường và đồng hồ 25:00; đang studying chọn preset khác không thay giá trị.
- Đã chụp và xem màn hình chính, kiểm tra phân cấp nội dung, độ tương phản và nút hành động. Chụp bằng tọa độ DPI-aware để tránh crop sai trên Windows scaling.

## Giới hạn và việc còn lại

- Chưa kiểm thử trực quan mọi dialog, màn hình nhỏ/DPI khác hoặc thao tác bằng screen reader. Thanh cuộn giúp tiếp cận nội dung dài nhưng chưa phải bố cục tự co giãn toàn bộ widget.
- Không triển khai dịch vụ email mới: yêu cầu chỉ nhập Gmail vẫn còn mở, cần cấu hình máy chủ/tài khoản gửi. Luồng SMTP hiện có vẫn được giữ và có thể timeout như người dùng đã báo.
- Chưa xử lý tất cả vấn đề UX của xác thực, tự chuyển tab khi AI hoàn tất hoặc nhập thời lượng không hợp lệ. Không coi thay đổi UI này là xác nhận sản phẩm sẵn sàng phát hành.

## Hướng dẫn tiếp tục

Thoát phiên cũ rồi mở `Mo_EvoLock.bat`. Khi sửa tiếp, giữ các tên widget/biến mà luồng phiên học đang dùng và bảo toàn AI Coach của Claude. Không dùng dữ liệu người dùng để dựng preview; ảnh trong output hiện dùng fixture trống.
