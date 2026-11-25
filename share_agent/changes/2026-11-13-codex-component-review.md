# Rà soát từng nhóm chức năng — đợt 2

- Ngày: 2026-11-13 (Asia/Tokyo)
- Agent: Codex
- Trạng thái: Hoàn thành rà soát source và kiểm tra có kiểm soát; chưa kiểm thử tích hợp toàn bộ.

## Yêu cầu
Kiểm tra tiếp từng phần của dự án, tổng hợp nơi chưa ổn. Không sửa nghiệp vụ trong lượt này.

## Phát hiện

| Ưu tiên | Phần | Phát hiện và bằng chứng | Hướng xử lý |
| --- | --- | --- | --- |
| P1 | Config/storage | Config JSON hỏng bị bỏ qua, has_password() trả False; thao tác set tiếp theo ghi đè file hỏng bằng mặc định. Đã tái hiện bằng file tạm. Các manager JSON khác cũng bắt lỗi đọc rồi dùng dữ liệu rỗng; ghi trực tiếp chưa nguyên tử. | Báo lỗi đọc, giữ bản hỏng, không tự ghi đè; ghi file tạm rồi replace và backup. |
| P2 | Timer | Gọi start() hai lần tạo hai Thread; đã xác nhận bằng mock. stop/start dùng chung running nên worker cũ có thể hoạt động lại. UI thường tạo timer mới nên mức ảnh hưởng thực tế cần kiểm tra thêm luồng callback đã xếp hàng. | Event/generation riêng và start idempotent; bỏ callback của phiên cũ. |
| P2 | Lịch sử/nhật ký | last_n_days(7) dùng today - 7 và so sánh >= nên chứa 8 ngày lịch nếu tính cả hôm nay. Đã tái hiện 8 ngày trong HistoryManager; override/activity có cùng dạng lọc. | Quy định khoảng ngày thống nhất, tính từ today - (n-1), chặn ngày tương lai. |
| P2 | Lịch sử/EXP | Phiên qua nửa đêm ghi toàn bộ thời lượng vào ngày log; chưa chia theo ngày. Reset thống kê ngày đã sửa không giải quyết phân bổ thời lượng phiên này. | Chia khoảng phiên tại mốc nửa đêm, bảo toàn tổng phút và chính sách EXP. |
| P2 | Cài đặt Screen AI | _save_api_key() đặt screen_enabled=bool(key), nên xóa key sẽ tắt Screen AI dù Ollama còn được cấu hình. Xác nhận từ source. | Tính backend khả dụng thống nhất và tôn trọng lựa chọn bật/tắt của người dùng. |
| P2 | Cài đặt AI | Toggle Smart/Screen chỉ sửa thuộc tính runtime; khởi động lại mặc định Smart bật và Screen bật nếu có backend. | Lưu lựa chọn trong config và đồng bộ checkbox khi đổi backend. |
| P2 | AI Coach/UI | _run_analysis(auto=True) không khóa nút chạy, không có request ID; nhiều worker có thể trả kết quả khác thứ tự và kết quả cũ ghi đè mới. Worker cũng chưa có try/finally bao toàn bộ phần dựng context. Xác nhận đường đi source, chưa tái hiện cạnh tranh đầu-cuối. | Một request tại một thời điểm hoặc version kết quả; phục hồi nút khi lỗi. |
| P2 | Gmail/keyring | save_app_password/save_local_password không xử lý exception backend; khi keyring không có, hàm lưu âm thầm không làm gì. UI có thể không hoàn thành thao tác lưu hoặc không nói rõ thất bại. | Trả trạng thái lưu, bắt lỗi và thông báo; kiểm thử backend unavailable/locked. |
| P3 | Giao diện | Nhãn Screen AI ghi 20 giây trong khi cooldown thực tế 10 giây cộng thời gian xử lý. | Dùng chung hằng số để sinh nhãn. |

## Kiểm tra từng nhóm

- Launcher, import, đường dẫn, khóa một phiên, watchdog: suite hiện tại đạt; chưa chạy startup Registry thật.
- Blocker: các hồi quy đợt trước đạt; còn giới hạn process browser không tiêu đề khi Smart bật và Screen không dùng được. Chưa xác nhận độ chính xác model hay hành vi cửa sổ thực tế.
- Timer: tái hiện double-start; chưa chạy kiểm tra sleep/resume Windows.
- Tasks: round-trip đạt; lưu trữ vẫn phụ thuộc khóa phiên ở launcher, không có transaction riêng cho script ngoài.
- Game hóa: hồi quy chuyển ngày đạt; còn phân bổ phiên qua nửa đêm nêu trên.
- Config/history/activity/override/password logs: rà soát xử lý JSON và khoảng ngày; chưa sửa dữ liệu cũ.
- AI Coach: source đã thay đổi ngay trong lúc rà soát (_run_analysis chuyển sang select_window/compute_findings). Không ghi đè thay đổi đó. Kết quả kiểm tra helper _calc_stats cho một ngày học cho consistency=1.0, nhưng không kết luận đây là lỗi của pipeline mới khi chưa kiểm tra lại toàn bộ cửa sổ phân tích mới.
- Gmail/credential/startup: đọc source, chưa gửi thư, ghi credential hoặc sửa Registry thật.
- GUI/mascot/tray: kiểm tra source và mock; chưa kiểm tra trực quan DPI, khay hệ thống, dialog và đóng/mở cửa sổ.

## Thay đổi thực tế
Chỉ tạo bản ghi này và thêm liên kết vào share_agent/CHANGELOG.md. Không sửa source hoặc dữ liệu cá nhân.

## Kiểm tra đã chạy
- `.\venv\Scripts\python.exe -B -m unittest discover -s tests -q`: 28/28 đạt.
- Python qua stdin, dùng TemporaryDirectory và unittest.mock: config hỏng -> has_password False và bị ghi đè sau set; last_n_days(7) trả 8 ngày; timer.start gọi hai lần -> 2 worker.
- Chỉ đọc source cho các phát hiện còn lại; không coi đó là xác nhận đầu-cuối.

## Giới hạn và hướng tiếp tục
Ưu tiên khả năng phục hồi JSON, vòng đời timer và tính nhất quán cài đặt AI. Sau đó kiểm tra các luồng GUI/AI/Gmail bằng fixture và backend giả. Cần rà lại AI Coach sau khi thay đổi đang diễn ra ổn định. Báo cáo không xác nhận đã tìm hết lỗi và không chứng nhận mọi chức năng hoạt động thực tế.
