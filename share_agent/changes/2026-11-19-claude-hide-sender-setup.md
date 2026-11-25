# Ẩn cấu hình Client OAuth khỏi người dùng cuối; hỗ trợ Client đóng gói sẵn

- Ngày: 2026-11-19 (múi giờ người dùng)
- Agent: Claude
- Trạng thái: code xong, 159 test đạt. Người dùng báo đã đăng nhập Google và 「テスト送信」 thành công (thư thật đã tới, 2026-11-19). Chưa thử luồng đầy đủ (bắt đầu phiên → nhận mã → dừng sớm bằng mã) và chưa xem bố cục mới ở cả ba ngôn ngữ

## Yêu cầu

Người dùng chỉ ra rằng ô Client ID/Secret là phần nội bộ của nhà phát hành, không phải thứ khách hàng phải thấy (mục tiêu: bán được). Cần làm để khách chỉ nhập Gmail.

## Thay đổi thực tế

| File | Nội dung |
| --- | --- |
| `evolock/integrations/gmail_oauth.py` | Hỗ trợ Client đóng gói sẵn: `assets/oauth_client.json` (cùng định dạng file Google cho tải về, khóa `installed`). `_client()` ưu tiên bản đóng gói, sau đó tới bản trong Credential Manager. `has_client`, `authorize`, `_access_token` dùng `_client()`. Thêm `uses_bundled_client()` |
| `evolock/ui/app.py` | Mục "送信元の設定" (Client ID/Secret, JSON, app password) chỉ hiện khi `developer_mode` = true, biến môi trường `EVOLOCK_DEV=1`, hoặc chưa có Client nào (giai đoạn dev). Có Client đóng gói sẵn thì ẩn hẳn. Nút "🔐 Googleでログイン" chuyển ra khu vực bảo vệ Gmail (hiện khi có Client và chưa đăng nhập, tự ẩn sau khi đăng nhập). Thông báo trạng thái đổi theo trường hợp. Các biến nhập liệu vẫn tồn tại khi mục bị ẩn |
| `evolock/storage/config.py` | Khóa `developer_mode` (mặc định false) |
| `evolock/locales/vi.py`, `en.py` | Bản dịch chuỗi mới |
| `tests/test_gmail_sending.py` | 3 test `BundledClientTests` |
| `tests/test_app_integration.py` | 2 test: khi nào hiện mục cấu hình, khi nào hiện nút đăng nhập |

## Kiểm tra

| Lệnh | Kết quả |
| --- | --- |
| `.\venv\Scripts\python.exe -B -m unittest discover -s tests` | 159/159 đạt |

## Giới hạn và việc còn lại

- Chưa có `assets/oauth_client.json`, nên hiện nay mục cấu hình vẫn hiện cho tới khi người dùng đọc file JSON vào (khi đó nó ẩn ở lần mở app sau).
- Client đóng gói sẵn vẫn cần mỗi khách bấm "Đăng nhập Google" một lần, và để dùng rộng rãi app phải qua xác minh của Google (khi ở chế độ Testing: tối đa 100 người dùng thử, token hết hạn sau 7 ngày). Hướng không cần đăng nhập là dịch vụ gửi thư riêng (Render hoặc dịch vụ email), chưa làm.
- `assets/oauth_client.json` chứa secret: không đưa vào kho mã công khai; chỉ đóng gói vào bản bán.
- Chưa xem bằng mắt bố cục mới của khu vực bảo vệ Gmail ở cả ba ngôn ngữ.
