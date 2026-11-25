# Quy tắc làm việc trong dự án EvoLock

Áp dụng cho toàn bộ dự án và mọi agent sửa source hoặc tài liệu. Ưu tiên chỉ dẫn mới nhất của người dùng nếu có xung đột với quy tắc này.

## Trước khi làm việc

- Đọc `README.md`, `docs/ARCHITECTURE.md`, `share_agent/README.md` và các bản ghi mới nhất được liệt kê trong `share_agent/CHANGELOG.md` để nắm thay đổi từ agent khác.
- Source hiện hành là package `evolock/`. Không sửa nhầm source trong `archive/`, môi trường ảo hoặc file sinh tự động.
- Giữ dữ liệu cá nhân và các thay đổi đang có của người dùng. Không đưa giá trị mật khẩu, API key, email cá nhân hoặc nội dung nhật ký riêng tư vào tài liệu bàn giao.

## Quy tắc bàn giao bắt buộc sau khi làm việc

Sau mỗi lượt công việc có thay đổi file, **trước khi gửi câu trả lời cuối**, phải:

1. Tạo một bản ghi Markdown mới trong `share_agent/changes/`, tên `YYYY-MM-DD-<agent>-<mo-ta-ngan>.md`. Dùng ngày theo múi giờ người dùng; nếu trùng tên thì thêm hậu tố, không ghi đè bản ghi cũ.
2. Dựa trên `share_agent/TEMPLATE.md`, mô tả yêu cầu, thay đổi thực tế, file đã tạo/sửa/di chuyển, lý do quyết định, kiểm tra đã chạy và kết quả, giới hạn/chưa kiểm tra, việc còn lại và hướng dẫn tiếp tục khi cần.
3. Cập nhật `share_agent/CHANGELOG.md`, thêm liên kết bản ghi ở đầu danh sách. Ghi tên agent để Claude, Codex hoặc người đọc khác biết nguồn bàn giao.
4. Nếu đổi cấu trúc, lệnh chạy hoặc cấu hình, cập nhật cả README/tài liệu kiến trúc liên quan.
5. Trong câu trả lời cuối, dẫn link bản ghi bàn giao để người dùng tìm được.

Quy tắc áp dụng cả với sửa nhỏ, refactor và thay đổi tài liệu. Nếu công việc chưa xong hoặc bị chặn, ghi rõ trạng thái và phần còn lại; không ghi đã hoàn thành hay đã test nếu chưa thực hiện. Nếu không thể ghi file do quyền truy cập, báo rõ giới hạn đó cho người dùng.

Không cần tạo bản ghi mới cho lượt chỉ đọc, giải thích hoặc trả lời mà không sửa file, trừ khi người dùng yêu cầu. Không tạo thêm vòng bản ghi chỉ vì vừa ghi nhật ký cho chính lượt đó. Không tự gửi tài liệu cho dịch vụ ngoài: các agent chia sẻ qua thư mục trong dự án.

## Quy ước kỹ thuật

- Import nội bộ dùng `evolock.<layer>.<module>`; mọi đường dẫn runtime lấy từ `evolock.paths`.
- Giữ launcher gốc `main.py` và `watchdog.py` tương thích với shortcut hiện có.
- Kiểm tra phù hợp với thay đổi. Với import/đường dẫn/storage, chạy `python -B -m unittest discover -s tests -v` bằng Python của môi trường dự án.
- Không chạy phiên chặn ứng dụng, gửi email thật hoặc chỉnh Windows startup chỉ để xác minh refactor/import. Dùng mock và dữ liệu tạm cho các kiểm tra đó.
- Tránh thêm thông tin cá nhân vào source; `data/`, `archive/`, `logs/` và virtualenv không thuộc source để chia sẻ.
