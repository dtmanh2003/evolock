# Trải nghiệm phiên học, quyền màn hình và phục hồi điểm

- Ngày: 2026-11-16 (Asia/Tokyo)
- Agent: Codex
- Trạng thái: Hoàn thành phạm vi dưới đây.

## Yêu cầu
Người dùng đồng ý làm tiếp thứ tự: nhập thời lượng, quyền riêng tư AI, nhất quán lịch sử/điểm, tinh chỉnh giao diện.

## Thay đổi thực tế
- Chặn bắt đầu nếu học/nghỉ không phải số nguyên 1–1440; báo tại vùng nhập, không chuyển trạng thái hay tự dùng giá trị mặc định cho lần bắt đầu đó.
- Thêm mục quyền đọc màn hình với giải thích ảnh toàn màn hình và nơi xử lý. Mặc định tắt; cấu hình cũ cũng cần consent. Consent gắn với local/Anthropic nên đổi đích phải xác nhận lại. Không phục hồi các ô kỹ thuật model/API.
- Session mới có UUID và reward_pending. Stats ghi ID đã thưởng cùng điểm, history xác nhận sau cùng. Reconcile khi startup và trước phiên mới. Lỗi stats hoặc lỗi xác nhận history có thể thử lại sau restart, không cộng trùng. Dữ liệu legacy không bị thưởng lại.
- Thu gọn font đồng hồ, padding hero và nút bắt đầu. Chưa đổi thanh cuộn.

| File | Thao tác | Nội dung |
| --- | --- | --- |
| evolock/ui/app.py | Sửa | Validation, privacy UI/consent, reconcile, hero |
| evolock/storage/config.py | Sửa | Screen mặc định tắt, consent destination |
| evolock/storage/history.py | Sửa | Session ID/pending, settle_rewards |
| evolock/services/gamification.py | Sửa | Idempotent study rewards |
| evolock/storage/state.py | Sửa | Validate danh sách ID đã thưởng |
| tests/test_session_experience.py | Tạo | 4 kiểm tra hồi quy |
| tests/test_optional_protection.py | Sửa | Fixture thêm input/history cho luồng bắt đầu |
| tests/test_priority_fixes.py | Sửa | Fixture phản ánh consent mới |
| README.md, docs/ARCHITECTURE.md | Sửa | Hành vi mới và giới hạn |
| share_agent/CHANGELOG.md | Sửa | Link bàn giao |

## Kiểm tra
- `.\venv\Scripts\python.exe -B -m unittest discover -s tests -v`: 72/72 đạt.
- Tk smoke với toàn bộ storage path tạm, Blocker/tray/startup/keyring mock: dựng UI thành công, nhập abc rồi bắt đầu giữ idle và không gọi blocker.start.
- Không đọc/sửa data riêng, không gửi email/AI thật, không chặn process hay đổi startup thật.

## Giới hạn và việc còn lại
- GUI smoke không phải đánh giá trực quan đầy đủ; cần xem lại trên DPI/màn hình thực tế. Thanh cuộn chưa đổi.
- Không phải atomic transaction nhiều file. Khi lỗi lưu còn tồn tại, app báo lỗi; pending reward được thử lại ở lần mở/bắt đầu sau. Task completion + rewards chưa idempotent.
- Recovery qua ngày không cộng vào phút/check-in hôm nay, nhưng chưa tái dựng streak multiplier quá khứ. Chưa chia phiên qua nửa đêm.
- Danh sách ID đã thưởng tăng theo lịch sử; chưa dọn để tránh cộng trùng.
- Tắt screen không thu hồi ảnh đã gửi hoặc hủy worker đang chạy. Consent mô tả điều này; cần test tích hợp backend thật.
- Quên mã, dịch vụ Gmail chỉ nhập email, sleep/resume còn lại như audit. Chưa đổi fallback nội bộ getters; validation được đặt tại cửa vào bắt đầu phiên.

## Hướng dẫn tiếp tục / phục hồi
Mở lại ứng dụng để nhận code. Đọc HistoryManager.settle_rewards và test pending reward trước khi đổi schema. Không xóa rewarded_sessions hoặc tự bật reward_pending cho dữ liệu cũ. Giữ source và dữ liệu schema mới cùng nhau nếu phục hồi phiên bản; không restore toàn bộ data tùy tiện.
