# Sửa độ ổn định AI Coach, lưu dữ liệu và browser fallback

- Ngày: 2026-11-16 (Asia/Tokyo)
- Agent: Codex
- Trạng thái: Hoàn thành nhóm ưu tiên; còn giới hạn bên dưới.

## Yêu cầu
Tiếp tục xử lý lỗi ưu tiên đã rà soát. Người dùng gửi thêm ảnh màn hình tập trung nhưng chưa chỉ định thay đổi cụ thể trong ảnh.

## Thay đổi thực tế
- AI Coach chỉ chạy một lượt; yêu cầu tự động trong lúc bận được gộp thành một lượt tiếp theo. Chuẩn bị dữ liệu trên UI thread, deepcopy lịch sử trước khi gọi backend. Lỗi chuẩn bị/backend/khởi chạy thread trả nút về trạng thái sử dụng được; không ghi đè cache bằng lỗi. Hoàn tất tự động không đổi tab.
- Lưu kết quả và timestamp AI trong một lần ghi config bằng set_many.
- Decorator committed_state kiểm tra dữ liệu khi load/save và khôi phục các thuộc tính manager về bản lưu thành công gần nhất nếu save lỗi. Áp dụng config, tasks, history, ba logger, stats và whitelist.
- Kiểm tra kiểu collection JSON, kiểu trường dataclass/config, số âm và ngày ISO; không tự xóa/reset file sai cấu trúc. Đây là kiểm tra cấu trúc cơ bản, chưa phải toàn bộ quy tắc nghiệp vụ/schema migration.
- Browser có trong blocklist nhưng không lấy được title và không có Screen AI dùng được: fallback blocklist cho process gốc; bỏ qua renderer/helper nhận diện qua command line. Giữ kiểm tra phiên còn hoạt động trước kill.

| File | Thao tác | Nội dung |
| --- | --- | --- |
| evolock/storage/state.py | Tạo | Validation và rollback bộ nhớ |
| evolock/storage/json_file.py | Sửa | Kiểm tra collection khi đọc |
| evolock/storage/config.py | Sửa | Validation, rollback, set_many |
| evolock/storage/tasks.py, history.py, activity_log.py, override_log.py, pw_log.py | Sửa | Áp dụng validation và rollback |
| evolock/services/gamification.py | Sửa | Validate stats và rollback |
| evolock/services/blocker.py | Sửa | Validate app/channel lists, rollback whitelist, browser fallback |
| evolock/ui/app.py | Sửa | Điều phối và xử lý lỗi AI Coach |
| tests/test_reliability.py | Tạo | 8 regression tests |
| docs/ARCHITECTURE.md | Sửa | Hành vi lưu và phân tích |
| share_agent/CHANGELOG.md | Sửa | Liên kết bàn giao |

## Kiểm tra
- `.\venv\Scripts\python.exe -B -m unittest discover -s tests -v`: 68/68 đạt.
- Sau bổ sung assertion xác nhận backend thực sự được gọi: chạy lại với `-q`, 68/68 đạt.
- Test dùng file tạm, mock backend/process/UI. Không gửi email, không chỉnh startup, không chạy chặn thật, không sửa data cá nhân.

## Giới hạn và việc còn lại
- Chưa kiểm thử GUI tương tác hoặc backend thật. Không thay layout/thanh cuộn trong ảnh mới.
- Rollback ở cấp từng manager/file; chưa có transaction xuyên history/stats/logs. Các tham chiếu ngoài manager tới object cũ không được khôi phục tại chỗ.
- Validator chưa kiểm tra toàn bộ enum, quan hệ ID hoặc định dạng giờ; field không biết trong config được giữ để tương thích. Các manager phải tiếp tục được sửa trên UI thread.
- Nhận diện process con browser dựa trên command line; cần xác minh thêm với phiên bản browser thực tế. Không đọc được command line thì xử lý theo exception psutil có sẵn.
- Gmail chỉ nhập địa chỉ vẫn cần dịch vụ; phục hồi mã, quyền kiểm soát chụp màn hình, nhập thời lượng, chia ngày qua nửa đêm và test sleep/resume còn lại như audit trước.

## Hướng dẫn tiếp tục / phục hồi
Khởi động lại app để nạp source. Đọc state.py và test_reliability.py trước khi mở rộng schema. File .bak vẫn là bản trước lần ghi theo json_file.py; không phục hồi cả data hàng loạt. Không khôi phục UI kỹ thuật đã ẩn ở lượt trước.
