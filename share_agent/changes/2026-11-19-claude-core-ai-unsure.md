# Core: sửa AI phân loại tiêu đề (torch), thêm mức "AI không chắc" + nhãn của phụ huynh

- Ngày: 2026-11-19 (múi giờ người dùng)
- Agent: Claude
- Trạng thái: hoàn thành; 172 test đạt. Bộ chặn đã thử THẬT trên process giả (9/9). Chưa thử với trình duyệt thật và chưa chạy `python main.py`

## Yêu cầu

Người dùng muốn kiểm tra các chức năng core (chặn, AI phán đoán) có thật sự ổn không, và đưa ý tưởng cũ: AI phán đoán, trang không phân loại được thì để phụ huynh gán nhãn.

## Phát hiện khi kiểm tra

- Bộ chặn (`Blocker`): thử thật trên bản sao `ping.exe` đổi tên (không đụng app thật): giết đúng process trong danh sách, không giết process khác, reload danh sách có hiệu lực, `stop()` dừng giết, bật lại hoạt động, callback đúng. 9/9.
- AI tiêu đề **không chạy được**: venv có hai bản `torch` lẫn nhau (2.12.1 và 2.14.0; thư mục venv nằm trong OneDrive) nên `import torch` lỗi `_ControlCollectives`. Khi AI chưa sẵn sàng, mọi trình duyệt có tiêu đề (trừ trang tra cứu/whitelist) bị chặn ngay theo danh sách cơ bản.
- Sau khi sửa: AI chạy (nạp mô hình lần đầu ~36 giây). Trên 32 tiêu đề mẫu: giải trí đúng 15/16; học đúng 11/16, sai 1, "không chắc" 4. Mô hình `all-MiniLM-L6-v2` chỉ giỏi tiếng Anh; tiêu đề tiếng Việt/Nhật hay sai hoặc nhập nhằng (ví dụ "Học tiếng Anh giao tiếp bài 5 - YouTube" bị coi là giải trí).

## Thay đổi thực tế

| File | Nội dung |
| --- | --- |
| `venv/` (không thuộc source) | Gỡ cả hai bản torch, xóa thư mục còn sót, cài lại sạch `torch 2.15.0+cpu` |
| `evolock/services/blocker.py` (mô hình) | Thêm `SMART_MODEL`, đổi từ `all-MiniLM-L6-v2` (chỉ tiếng Anh) sang `paraphrase-multilingual-MiniLM-L12-v2` (~470MB, tải lần đầu về `C:\Users\<user>\.cache\huggingface`). Đo lại trên cùng 32 tiêu đề: học đúng 15/16 (sai 0, không chắc 1), giải trí đúng 15/16 (sai "Shopee - Săn sale"); trước đó học đúng 11/16. Bộ mẫu nhỏ do Claude tự soạn, chưa phải đánh giá độc lập |
| `evolock/storage/site_labels.py` (mới) | `SiteLabels`: nhãn `study`/`block` theo khóa trang (chỉ giữ tên trang, không giữ tiêu đề đầy đủ) và danh sách chờ (tối đa 50, đếm số lần gặp, ghi đĩa thưa; xử lý xong thì xóa khỏi danh sách chờ; chờ quá 14 ngày không ai xử lý thì tự xóa), ghi nguyên tử vào `data/site_labels.json`, file hỏng thì báo `DataFileError` |
| `evolock/services/blocker.py` | `UNSURE_MARGIN = 0.05`; `site_key(title)`; `Blocker.labels`. Nhãn phụ huynh được ưu tiên hơn AI. Nếu điểm học/giải trí chênh < 0.05 và không có tín hiệu Screen AI: **không chặn**, ghi vào danh sách chờ, chỉ báo giao diện một lần cho mỗi trang mới. Nhãn `block` vẫn đi qua bộ tích lũy (chặn sau vài lần quét liên tiếp) |
| `evolock/ui/app.py` | Khung "Trang AI chưa phân biệt được" nằm trong tab AIコーチ (theo yêu cầu gom vào mục phân tích; ban đầu đặt ở Cài đặt rồi đã chuyển): mỗi trang có số lần gặp và nút 学習/娯楽/✕ (không bắt buộc); danh sách "quyết định đã lưu" có nút xóa. Nút luôn nằm bên phải, tiêu đề dài tự cắt. Gán hoặc xóa nhãn phải qua `_check_password("label_site")` (khi bật bảo vệ Gmail thì cần mã gửi về Gmail). `_on_smart_allow` xử lý lớp `unsure` và `label` |
| `evolock/locales/vi.py`, `en.py` | Bản dịch chuỗi mới |
| `tests/test_unsure_sites.py` (mới) | 12 test: `site_key`, kho nhãn (lưu, khởi động lại, giới hạn, file hỏng), tiêu đề không chắc không bị giết và chỉ báo một lần, giải trí rõ ràng vẫn bị giết, nhãn phụ huynh ghi đè AI hai chiều |
| `tests/test_app_integration.py` | 2 test giao diện cho danh sách chờ và việc gán nhãn cần mã; dùng `SiteLabels` tạm |

## Kiểm tra

| Lệnh hoặc cách kiểm tra | Kết quả |
| --- | --- |
| `.\venv\Scripts\python.exe -B -m unittest discover -s tests` | 171/171 đạt |
| Chạy `Blocker` thật trên process giả | 9/9 đạt |
| `SmartClassifier` thật trên 32 tiêu đề mẫu | xem phần Phát hiện |

## Giới hạn và việc còn lại

- Mức "không chắc" cho qua: học sinh có thể cố chọn tiêu đề nhập nhằng để né. Giới hạn bởi ngưỡng 0.05 và việc phụ huynh có thể gán nhãn `block`; chưa có giới hạn tổng thời gian ở trạng thái "không chắc".
- Đã đổi sang mô hình đa ngôn ngữ (bảng trên). Mô hình tải từ Hugging Face ở lần chạy đầu nên máy khách cần mạng lúc đó; khi bán cần đóng gói sẵn mô hình hoặc có bước tải rõ ràng. Ngưỡng `UNSURE_MARGIN = 0.05` chưa hiệu chỉnh lại riêng cho mô hình mới. Cần bộ tiêu đề lớn và độc lập hơn để đánh giá thật.
- Nhãn gán theo khóa trang (tên trang hoặc kênh YouTube), nên gán "Facebook" là học thì mọi tiêu đề Facebook đều qua.
- Danh sách chờ hiện lưu cục bộ, chưa gửi về phụ huynh từ xa. Người dùng đã bỏ ý định gửi từng trang qua Gmail vì phiền; việc bấm "Học/Giải trí" ngay trong thư cần máy chủ (chưa làm). Chưa có báo cáo định kỳ qua Gmail.
- Khi AI chưa sẵn sàng (đang nạp ~36 giây, hoặc hỏng), hành vi cũ vẫn là chặn cơ bản trình duyệt; chưa đổi.
- Chưa thử với Chrome/Edge thật và chưa chạy `python main.py` (khay hệ thống, khóa một phiên, watchdog). Venv nằm trong OneDrive nên có nguy cơ hỏng lại khi đồng bộ.
