# Kiến trúc và bản đồ source EvoLock

## Nguyên tắc tổ chức

Source đang chạy nằm trong package `evolock/`. Các file Python ở thư mục gốc chỉ là launcher. Dữ liệu, tài nguyên, tài liệu và bản sao lịch sử được tách khỏi source để dễ tìm và tránh sửa nhầm bản `*-WIN-*`.

Đây là bước chia module theo trách nhiệm, chưa phải kiến trúc phân tầng nghiêm ngặt: `ui/app.py` vẫn điều phối nhiều nghiệp vụ; `services/gamification.py` và `services/blocker.py` vẫn có phần đọc/ghi JSON. Khi mở rộng lớn, có thể đưa các phần đó vào lớp lưu trữ riêng.

| Vùng | Trách nhiệm | File chính |
| --- | --- | --- |
| `ui/` | Widget, hộp thoại, callback và trạng thái phiên | `app.py` |
| `services/` | Chặn process, phân tích AI, thời gian và EXP | `blocker.py`, `ai_coach.py`, `timer.py`, `gamification.py` |
| `storage/` | Đọc/ghi JSON và quản lý cấu hình, nhiệm vụ, lịch sử, nhật ký | `config.py`, `tasks.py`, `history.py`, `activity_log.py`, `override_log.py`, `pw_log.py` |
| `integrations/` | Hệ điều hành và dịch vụ ngoài ứng dụng | `protection.py`, `session_code.py`, `watchdog.py`, `instance.py` |
| `paths.py` | Nguồn duy nhất cho các đường dẫn runtime | `PROJECT_ROOT`, `DATA_DIR`, `ASSETS_DIR`, `MAIN_SCRIPT`, `MASCOT_FRAMES_DIR` |
| `i18n.py`, `locales/` | Đa ngôn ngữ: `tr()` (gốc tiếng Nhật) và bảng dịch `vi.py`, `en.py`; xem README mục "Ngôn ngữ giao diện" | `tr`, `translate`, `set_language`, `LANGUAGES` |
| `storage/site_labels.py` | Nhãn học/giải trí do phụ huynh gán cho trang AI không chắc, và danh sách chờ (`data/site_labels.json`); `blocker.site_key` tạo khóa trang | `SiteLabels`, `UNSURE_MARGIN` |
| `ui/charts.py` | Biểu đồ vẽ bằng Canvas dùng cho tab 記録 và AIコーチ | `BarChart`, `HBarChart`, `ProgressBar` |

## Luồng ứng dụng

```text
main.py hoặc python -m evolock
    → evolock.ui.app.main()
    → giành khóa một phiên trên thư mục data (dừng nếu đã có phiên khác)
    → tạo Tk + EvoLockApp
    → nạp Config / các manager / Blocker
    → giao diện điều phối học, mở khóa, lịch sử và AI

idle → studying → unlocked → locked → studying
          │           ↑
          ├─ hoàn thành nhiệm vụ
          └─ dừng có xác thực → idle
```

`Mo_EvoLock.bat` là launcher nhấp đúp trên Windows: chọn `venv/Scripts/python.exe`, dự phòng `.venv/Scripts/python.exe`, đặt thư mục làm việc về gốc dự án và chạy `main.py`. Cửa sổ console giữ thông báo nếu ứng dụng thoát với mã lỗi. Launcher không tự chạy watchdog.

- `studying` và `locked`: blocker hoạt động.
- `unlocked`: blocker dừng, bộ đếm giờ chơi chạy.
- Mỗi lần bật blocker có một `threading.Event` hủy riêng; dừng và kiểm tra trước `kill()` dùng cùng lock. Worker cũ không được hồi sinh khi bật lại. Callback ghi log UI của blocker được đưa về luồng Tk bằng `root.after()`.
- Chốt giờ chơi trước khi học tiếp hoặc nhận phần thưởng mở khóa mới. Thống kê reset ngày trước khi cộng thưởng và UI kiểm tra đổi ngày mỗi phút.
- `CountdownTimer` dùng `time.monotonic()` và gọi callback từ luồng nền; phần UI bọc các callback cập nhật giao diện bằng `root.after()`.
- Khi hoàn thành phiên học, UI lưu lịch sử, cộng EXP và chạy phân tích Coach trên luồng nền.
- Phân loại tiêu đề, phân loại màn hình, SMTP và AI Coach sử dụng luồng nền để không giữ luồng giao diện trong khi chờ.

## Bản đồ đường dẫn sau khi sắp xếp

| Trước đây | Hiện tại |
| --- | --- |
| `main.py` chứa toàn bộ UI | `evolock/ui/app.py`; `main.py` mới chỉ gọi `main()` |
| `blocker.py`, `ai_coach.py`, `gamification.py`, `timer.py` | `evolock/services/` |
| `config.py`, `tasks.py`, `history.py`, `activity_log.py`, `override_log.py`, `pw_log.py` | `evolock/storage/` |
| `session_code.py`, `protection.py`, `watchdog.py` | `evolock/integrations/`; giữ launcher `watchdog.py` ở gốc |
| JSON tại thư mục gốc | `data/`, giữ nguyên nội dung |
| `mascot_frames/` | `assets/mascot_frames/` |
| `okhoafile-20260924T021942Z-1-001/` | `assets/source_media/okhoafile-20260924T021942Z-1-001/` |
| `ABOUT.txt` | `docs/ABOUT.legacy.txt` |
| `launch*.log` | `logs/` |
| `*-WIN-*` tại thư mục gốc | `archive/sync_conflicts/` |
| `_backup_before_merge/` | `archive/before_merge/` |
| Bytecode `.pyc` và cache ở gốc | `archive/bytecode/` |
| Source và JSON trước đợt chia thư mục | Bản sao trong `archive/before_restructure/` |

`venv/`, `venv_broken_1790218479/`, `.claude/`, `.codex-build/` và `output/` được giữ tại vị trí cũ. Đặc biệt không di chuyển virtualenv đang dùng vì chúng chứa đường dẫn gắn với vị trí cài đặt.

## Quy ước khi sửa source

1. Import module nội bộ bằng tên đầy đủ, ví dụ `from evolock.services.timer import CountdownTimer`. Không dùng lại `from timer import ...` vì đã từng xung đột với module ngoài dự án.
2. Lấy đường dẫn từ `evolock.paths`; không ghép dữ liệu theo `Path.cwd()` hoặc `Path(__file__).parent` trong từng module.
3. Mã UI mới đặt trong `ui/`; nghiệp vụ đặt trong `services/`; quản lý JSON đặt trong `storage/`; kết nối hệ thống/dịch vụ đặt trong `integrations/`.
4. Giữ `main.py` và `watchdog.py` ở gốc để shortcut Windows hiện có tiếp tục tìm đúng file. Cập nhật vị trí Python trong startup nếu thay môi trường ảo.
5. Không chạy các bản Python trong `archive/`; chúng chỉ dùng đối chiếu hoặc phục hồi có chọn lọc.
6. Tạo kiểm tra đọc/ghi bằng file tạm và mock tác động bên ngoài. Không chạy blocker, gửi email hay sửa Registry chỉ để kiểm tra import.
7. Cập nhật README nếu đổi cách chạy/cấu hình; ghi bàn giao vào `share_agent/` theo `AGENTS.md`.

## Dữ liệu và khả năng chia sẻ source

Dữ liệu runtime được chuyển trực tiếp sang `data/`, không đổi schema JSON. Credential Manager vẫn dùng service/user key cũ, nên việc đổi thư mục source không đổi định danh credential.

`.gitignore` giữ dữ liệu cá nhân, backup và môi trường ảo ngoài source được chia sẻ. `data/blocked.example.json` là cấu hình mẫu duy nhất được cung cấp để khởi tạo danh sách chặn; không ghi đè dữ liệu hiện có khi dùng mẫu.

`integrations/instance.py` dùng khóa byte-range Windows (`msvcrt`) trên `data/.instance.lock`. Launcher giành khóa trước khi tạo manager, giữ đến khi GUI đóng và giải phóng trong `finally`; Windows cũng giải phóng nếu process bị kết thúc. Watchdog kiểm tra khóa này trước khi dò command line. Phải thoát các phiên của bản cũ rồi mở lại sau cập nhật vì chúng chưa có cơ chế khóa.

Các manager dùng `storage/json_file.py`: đọc JSON object, báo DataFileError khi không đọc được, ghi file tạm rồi os.replace và giữ bản trước trong .bak. Chưa có transaction giữa nhiều file hoặc kiểm tra schema đầy đủ cho mọi trường. Khóa phiên bảo vệ các launcher của ứng dụng, không bảo vệ script ngoài tự gọi manager hoặc chỉnh JSON. Backup trong `archive/before_restructure/` có thể chứa thông tin cá nhân, cần giữ riêng như `data/`.

## Kiểm tra và giới hạn

`tests/test_project_structure.py` kiểm tra import từ thư mục khác, ba entry point, đường dẫn startup/watchdog/assets/data và đọc/ghi các manager trên file tạm.

`tests/test_audit_regressions.py` kiểm tra các lỗi từ đợt rà soát: fallback chặn browser, hủy worker/khởi động lại, xác thực sửa danh sách, chốt giờ nghỉ, chuyển ngày, khóa giữa hai process và nhận diện watchdog. `share_agent/checks/audit_2026_11_13.py` chạy bộ hồi quy này; báo cáo lỗi trước sửa được giữ nguyên để tham khảo lịch sử.

Kiểm tra này không khởi động phiên học thật, gọi AI/SMTP, truy cập Credential Manager để ghi credential hoặc thay đổi Registry. Các luồng đó cần kiểm thử tích hợp riêng khi sửa hành vi liên quan.

Timer dùng Event riêng cho mỗi lần chạy và dispatcher kiểm tra hủy ngay khi callback được giao cho Tk. Cấu hình bổ sung `smart_enabled` và `screen_enabled` (mặc định False từ 2026-11-16); trạng thái Screen thực tế còn phụ thuộc backend. `tests/test_priority_fixes.py` kiểm tra file hỏng, lỗi replace, timer, cài đặt AI và cửa sổ ngày.

Bảo vệ phiên học: `protection_enabled` mặc định False. `_begin_studying_state` chụp trạng thái vào `_session_protected`; stop/quit khi đang học dùng xác nhận hoặc mã local theo snapshot đó. UI không cho đổi bảo vệ trong phiên. SMTP cũ không còn được gọi từ `_enter_studying`; credential cũ được giữ. `tests/test_optional_protection.py` kiểm tra mặc định, hủy/sai mã, lưu hash và điều kiện thay đổi bảo vệ.


## Độ nhất quán dữ liệu và AI Coach

`storage/state.py` bổ sung kiểm tra kiểu dữ liệu và snapshot lần ghi thành công cho các manager. Khi `_save` lỗi, thuộc tính manager được thay bằng snapshot; không có transaction xuyên nhiều file và không cập nhật các tham chiếu ngoài tới object cũ. `json_file.read_json` kiểm tra collection trước khi tạo record; atomic replace và `.bak` vẫn giữ nguyên.

AI Coach chuẩn bị dữ liệu trên UI thread, gọi backend trong một worker tại một thời điểm. Yêu cầu tự động trong lúc bận được gộp; hoàn tất không tự đổi tab. Kết quả và thời điểm được lưu chung bằng `Config.set_many`. Browser trong blocklist không có title/Screen AI khả dụng dùng fallback theo process gốc, loại helper qua command line.


## Cập nhật trải nghiệm phiên học 2026-11-16

- Screen AI yêu cầu `screen_enabled` và `screen_consent_destination` khớp backend hiện tại (`local`/`anthropic`). Dữ liệu cũ thiếu consent không kích hoạt capture. Consent lưu bằng set_many; đổi nơi xử lý sẽ tắt cho đến khi xác nhận lại. Không thêm UI model/API key.
- `_enter_studying` kiểm tra cả hai ô thời lượng trước mọi thay đổi phiên. Đồng hồ hero giảm từ 56 xuống 44 pt, giảm padding và chiều cao nút.
- `Session` thêm `session_id` và `reward_pending`; bản ghi cũ mặc định không pending. Phiên mới ghi history trước, sau đó `HistoryManager.settle_rewards` gọi `GameManager.on_study_complete` có ID. Stats lưu `rewarded_sessions` cùng điểm trong một lần ghi; nếu history chưa xác nhận được, chạy lại sẽ không cộng trùng.
- Reconcile khi khởi động và trước phiên học mới. Đây là cơ chế hoàn tất bù có thể thử lại, không phải transaction đồng thời giữa các file. Khi đĩa vẫn lỗi, thao tác dừng và báo lỗi. Task rewards/logs chưa có cơ chế tương tự.
- Phần thưởng phục hồi của ngày trước không cộng phút vào hôm nay hoặc nhận check-in hôm nay; chưa tái dựng chính xác hệ số streak của thời điểm cũ. ID đã thưởng chưa được dọn để đảm bảo không cộng trùng.
