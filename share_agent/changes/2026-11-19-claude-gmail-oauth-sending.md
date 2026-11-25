# Gmail: gửi mã bằng đăng nhập Google (OAuth), sửa lỗi SMTP

- Ngày: 2026-11-19 (múi giờ người dùng)
- Agent: Claude
- Trạng thái: code hoàn thành và có test; **chưa gửi được thư thật** vì cần người dùng tạo OAuth Client ID và đăng nhập

## Yêu cầu

Người dùng báo app không gửi được Gmail, không muốn dùng App Password và muốn app tự gửi thẳng. Đây chỉ sửa khả năng gửi; chưa nối lại việc gửi mã vào lúc bắt đầu học (Codex đã tách ra, README ghi rõ).

## Chẩn đoán (không gửi thư, không in bí mật)

- `keyring` hoạt động, đã có địa chỉ Gmail và App Password; kết nối TLS tới `smtp.gmail.com` cổng 587 và 465 bình thường, chứng chỉ Google thật.
- Đăng nhập bằng thông tin giả: Google trả `535` chuẩn. Đăng nhập bằng **địa chỉ thật** (kể cả mật khẩu cố tình sai): Google **ngắt kết nối** thay vì trả 535. Kết luận: Google đang chặn/giới hạn đăng nhập SMTP của tài khoản này từ máy người dùng (nguyên nhân chưa xác định: giới hạn tạm thời, đăng nhập đáng ngờ hoặc tắt xác minh 2 bước). Không rõ App Password còn đúng hay không.
- Lưu ý: đã thử 5 lần đăng nhập vào tài khoản thật khi chẩn đoán; không thử thêm.
- Code cũ còn tự thử đăng nhập lại ở cổng thứ hai khi đăng nhập thất bại (nhân đôi lần sai) và cắt thông báo lỗi còn 50 ký tự.

## Thay đổi thực tế

| File/thư mục | Thao tác | Nội dung |
| --- | --- | --- |
| `evolock/integrations/gmail_oauth.py` | Tạo | OAuth 2.0 loopback + PKCE (S256) + kiểm tra `state`, chỉ dùng thư viện chuẩn; refresh token/Client ID/Secret lưu trong Credential Manager; gửi qua Gmail API (scope `gmail.send`); tự lấy lại access token, thử lại 1 lần khi 401; lỗi dịch sang tiếng Nhật |
| `evolock/integrations/session_code.py` | Sửa | `send_code_email` dùng OAuth nếu đã đăng nhập, nếu không dùng SMTP. SMTP: chỉ đổi cổng khi lỗi kết nối, dừng khi đã đăng nhập thất bại; `describe_smtp_error` dịch lỗi; `normalize_app_password` bỏ khoảng trắng; `save_app_password`/`save_local_password` trả bool; thêm `build_code_message`, `has_sender_credentials` |
| `evolock/storage/config.py` | Sửa | `has_gmail_configured` chấp nhận OAuth hoặc App Password |
| `evolock/ui/app.py` | Sửa | Mục Gmail (thu gọn) có ô Client ID/Secret và nút `Googleでログイン`; `保存` báo lỗi khi không lưu được; trạng thái hiển thị phương thức; lỗi thử gửi không còn bị cắt 50 ký tự; `解除` cũng xóa đăng nhập Google |
| `tests/test_gmail_sending.py` | Tạo | 21 test: SMTP không thử lại đăng nhập, ngắt kết nối, dự phòng cổng, bỏ khoảng trắng, lưu thất bại; OAuth login (PKCE, state sai, hủy, hết hạn chờ, thiếu quyền), gửi, refresh, thu hồi, API chưa bật |
| `README.md` | Sửa | Mục Gmail mô tả hai cách gửi và cách tạo Client ID |

## Kiểm tra

| Lệnh hoặc cách kiểm tra | Kết quả |
| --- | --- |
| `.\venv\Scripts\python.exe -B -m unittest discover -s tests` | 93/93 đạt (có 21 test Gmail mới; kho bí mật, SMTP, HTTP và trình duyệt đều giả) |
| Dựng thật `_build_settings_tab` bằng Tk ẩn + stub, chạy `_refresh_gmail_status`, `_on_google_login_done`, `_on_gmail_test_done` | Dựng được; chuỗi trạng thái đúng |
| Gửi thư thật / đăng nhập Google thật | **Chưa chạy** (cần Client ID của người dùng) |

## Giới hạn và việc còn lại

- Người dùng phải tạo OAuth Client ID loại "Desktop app" trong Google Cloud Console, bật Gmail API, nhập vào `設定` rồi bấm `Googleでログイン` và `テスト送信`. Nếu app ở trạng thái "Testing" thì token hết hạn sau 7 ngày; cần chuyển "In production".
- Chưa biết OAuth có vượt được việc Google đang chặn tài khoản hay không.
- Chưa nối lại việc gửi mã vào bắt đầu học/dừng sớm (đang là tùy chọn mã bảo vệ cục bộ theo thiết kế của Codex). `_send_session_code_then_start` trong `app.py` hiện không được gọi.
- Chế độ "chỉ nhập địa chỉ Gmail" (không cần thiết lập gì) vẫn cần dịch vụ gửi do developer sở hữu (server hoặc dịch vụ email); chưa làm.
- Mật khẩu dự phòng cục bộ chưa được tạo sẵn; chỉ tạo khi gửi thất bại và người dùng chọn.
- Thông báo ngắt kết nối SMTP trước khi đăng nhập vẫn dùng chung câu về "đang đăng nhập" (không phân biệt giai đoạn).

## Hướng dẫn tiếp tục / phục hồi

- Điểm vào: `evolock/integrations/gmail_oauth.py` (`authorize`, `send_message`) và `send_code_email` trong `session_code.py`.
- Kiểm thử không chạm Credential Manager: dùng `FakeSecrets` trong `tests/test_gmail_sending.py`.
- Khi viết file có tiếng Nhật/Việt từ shell, đừng dùng heredoc qua stdin của Python trên Windows (hỏng ký tự và `\n`); dùng công cụ ghi/sửa file.
