# Ưu tiên dữ liệu, timer và cài đặt AI

- Ngày: 2026-11-13 (Asia/Tokyo)
- Agent: Codex
- Trạng thái: Hoàn thành các hạng mục dưới đây.

## Yêu cầu

Làm trước các phần ưu tiên từ rà soát đợt 2; người dùng yêu cầu tiếp tục trong lúc thực hiện. Giữ nguyên cơ chế gửi Gmail để sửa sau. Đã đọc bàn giao AI Coach của Claude và giữ nguyên phần findings/prompt/data của lượt đó.

## Thay đổi thực tế

| File/thư mục | Thao tác | Nội dung |
| --- | --- | --- |
| `evolock/storage/json_file.py` | Tạo | Đọc JSON object; lỗi đọc báo DataFileError; ghi temp cùng thư mục, flush/fsync rồi replace; giữ bản hợp lệ trước trong `.bak`; không ghi đè JSON hỏng. |
| `evolock/storage/config.py`, `tasks.py`, `history.py`, `activity_log.py`, `override_log.py`, `pw_log.py` | Sửa | Dùng helper lưu trữ, không nuốt lỗi đọc thành dữ liệu mặc định/rỗng. Config deepcopy defaults, lưu lựa chọn Smart/Screen. Các bộ lọc nhật ký lấy đúng N ngày lịch và bỏ ngày tương lai. |
| `evolock/services/gamification.py`, `blocker.py` | Sửa | Áp dụng helper cho stats, blocklist và whitelist. Giữ thuật toán AI/chặn hiện hành. |
| `evolock/services/timer.py` | Sửa | Start idempotent; Event mỗi lượt chạy, sleep có thể hủy, ceil thời gian còn lại; dispatcher loại callback cũ sau stop/reset. Không phát tick 0 hai lần. |
| `evolock/ui/app.py` | Sửa | Thông báo lỗi dữ liệu khi khởi động và callback Tk; nối dispatcher timer; lưu và khôi phục toggle AI, đồng bộ checkbox/backend, xóa API key vẫn dùng được Ollama; nhãn Screen AI 10 giây. |
| `tests/test_priority_fixes.py` | Tạo | 9 test methods mới, có subtests cho 9 manager/nguồn JSON và 4 loại nhật ký. |
| `README.md`, `docs/ARCHITECTURE.md` | Sửa | Mô tả backup/phục hồi, cấu hình, timer và cửa sổ ngày. |
| `share_agent/CHANGELOG.md` | Sửa | Thêm bản ghi này. |

Không thay đổi source Gmail, AI Coach hoặc nội dung dữ liệu người dùng. `.bak` chỉ được tạo khi ứng dụng thực sự lưu file hiện có; kiểm thử dùng thư mục tạm.

## Kiểm tra

`.\venv\Scripts\python.exe -B -m unittest discover -s tests -q`: **52/52 đạt**, bao gồm 15 test AI Coach của Claude và các hồi quy trước.

Các tình huống mới: JSON lỗi cú pháp/root sai kiểu không bị reset ở 9 nguồn dữ liệu; lỗi replace giữ file gốc và backup, dọn temp; JSON hỏng sau load không bị lần save tiếp theo ghi đè; double-start không tạo worker thứ hai; restart hủy generation cũ; callback đã xếp hàng bị bỏ khi stop; đếm ngược không hết sớm do làm tròn xuống; cấu hình AI giữ qua reload và vẫn bật với Ollama khi bỏ API key; 4 bộ lọc log đúng 7/1/0 ngày và loại ngày tương lai.

## Giới hạn và việc còn lại

- Chưa chạy GUI/AI/Gmail thật hoặc mô phỏng mất điện vật lý. Atomic replace không bảo đảm transaction giữa nhiều JSON, và không đồng bộ script ngoài bỏ qua khóa một phiên.
- Helper xác thực cú pháp và root object; chưa có schema đầy đủ cho mọi trường dữ liệu. Một số object có trường sai kiểu vẫn cần validation riêng.
- Khi lỗi ghi, file cũ được giữ nhưng object đang chạy có thể đã thay đổi trong bộ nhớ. UI báo lỗi; nên thoát và khởi động lại sau khi xử lý nguyên nhân trước khi tiếp tục thao tác. Chưa triển khai rollback toàn bộ state giữa các manager.
- Không tự phục hồi file hỏng từ `.bak`, tránh âm thầm quay về dữ liệu cũ. Backup nằm trong `data/`, chứa thông tin riêng tư như file gốc.
- Còn ngoài phạm vi: phân bổ phiên qua nửa đêm, chống nhiều request AI Coach ghi kết quả ngược thứ tự, xử lý lỗi keyring/Gmail và kiểm thử GUI đầu-cuối.

## Hướng dẫn tiếp tục / phục hồi

Thoát app cũ rồi mở `Mo_EvoLock.bat` để nạp source mới. Nếu báo lỗi dữ liệu: giữ nguyên file hỏng, thoát app/watchdog, đối chiếu `.bak` và chỉ phục hồi file cần thiết; không xóa toàn bộ data. Không đăng nội dung backup/credential vào tài liệu bàn giao.

Khi sửa tiếp, duy trì kiểm tra 52 test và không ghi đè thay đổi AI Coach của Claude. Hai khóa cấu hình AI mới là tùy chọn, dữ liệu cũ dùng mặc định tương thích.
