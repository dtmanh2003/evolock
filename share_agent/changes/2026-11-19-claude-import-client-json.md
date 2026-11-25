# Nút đọc Client OAuth từ file JSON (Gmail)

- Ngày: 2026-11-19 (múi giờ người dùng)
- Agent: Claude
- Trạng thái: code xong, 154 test đạt; chưa bấm thử nút bằng file thật và chưa gửi thư thật

## Yêu cầu

Người dùng đã tạo OAuth Client (Desktop app) trên Google Cloud, tải file JSON và đặt vào thư mục dự án, muốn dùng nó để gửi mã Gmail. Secret không được đi qua chat nên agent không mở file đó.

## Thay đổi thực tế

| File | Nội dung |
| --- | --- |
| `evolock/integrations/gmail_oauth.py` | Thêm `load_client_file(path)`: đọc JSON khóa `installed`, lưu Client ID/Secret vào Credential Manager qua `save_client`. Từ chối JSON loại `web` kèm lý do, file hỏng, thiếu trường. Thông báo lỗi không bao giờ chứa secret |
| `evolock/ui/app.py` | Nút "📄 JSONファイルから読み込む" trong "送信元の設定", hàm `_import_client_json` (hộp chọn file, báo lỗi/thành công, nhắc xóa file JSON); import `filedialog` |
| `evolock/locales/vi.py`, `en.py` | Bản dịch các chuỗi mới (do Claude viết, chưa có người bản ngữ xem) |
| `tests/test_gmail_sending.py` | 4 test `ClientFileTests`: lưu đúng, từ chối loại web, file hỏng/thiếu trường, thông báo lỗi không lộ secret |

## Kiểm tra

| Lệnh | Kết quả |
| --- | --- |
| `.\venv\Scripts\python.exe -B -m unittest discover -s tests` | 154/154 đạt |

## Giới hạn và việc còn lại

- Chưa bấm thử nút trong cửa sổ thật; chưa đăng nhập Google và chưa gửi thư thật.
- File JSON chứa secret đang nằm trong thư mục dự án (nằm trong OneDrive, nên có thể đã đồng bộ lên cloud). Sau khi đọc xong cần xóa file; nếu lo ngại, tạo lại secret trên Google Cloud.
- Khi bán cho nhiều khách, mỗi khách không nên tự tạo Client; cần dịch vụ gửi thư do nhà phát hành quản lý.
