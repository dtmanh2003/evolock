# Sửa 7 vấn đề từ báo cáo rà soát

- Ngày: 2026-11-13 (Asia/Tokyo)
- Agent: Codex
- Trạng thái: Hoàn thành sửa source và kiểm tra hồi quy.

## Yêu cầu

Người dùng yêu cầu sửa các lỗi vừa tổng hợp và cập nhật bàn giao. Phạm vi là 7 mục trong `2026-11-13-codex-audit-and-launcher.md`. Báo cáo cũ được giữ nguyên như lịch sử trước sửa.

## Thay đổi thực tế

| Vấn đề | Hành vi sau sửa |
| --- | --- |
| 1. Tắt AI làm lọt browser | Khi Smart Block tắt và Screen AI tắt/không dùng được, áp dụng danh sách chặn trực tiếp cho browser. Nếu Screen AI đang hoạt động, vẫn giữ ngoại lệ học theo kết quả AI. |
| 2. Xóa app khi học không cần xác thực | Khi `studying`/`locked`, thao tác xóa gọi xác thực mã phiên hoặc mật khẩu. Nếu hủy/sai mã thì không ghi danh sách và không reload. Xác thực quản lý không xóa mã phiên và không ghi nhầm là dừng học. |
| 3. Hai cửa sổ cùng ghi đè dữ liệu | Tất cả launcher đi qua `main()` và giành khóa liên tiến trình trước khi khởi tạo manager. Phiên thứ hai báo đã chạy và không nạp/ghi dữ liệu. Khóa theo thư mục data, Windows giải phóng khi process kết thúc. |
| 4. Worker cũ vẫn đóng process sau khi mở khóa | Mỗi lần start có Event hủy riêng. Stop và kiểm tra ngay trước `kill()` dùng cùng lock; vòng đang phân loại không được kill sau stop. Bật lại không làm sống lại Event cũ. Kiểm tra lại app còn trong danh sách trước khi kill. |
| 5. Giờ chơi bị mất/tính lẫn vào học | Chốt `_unlock_started_at` trước khi vào học hoặc mở một khoảng chơi mới; timestamp cũ được xóa sau ghi, tránh ghi hai lần. |
| 6. Thống kê cộng dồn qua ngày | Kiểm tra/reset ngày trước cập nhật thưởng học, task và phạt; UI kiểm tra đổi ngày mỗi phút để làm mới thống kê/lịch sử ngay cả khi không tương tác. |
| 7. Watchdog không nhận diện chạy module | Ưu tiên kiểm tra khóa phiên. Dò dự phòng nhận diện `main.py`, đường dẫn tương đối theo cwd của process, `-m evolock` tại dự án và các cờ Python như `-B`, `-W`, `-X`. |

Các sửa liên quan: callback log của blocker được chuyển về luồng Tk bằng `root.after()`; thoát ứng dụng dừng cả hai timer và hủy lịch cập nhật ngày.

| File/thư mục | Thao tác | Nội dung |
| --- | --- | --- |
| `evolock/integrations/instance.py` | Tạo | `InstanceLock`, khóa byte-range qua `msvcrt`; helper kiểm tra phiên đang chạy. |
| `evolock/integrations/watchdog.py` | Sửa | Kiểm tra khóa và các entry point/command line. |
| `evolock/services/blocker.py` | Sửa | Chặn browser cơ bản, hủy theo từng worker, đồng bộ stop/kill và kiểm tra lại danh sách. |
| `evolock/services/gamification.py` | Sửa | Reset ngày trước cập nhật số liệu. |
| `evolock/ui/app.py` | Sửa | Khóa một phiên, bảo vệ xóa app, giữ mã khi quản lý, chốt giờ chơi, làm mới ngày, callback UI và dừng timer khi thoát. |
| `tests/test_audit_regressions.py` | Tạo | 22 test methods mới cho các hành vi sửa, có subtests cho trạng thái/cấu hình/entry point. |
| `share_agent/checks/audit_2026_11_13.py` | Sửa | Chạy bộ hồi quy mới thay cho assertion xác nhận lỗi cũ. |
| `README.md`, `docs/ARCHITECTURE.md` | Sửa | Cập nhật cơ chế chặn, xác thực, khóa phiên, watchdog, kiểm tra và giới hạn lưu trữ. |
| `share_agent/CHANGELOG.md` | Sửa | Thêm bản ghi này lên đầu. |

`Mo_EvoLock.bat` tiếp tục dùng được, không cần thay launcher hoặc cài dependency. Không đổi schema JSON, không sửa nội dung dữ liệu cá nhân và không sửa startup Windows.

## Kiểm tra

| Lệnh hoặc cách kiểm tra | Kết quả |
| --- | --- |
| `.\venv\Scripts\python.exe -B -m unittest discover -s tests -v` | 28/28 đạt: 6 kiểm tra cấu trúc/lưu trữ hiện có và 22 kiểm tra hồi quy mới. |
| Khóa file giữa hai process Python riêng trong thư mục tạm (nằm trong suite) | Process thứ hai không lấy được khóa; lấy được sau khi chủ khóa release; khóa cũng được giải phóng khi process con thoát mà không gọi release. |
| Worker đang chờ phân loại được stop rồi start lại (nằm trong suite) | Event cũ bị hủy, Event mới độc lập; worker cũ kết thúc và không kill process giả. |
| Xác thực với Config tạm (nằm trong suite) | Quản lý danh sách bằng mã hợp lệ giữ nguyên mã phiên; mã sai bị từ chối. |
| Chuyển từ 12/11 sang 13/11 bằng đồng hồ mock (nằm trong suite) | 50 phút ngày trước không cộng vào 10 phút ngày mới; không mở sai thành tích 60 phút/ngày; check-in chỉ cộng một lần/ngày. |

Tất cả process bị chặn, widget và AI đều được mock; chỉ subprocess phục vụ kiểm tra khóa file là Python thật. Không gửi Gmail, gọi AI, truy cập credential thật hay đóng ứng dụng thật.

## Giới hạn và việc còn lại

- Chưa kiểm thử tương tác GUI/AI/Gmail/Windows startup đầu-cuối. Kết quả kiểm thử xác nhận logic và các tình huống hồi quy nêu trên, không phải bảo đảm ứng dụng không còn lỗi khác.
- Cần thoát các phiên EvoLock/watchdog đang chạy rồi mở lại để nạp source mới. Phiên của bản cũ không tự nhận cơ chế khóa mới.
- Cơ chế khóa bảo vệ các launcher hiện hành. Các manager JSON vẫn không có transaction/ghi nguyên tử riêng: script ngoài tự gọi manager hoặc phiên source cũ có thể ghi dữ liệu nếu bỏ qua khóa. Không tự chạy script chỉnh dữ liệu khi GUI đang mở.
- Trong chế độ Smart Block, process browser không có tiêu đề và không có Screen AI dùng được vẫn được bỏ qua nhằm tránh chặn nhầm process phụ. Chế độ chặn cơ bản khi tắt AI đã được sửa theo mục 1.
- Không sửa hồi tố lịch sử/EXP sai đã tồn tại trước bản này. Phân chia một phiên học băng qua nửa đêm thành từng ngày chưa thuộc bản sửa; thời lượng phiên vẫn ghi theo cơ chế cũ.
- Những quan sát ngoài 7 mục như lưu tùy chọn bật/tắt AI qua restart, nhãn cooldown 20 giây, hoặc độ chính xác model chưa được xử lý trong lượt này.

## Hướng dẫn tiếp tục / phục hồi

Thoát bản đang chạy qua menu ứng dụng rồi mở `Mo_EvoLock.bat`; nếu dùng watchdog riêng thì khởi động lại watchdog. Không cần xóa `data/.instance.lock`: file tồn tại không có nghĩa là đang bị khóa; Windows quản lý khóa qua handle.

Khi sửa tiếp, chạy toàn bộ unittest suite. Có thể chạy riêng nhóm audit bằng `.\venv\Scripts\python.exe -B share_agent/checks/audit_2026_11_13.py`; thành công giờ có nghĩa hành vi mong muốn đạt test, không phải các lỗi cũ còn tái hiện.

Không phục hồi nguyên thư mục `data/` từ backup cũ để hoàn tác source; bản sửa không đổi schema và dữ liệu mới của người dùng cần được giữ nguyên.
