# Chia thư mục source, viết README và thiết lập bàn giao giữa agent

- Ngày: 2026-11-13 (Asia/Tokyo)
- Agent: Codex
- Trạng thái: Hoàn thành

## Yêu cầu

Người dùng yêu cầu đọc dự án và viết README, sau đó bổ sung yêu cầu chia thư mục để dễ kiểm soát source và tạo quy tắc lưu tài liệu thay đổi trong `share_agent/` để Claude cũng đọc được.

## Thay đổi thực tế

Chuyển các module Python từ thư mục gốc vào package `evolock/`, chia theo trách nhiệm. Cập nhật import tuyệt đối và đường dẫn runtime để dữ liệu/ảnh vẫn được tìm đúng sau khi di chuyển. Giữ launcher `main.py` và `watchdog.py` ở gốc; thêm điểm vào `python -m evolock`.

| File/thư mục | Thao tác | Nội dung |
| --- | --- | --- |
| `evolock/ui/app.py` | Di chuyển + sửa import | UI cũ từ `main.py`, dùng import theo package và đường dẫn mascot tập trung. |
| `evolock/services/` | Di chuyển + sửa đường dẫn | `blocker.py`, `ai_coach.py`, `gamification.py`, `timer.py`. |
| `evolock/storage/` | Di chuyển + sửa đường dẫn/import | Config, tasks, history, activity log, override log, password log. |
| `evolock/integrations/` | Di chuyển + sửa đường dẫn | Gmail/keyring, Windows startup, watchdog. Vòng chạy watchdog được đặt trong hàm `main()` để launcher gọi. |
| `evolock/paths.py` | Tạo | Tập trung `PROJECT_ROOT`, `DATA_DIR`, `ASSETS_DIR`, `MAIN_SCRIPT`, `MASCOT_FRAMES_DIR`. |
| `evolock/__init__.py`, `evolock/__main__.py` và `__init__.py` các lớp | Tạo | Khai báo package và điểm khởi động module. |
| `main.py`, `watchdog.py` | Tạo lại dưới dạng launcher | Giữ đường dẫn khởi động cũ. |
| `data/` | Di chuyển dữ liệu + thêm mẫu | JSON đang dùng giữ nguyên nội dung; thêm `blocked.example.json` và `.gitkeep`. |
| `assets/mascot_frames/`, `assets/source_media/` | Di chuyển | Frame PNG runtime và GIF/MP4 nguồn. |
| `archive/before_restructure/` | Tạo bản sao | Source Python và JSON chính trước khi sửa cấu trúc. |
| `archive/sync_conflicts/` | Di chuyển | Các bản sao `*-WIN-*` ở gốc. |
| `archive/before_merge/`, `archive/bytecode/` | Di chuyển | Backup cũ, `.pyc` và cache cũ. |
| `logs/` | Di chuyển | Các file `launch*.log`. |
| `docs/ABOUT.legacy.txt` | Di chuyển | `ABOUT.txt` cũ, giữ làm tài liệu lịch sử. |
| `README.md`, `docs/ARCHITECTURE.md` | Tạo | Cài đặt, tính năng thật, dữ liệu, giới hạn, bản đồ đường dẫn và quy ước source. |
| `.gitignore` | Tạo | Loại credential/dữ liệu runtime, archive, log, virtualenv và output sinh tự động. |
| `tests/test_project_structure.py` | Tạo | 6 kiểm tra hồi quy cho import, launcher, đường dẫn và lưu trữ. |
| `AGENTS.md`, `CLAUDE.md` | Tạo | Quy tắc đọc thông tin bàn giao và ghi tài liệu sau mỗi lượt sửa. |
| `share_agent/` | Chuẩn hóa tên + tạo tài liệu | Thư mục rỗng ban đầu có tên `share_Agent`; đổi chữ hoa/thường, thêm README, TEMPLATE, CHANGELOG và bản ghi này. |

Giữ nguyên vị trí `venv/`, `venv_broken_1790218479/`, `.claude/`, `.codex-build/` và `output/`. Không cài thêm dependency hoặc sửa `requirements.txt`.

## Quyết định cần giữ khi tiếp tục

- Source đang dùng là `evolock/`; các bản trong `archive/` không phải điểm chạy.
- Dùng import dạng `evolock.services.timer`, tránh xung đột tên `timer` với `win32/timer.pyd` từng xuất hiện trong log cũ.
- Không đổi schema dữ liệu hay thuật toán chặn/AI trong đợt tổ chức này.
- Không di chuyển môi trường ảo đang dùng vì đường dẫn cài đặt có thể bị cố định.
- Đây là chia module theo trách nhiệm; UI vẫn là một file lớn và blocker/game hóa còn trực tiếp lưu một phần JSON. Chưa refactor thành các lớp repository độc lập.
- Quy tắc bàn giao là hướng dẫn trong file dự án, không phải dịch vụ tự gửi thông báo cho Claude. Agent cần đọc các file này khi làm việc.

## Kiểm tra

| Lệnh hoặc cách kiểm tra | Kết quả |
| --- | --- |
| `.\venv\Scripts\python.exe -B -m unittest discover -s tests -v` | 6/6 đạt trên Python 3.12.10. |
| So sánh SHA-256 JSON trong `data/` với `archive/before_restructure/` | Mọi file JSON được di chuyển khớp nguyên bản. Không đưa nội dung riêng tư vào báo cáo. |
| Tìm import nội bộ cũ và `Path(__file__)` trong package | Không còn import nội bộ dạng top-level cũ; việc tìm gốc dự án tập trung trong `paths.py`. |
| Parse AST Python, kiểm tra tài liệu Markdown và cấu hình mẫu | 24 file Python hợp lệ; 8 tài liệu không lỗi ký tự thay thế/code fence, 11 liên kết nội bộ tồn tại; JSON mẫu hợp lệ. |

Các kiểm tra dùng dữ liệu tạm; launcher GUI/watchdog được mock. Không khởi động phiên chặn thật hay gọi SMTP/AI để kiểm tra refactor.

## Giới hạn và việc còn lại

- Chưa chạy kiểm thử tương tác GUI, gửi Gmail, gọi Ollama/Anthropic hoặc thay đổi Windows startup. Không có xác nhận đầu-cuối cho các luồng này.
- Watchdog hiện nhận diện `main.py` theo đường dẫn, chưa nhận diện `python -m evolock`; dùng launcher `main.py` nếu bật watchdog.
- README ghi rõ các giới hạn sẵn có: Screen AI không tạo ngoại lệ cho app ngoài nhóm browser; browser không có tiêu đề có thể bị bỏ qua nếu Screen AI không dùng được; nhãn 20 giây trên UI khác cooldown 10 giây trong source.
- Không còn công việc bắt buộc trong phạm vi yêu cầu hiện tại. Các giới hạn trên là thông tin cho lần phát triển tiếp theo.

## Hướng dẫn tiếp tục / phục hồi

Đọc `AGENTS.md` và `share_agent/CHANGELOG.md` trước khi sửa. Cập nhật bản ghi riêng theo `share_agent/TEMPLATE.md` sau mỗi lượt có thay đổi.

Chạy app bằng `.\venv\Scripts\python.exe main.py` tại gốc dự án. Khi đổi máy, tạo môi trường mới theo README.

Nếu cần đối chiếu/phục hồi source trước refactor, dùng `archive/before_restructure/` và bảng ánh xạ trong `docs/ARCHITECTURE.md`. Chỉ phục hồi có chọn lọc sau khi sao lưu dữ liệu hiện tại; không ghi đè toàn bộ `data/` từ backup cũ vì có thể mất phiên học mới. Backup chứa dữ liệu riêng tư và đã được loại khỏi Git.
