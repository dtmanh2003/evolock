# Đơn giản hóa bảo vệ phiên học

- Ngày: 2026-11-13 (Asia/Tokyo)
- Agent: Codex
- Trạng thái: Hoàn thành luồng bảo vệ tùy chọn đã được người dùng đồng ý.

## Yêu cầu

Người dùng đồng ý phương án: bắt đầu học không tạo mật khẩu, dừng sớm xác nhận; bảo vệ bằng mã mặc định tắt và người muốn dùng tự đặt mã. Bỏ các nút tạo ngẫu nhiên/xem/xóa và giải thích rõ loại mã đang được yêu cầu.

## Thay đổi thực tế

| File | Thao tác | Nội dung |
| --- | --- | --- |
| `evolock/storage/config.py` | Sửa | Thêm `protection_enabled=False`; cấu hình cũ không có khóa này dùng chế độ nhẹ nhàng. |
| `evolock/ui/app.py` | Sửa | Cài đặt một toggle bảo vệ; đặt mã 6 số hai lần; quản lý mã chỉ hiện khi bật; đổi/tắt cần mã hiện tại; không cho đổi giữa phiên. |
| `evolock/ui/app.py` | Sửa | Bắt đầu trực tiếp, không tạo mật khẩu hoặc chờ SMTP. Dừng/thoát giữa phiên không bảo vệ có dialog hai nút rõ nghĩa; phiên bảo vệ yêu cầu mã local. Ngoài phiên học, thoát không hỏi mã. |
| `evolock/ui/app.py` | Sửa | Hộp nhập ghi rõ mã EvoLock, không phải mật khẩu Gmail. Bỏ liên kết mã khẩn cấp khỏi dialog thường. Gmail cũ nằm trong mục thu gọn và nói rõ chỉ dùng thử kết nối. |
| `tests/test_optional_protection.py` | Tạo | 8 test mới cho opt-in, migration defaults, hủy/sai mã, hash, snapshot phiên và quản lý bảo vệ. |
| `README.md`, `docs/ARCHITECTURE.md` | Sửa | Mô tả luồng mới và cơ chế cũ còn lưu trong source. |
| `share_agent/CHANGELOG.md` | Sửa | Thêm bản ghi. |

Không sửa dữ liệu cá nhân; mật khẩu/hash/credential cũ vẫn được giữ. Việc người dùng tự đặt mã mới sẽ cập nhật hash mật khẩu theo thao tác đó. Mã mới không được ghi rõ vào Credential Manager. Trạng thái bảo vệ được chụp đầu phiên; bật/tắt chỉ sau khi kết thúc phiên. Phần SMTP và các helper cũ giữ để tương thích nhưng không còn nằm trên luồng bắt đầu học.

## Kiểm tra

- `.\venv\Scripts\python.exe -B -m unittest discover -s tests -q`: 60/60 đạt.
- Tk thật với data tạm và Blocker/tray/keyring/startup giả: trang Cài đặt dựng được, bảo vệ mặc định tắt; sau đặt mã nút quản lý xuất hiện. Không chạy phiên chặn, gửi thư hay sửa credential thật.

## Giới hạn và việc còn lại

- Đây là thay đổi chính sách sản phẩm có chủ đích: bản cũ có mật khẩu cũng mặc định không bảo vệ nếu chưa bật toggle mới. Người dùng đã đồng ý phương án trước triển khai.
- Chưa thiết kế lại phục hồi mã bị quên. Hướng dẫn đặt mã nhắc người dùng giữ mã; không cung cấp bypass mới trên UI. Helper mã khẩn cấp cũ còn trong source nhưng không được giới thiệu trong luồng mới.
- Lịch sử giữ quy tắc cũ: phiên dưới một phút chưa ghi. Không sửa hồi tố lịch sử.
- Dịch vụ email chỉ nhập địa chỉ Gmail vẫn chưa triển khai; không tuyên bố hoạt động. SMTP cũ chỉ có nút thử trong phần thu gọn.
- Chưa kiểm thử toàn bộ thao tác người dùng cuối bằng GUI; các nhánh logic đã có kiểm tra mock và tạm.

## Hướng dẫn tiếp tục

Thoát bản đang chạy rồi mở lại `Mo_EvoLock.bat`. Muốn khóa chặt hơn thì bật bảo vệ và tự đặt mã trong Cài đặt. Không cần xóa data hoặc credential cũ để nâng cấp. Bảo toàn phần AI Coach của Claude khi phát triển tiếp.
