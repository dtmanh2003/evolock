# Nhật ký thay đổi dùng chung

Bản ghi mới nhất đặt trên cùng. Các ngày dùng múi giờ người dùng (hiện tại: Asia/Tokyo).

| Ngày | Agent | Công việc | Bản ghi |
| --- | --- | --- | --- |
| 2026-11-19 | Claude | Core: thử thật bộ chặn (9/9), sửa torch hỏng để AI tiêu đề chạy lại, thêm mức "AI không chắc" + nhãn học/giải trí của phụ huynh, đổi sang mô hình đa ngôn ngữ (học đúng 11/16 → 15/16 trên bộ mẫu nhỏ); 171 test đạt | [Chi tiết](changes/2026-11-19-claude-core-ai-unsure.md) |
| 2026-11-19 | Claude | Ẩn ô Client ID/Secret khỏi người dùng thường, hỗ trợ Client đóng gói sẵn, nút đăng nhập Google ra ngoài; 159 test đạt | [Chi tiết](changes/2026-11-19-claude-hide-sender-setup.md) |
| 2026-11-19 | Claude | Gmail: nút đọc Client OAuth từ file JSON (không đưa secret qua chat); 154 test đạt, chưa gửi thật | [Chi tiết](changes/2026-11-19-claude-import-client-json.md) |
| 2026-11-19 | Claude | Tab 集中: thanh tiến độ phiên, tô sáng mức; test tích hợp chạy EvoLockApp thật; sửa bố cục cửa sổ 640px (vi/en), ô chọn tối màu, cache Coach theo ngôn ngữ; 150 test đạt | [Chi tiết](changes/2026-11-19-claude-focus-tab-polish.md) |
| 2026-11-19 | Claude | Đổi ngôn ngữ giao diện 日本語/Tiếng Việt/English (i18n, bảng dịch, test quét toàn source); 131 test đạt, chưa xem bố cục thực | [Chi tiết](changes/2026-11-19-claude-language-switch.md) |
| 2026-11-19 | Claude | Bảo vệ bằng mã Gmail thay mã cục bộ; thiết kế lại task/記録/AIコーチ có biểu đồ; làm sạch văn bản AI; khung i18n; 125 test đạt | [Chi tiết](changes/2026-11-19-claude-gmail-protection-and-ui.md) |
| 2026-11-19 | Claude | Gmail: gửi bằng đăng nhập Google (OAuth, không App Password), sửa SMTP/thông báo lỗi; 93 test đạt, chưa gửi thật | [Chi tiết](changes/2026-11-19-claude-gmail-oauth-sending.md) |
| 2026-11-16 | Codex | Validation thời lượng, consent màn hình, phục hồi điểm không trùng, hero gọn hơn; 72 test đạt | [Chi tiết](changes/2026-11-16-codex-session-experience.md) |
| 2026-11-16 | Codex | AI Coach single-flight, rollback lưu dữ liệu, validation và browser fallback; 68 test đạt | [Chi tiết](changes/2026-11-16-codex-reliability.md) |
| 2026-11-14 | Codex | Bỏ cấu hình kỹ thuật khỏi UI, tài liệu cho developer và việc còn lại | [Chi tiết](changes/2026-11-14-codex-hide-technical-settings.md) |
| 2026-11-13 | Codex | Đơn giản hóa phiên học: bảo vệ mã tùy chọn, mặc định tắt; 60/60 test đạt | [Chi tiết](changes/2026-11-13-codex-optional-session-code.md) |
| 2026-11-13 | Codex | Nâng cấp UI tập trung, tab cuộn, preset và cài đặt nâng cao thu gọn | [Chi tiết](changes/2026-11-13-codex-focus-interface.md) |
| 2026-11-13 | Codex | Bỏ memo mật khẩu và vùng quản lý process khỏi UI; 52/52 test đạt | [Chi tiết](changes/2026-11-13-codex-simplify-user-controls.md) |
| 2026-11-13 | Codex | Bảo vệ JSON, sửa timer/cài đặt AI và bộ lọc ngày; 52/52 kiểm tra đạt | [Chi tiết](changes/2026-11-13-codex-priority-storage-timer-settings.md) |
| 2026-11-13 | Claude | AI Coach: code tính sẵn findings, fallback sang tuần học gần nhất, khôi phục data activity/overrides đầy đủ; 43/43 test đạt | [Chi tiết](changes/2026-11-13-claude-ai-coach-findings.md) |
| 2026-11-13 | Codex | Rà soát từng nhóm chức năng, phát hiện thêm vấn đề storage/timer/cài đặt/AI | [Chi tiết](changes/2026-11-13-codex-component-review.md) |
| 2026-11-13 | Codex | Sửa 7 vấn đề đã rà soát; bổ sung khóa một phiên và kiểm tra hồi quy, 28/28 đạt | [Chi tiết](changes/2026-11-13-codex-fix-seven-audit-findings.md) |
| 2026-11-13 | Codex | Rà soát và tái hiện 7 lỗi; thêm file BAT mở EvoLock | [Chi tiết](changes/2026-11-13-codex-audit-and-launcher.md) |
| 2026-11-13 | Codex | Chia thư mục source, viết README và tạo quy tắc bàn giao Codex/Claude | [Chi tiết](changes/2026-11-13-codex-project-restructure.md) |

