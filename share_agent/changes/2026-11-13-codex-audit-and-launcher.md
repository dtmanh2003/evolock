# Rà soát lỗi hiện tại và thêm launcher Windows

- Ngày: 2026-11-13 (Asia/Tokyo)
- Agent: Codex
- Trạng thái: Hoàn thành rà soát và launcher; các lỗi bên dưới chưa được sửa.

## Yêu cầu

Kiểm tra lại dự án, tổng hợp các chỗ chưa ổn. Trong lúc rà soát, người dùng yêu cầu thêm file BAT để tiện mở EvoLock.

## Thay đổi thực tế

| File/thư mục | Thao tác | Nội dung |
| --- | --- | --- |
| `Mo_EvoLock.bat` | Tạo | Nhấp đúp để chạy `main.py` bằng Python trong `venv`, dự phòng `.venv`; hỗ trợ đường dẫn có dấu cách, giữ lỗi trên console. |
| `README.md` | Sửa | Thêm hướng dẫn dùng file BAT. |
| `docs/ARCHITECTURE.md` | Sửa | Mô tả launcher Windows mới. |
| `share_agent/checks/audit_2026_11_13.py` | Tạo | Tái hiện 7 lỗi hiện tại bằng mock và dữ liệu tạm; không chạy blocker thật. |
| `share_agent/changes/2026-11-13-codex-audit-and-launcher.md` | Tạo | Báo cáo phát hiện và cách tiếp tục. |
| `share_agent/CHANGELOG.md` | Sửa | Thêm liên kết bản ghi này. |

Không thay đổi logic ứng dụng hay dữ liệu cá nhân. BAT gọi trực tiếp `python.exe main.py` bằng đường dẫn tuyệt đối để tương thích bộ nhận diện script của watchdog hiện tại. Console ở lại trong khi app chạy; đóng console có thể kết thúc app, nên giữ console và thoát qua ứng dụng.

## Các vấn đề đã tái hiện

P1: nên sửa trước vì ảnh hưởng việc chặn hoặc dữ liệu. P2: sai hành vi/thống kê trong một số luồng sử dụng.

### 1. P1 — Tắt cả hai AI khiến trình duyệt trong danh sách chặn vẫn chạy

- Vị trí: `evolock/services/blocker.py`, `Blocker._loop()`, khoảng dòng 456–481.
- Khi `smart_enabled=False`, bảng tiêu đề rỗng; nếu Screen AI cũng tắt/không dùng được, nhánh `if not screen_usable: continue` bỏ qua mọi process browser.
- Tái hiện: cho Chrome nằm trong danh sách chặn, tắt cả hai AI, quét một lượt; `kill()` không được gọi.
- Ảnh hưởng: không có chế độ chặn browser cơ bản khi AI bị tắt. README đã ghi giới hạn này nhưng hành vi vẫn làm danh sách chặn mất hiệu lực.
- Hướng sửa: định nghĩa rõ chế độ chặn cơ bản và phân biệt browser chính với process phụ; bổ sung kiểm tra các tổ hợp bật/tắt AI.

### 2. P1 — Xóa ứng dụng khỏi danh sách chặn khi đang học mà không xác thực

- Vị trí: `evolock/ui/app.py:1968`, `_remove_blocked_app()` và nút xóa trong `_refresh_blocked_list()`.
- Nút xóa vẫn khả dụng; hàm ghi lại danh sách và reload blocker ngay, không kiểm tra trạng thái hoặc mã/mật khẩu.
- Tái hiện: `state='studying'`, xác thực giả lập trả về False; lệnh xóa vẫn lưu danh sách rỗng mà không gọi xác thực.
- Ảnh hưởng: có thể vô hiệu hóa chặn ngay trên UI trong khi luồng dừng học vẫn yêu cầu mã.
- Hướng sửa: bảo vệ thao tác làm yếu danh sách chặn trong phiên học, theo cùng chính sách xác thực của phiên.

### 3. P1 — Mở hai phiên ứng dụng có thể ghi đè, mất nhiệm vụ

- Vị trí: `evolock/storage/tasks.py:37`, `_save()`; `evolock/ui/app.py:2184`, `main()`.
- Mỗi manager giữ snapshot riêng rồi ghi toàn bộ JSON. Điểm vào ứng dụng không có cơ chế giới hạn một phiên; watchdog cũng có thể tạo phiên thứ hai (mục 7).
- Tái hiện: tạo hai `TaskManager` cùng đọc một file trống; phiên A thêm task A, phiên B thêm task B. Đọc lại file chỉ còn task B.
- Ảnh hưởng: task của phiên A bị mất. Các manager khác cũng dùng cách ghi snapshot tương tự; đợt này chỉ tái hiện trực tiếp trên tasks.
- Hướng sửa: ưu tiên chặn nhiều instance cùng dùng dữ liệu; bổ sung ghi nguyên tử và chiến lược khóa/đồng bộ. Chỉ ghi nguyên tử không giải quyết việc snapshot cũ ghi đè snapshot mới.

### 4. P1 — Blocker vẫn có thể đóng process sau khi đã gọi stop

- Vị trí: `evolock/services/blocker.py:407`, `stop()` và `_loop()` khoảng dòng 513–545.
- `stop()` chỉ đặt `running=False`. Nếu vòng quét đang phân loại tiêu đề, sau khi phân loại xong nó vẫn đi đến `proc.kill()` mà không kiểm tra lại trạng thái.
- Tái hiện: tracker sắp đạt ngưỡng chặn, gọi `stop()` ngay trong callback phân loại giả; sau đó `kill()` vẫn được gọi.
- Ảnh hưởng: app có thể bị đóng ngay sau lúc UI báo đã mở khóa. Ngoài ra, stop/start nhanh dùng lại cùng cờ `running` có nguy cơ làm vòng quét cũ tiếp tục song song vòng mới; phần chạy song song mới xác định từ source, chưa tái hiện trong script.
- Hướng sửa: dùng tín hiệu hủy theo từng lần chạy, kiểm tra hủy trước tác động process và quản lý vòng đời worker.

### 5. P2 — Chuyển từ giờ chơi về học không chốt lịch sử giờ chơi

- Vị trí: `evolock/ui/app.py:1612`, `_begin_studying_state()`; `:1726`, `_enter_unlocked()`; `:1770`, `_record_play_session()`.
- Khi đang chơi và bấm học tiếp, `_reset_timers()` dừng timer nhưng không ghi/chốt `_unlock_started_at`.
- Tái hiện: đặt giờ chơi đã bắt đầu 10 phút trước, gọi `_begin_studying_state()`; lịch sử chưa được ghi và timestamp giờ chơi cũ vẫn còn.
- Ảnh hưởng: nếu học xong bình thường, timestamp cũ bị ghi đè và phần chơi trước đó mất; nếu dừng/thoát giữa phiên học, khoảng học có thể bị cộng vào giờ chơi. AI Coach nhận số liệu sai.
- Hướng sửa: chốt phiên chơi trước khi bước vào `studying` hoặc bắt đầu một khoảng chơi mới.

### 6. P2 — Thống kê ngày không reset khi ứng dụng mở qua nửa đêm

- Vị trí: `evolock/services/gamification.py:93`, `_check_streak()` và `:164`, `on_study_complete()`.
- Reset `today_study_minutes` chỉ chạy khi khởi tạo manager. Hoạt động ngày mới không kiểm tra lại `today_date` trước khi cộng phút.
- Tái hiện: giữ manager với ngày hôm qua và 50 phút, cộng 10 phút hôm nay; tổng ngày thành 60, ngày vẫn là hôm qua và mở thành tích học 60 phút/ngày.
- Hướng sửa: chuẩn hóa ngày trước mỗi lần cập nhật số liệu; thêm kiểm tra chuyển ngày và phiên học băng qua nửa đêm.

### 7. P2 — Watchdog không nhận diện cách chạy `python -m evolock`

- Vị trí: `evolock/integrations/watchdog.py:18`, `_is_running()`.
- Hàm chỉ coi `cmdline[1]` là đường dẫn script. Với `python -m evolock`, giá trị này là `-m`.
- Tái hiện: process giả có command line trên; `_is_running()` trả False.
- Ảnh hưởng: watchdog có thể mở thêm `main.py` dù ứng dụng đã chạy, góp phần gây lỗi nhiều instance ở mục 3. Giới hạn đã được nêu trong bàn giao trước.
- Hướng sửa: nhận diện đủ entry point hoặc dùng cơ chế single-instance chung. File BAT mới sử dụng `main.py` nên tránh riêng trường hợp này.

## Kiểm tra

| Lệnh hoặc cách kiểm tra | Kết quả |
| --- | --- |
| `.\venv\Scripts\python.exe -B -m unittest discover -s tests -v` | 6/6 đạt. Bộ hiện có tập trung import, launcher, đường dẫn và đọc/ghi cơ bản; không phủ 7 tình huống trên. |
| `.\venv\Scripts\python.exe -B -m pip check` | `No broken requirements found.` |
| `.\venv\Scripts\python.exe -B share_agent/checks/audit_2026_11_13.py` | Tái hiện 7/7 vấn đề trên bằng mock/dữ liệu tạm. Script đạt nghĩa là lỗi hiện tại đã được xác nhận, KHÔNG nghĩa là ứng dụng đã hết lỗi. |
| Chạy BAT bằng `cmd /d /c` trong fixture tạm có dấu cách, từ thư mục khác; dùng `main.py` giả chỉ kiểm tra cwd và in marker | Đạt cả lựa chọn `venv` và dự phòng `.venv`; không mở ứng dụng thật. |

## Giới hạn và việc còn lại

- Chưa sửa 7 lỗi nghiệp vụ vì yêu cầu hiện tại là rà soát/tổng hợp; chỉ bổ sung launcher và tài liệu.
- Chưa kiểm thử tương tác GUI, model AI thật, Gmail, Credential Manager, Windows startup hoặc watchdog thật. Không đóng process thật và không gửi dữ liệu ra dịch vụ ngoài.
- Không kiểm tra nội dung dữ liệu cá nhân để tìm lỗi; báo cáo dựa trên source, mock và file tạm. Chưa chứng minh nguyên nhân chính xác của lỗi cụ thể mà người dùng đang thấy nếu chưa có mô tả triệu chứng.
- Các điểm cần cải thiện thêm từ source: trạng thái bật/tắt Smart Block và Screen AI chưa được lưu qua lần mở app; JSON ghi trực tiếp và nhiều lỗi đọc bị bỏ qua; callback blocker thao tác widget trực tiếp từ worker; giao diện ghi chu kỳ Screen AI 20 giây trong khi cooldown là 10 giây. Những điểm này chưa được tái hiện đầu-cuối trong lượt này.
- Không coi danh sách này là xác nhận đã tìm hết mọi lỗi. Kiểm thử hiện tại chưa đủ bao phủ chuyển trạng thái, đồng thời và lỗi dịch vụ ngoài.

## Hướng dẫn tiếp tục / phục hồi

Ưu tiên sửa các mục P1 về chặn và dữ liệu, sau đó chốt lịch sử và reset ngày. Khi sửa, chuyển các tình huống tái hiện thành regression tests kiểm tra hành vi mong muốn; không giữ assertion xác nhận lỗi như tiêu chí chất lượng lâu dài.

Source và dữ liệu runtime không bị sửa trong lượt rà soát. Nếu không cần launcher, có thể bỏ riêng `Mo_EvoLock.bat` và hướng dẫn tương ứng; giữ bản ghi này để bảo toàn lịch sử.
