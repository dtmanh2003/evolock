# Đổi ngôn ngữ giao diện (日本語 / Tiếng Việt / English)

- Ngày: 2026-11-19 (múi giờ người dùng)
- Agent: Claude
- Trạng thái: hoàn thành code và test. Bố cục tiếng Việt đã được xem bằng ảnh chụp các tab 集中, タスク, AIコーチ, 設定 (sau khi màn hình bật lại, xem `2026-11-19-claude-focus-tab-polish.md`); tiếng Anh chỉ được quét tự động, chưa xem bằng mắt; tab 記録 và các hộp thoại chưa xem ở tiếng Việt/Anh

## Yêu cầu

Người dùng muốn thêm tính năng đổi ngôn ngữ cho app (hướng sản phẩm để bán).

## Thay đổi thực tế

- `evolock/i18n.py`: `tr(text)`, `translate(code, text)`, `set_language`, `LANGUAGES`. Văn bản gốc trong source là tiếng Nhật; thiếu bản dịch thì trả lại nguyên câu gốc (không bao giờ làm app lỗi). Chuỗi có tham số dùng chỉ số `{0}`.
- `evolock/locales/vi.py`, `en.py`: khoảng 420 mục mỗi ngôn ngữ (giao diện, thông báo lỗi Gmail/OAuth, tên cấp bậc, thành tích, lời mascot, lý do dừng sớm, loại nhiệm vụ, báo cáo và phát hiện của AI Coach).
- Bọc `tr()` bằng script AST (chạy một lần, không còn nằm trong repo) cho `ui/app.py`, `integrations/session_code.py`, `integrations/gmail_oauth.py`, `services/ai_coach.py`, `ui/charts.py`. Script chủ động **không bọc** chuỗi dùng để so sánh, khóa dict, đối số `.replace/.startswith`, hằng số cấp module và các hàm dựng prompt; những chỗ đó được xử lý tay:
  - Dữ liệu lưu giữ nguyên tiếng Nhật, chỉ dịch khi hiển thị: loại nhiệm vụ (`OptionMenu` hiển thị bản dịch, biến thật vẫn giữ tiếng Nhật), lý do dừng sớm (`ask_override` ánh xạ ngược về tiếng Nhật trước khi ghi `override_log`), cấp bậc/thành tích (`tr(...)` lúc vẽ), lời mascot, nhãn khung giờ (`_time_bucket` trả khóa tiếng Nhật; `tr(b)` khi ghép vào câu và khi vẽ biểu đồ), ghi chú " (追加済み)" dùng chung một biến cho cả hiển thị và tách lại.
  - Các f-string chứa tiếng Nhật trong biểu thức được viết lại thành `tr("...{0}").format(...)`.
- `app.py`: `i18n.set_language(cfg.get("language"))` ngay sau khi nạp `Config`; mục "言語 / Language / Ngôn ngữ" ở đầu Cài đặt (combobox, tên mỗi ngôn ngữ viết bằng chính ngôn ngữ đó). Đổi xong hiện thông báo bằng ngôn ngữ mới, có hiệu lực sau khi khởi động lại.
- `config.py`: khóa `language` (mặc định `ja`).
- `ai_coach.analyze(..., language=)`: với Ollama/Anthropic, prompt vẫn bằng tiếng Nhật và thêm chỉ thị "trả lời bằng tiếng Việt/Anh, giữ nguyên số liệu".

| File | Thao tác |
| --- | --- |
| `evolock/i18n.py`, `evolock/locales/{__init__,vi,en}.py` | Tạo / hoàn thiện |
| `evolock/ui/app.py`, `integrations/session_code.py`, `integrations/gmail_oauth.py`, `services/ai_coach.py`, `ui/charts.py`, `storage/config.py` | Sửa (bọc `tr`, chọn ngôn ngữ) |
| `tests/test_i18n.py` | 10 test: quét toàn bộ source, mọi chuỗi `tr()`/`translate()` và các hằng số hiển thị phải có bản dịch ở cả hai ngôn ngữ; placeholder khớp; không có bản dịch thừa; chuyển ngôn ngữ và quay lại |
| `README.md`, `docs/ARCHITECTURE.md` | Mục "Ngôn ngữ giao diện"; ghi chú cập nhật ở mục bảo vệ phiên học |

## Kiểm tra

| Lệnh hoặc cách kiểm tra | Kết quả |
| --- | --- |
| `.\venv\Scripts\python.exe -B -m unittest discover -s tests` | 131/131 đạt (bản gốc tiếng Nhật không đổi hành vi vì `tr` trả nguyên câu) |
| Dựng thật 4 tab ở tiếng Việt và tiếng Anh với dữ liệu thật, quét mọi widget tìm chữ tiếng Nhật còn sót và phần tử tràn khung | Không còn chữ Nhật của app (chỉ còn tiêu đề chọn ngôn ngữ cố ý, dấu "・" và nhận xét AI đã lưu từ trước); không có phần tử nào tràn khung ngoài thanh cuộn |
| Xem bằng mắt ở tiếng Việt/Anh | **Chưa làm được** (ảnh chụp màn hình ra màu đen vì màn hình đang tắt/khóa) |

## Giới hạn và việc còn lại

- Chưa nhìn bố cục thực ở tiếng Việt/Anh: chữ Việt dài hơn chữ Nhật nên có thể có nút/nhãn bị chật, đặc biệt ở tab `集中` (chưa dựng thử) và các hộp thoại. Việc đầu tiên nên làm: mở app ở `language=vi` và `en`, chụp từng tab và hộp thoại.
- Bản dịch do Claude viết, chưa có người bản ngữ rà soát.
- `blocker.py` chưa dịch (lý do được lưu vào `activity_log`); nội dung người dùng nhập không dịch; nhận xét AI đã lưu giữ ngôn ngữ cũ tới lần phân tích kế tiếp.
- Đổi ngôn ngữ cần khởi động lại app.
- Khi thêm chữ mới vào giao diện: bọc `tr()` và thêm vào cả `vi.py` và `en.py`; `tests/test_i18n.py` sẽ báo nếu quên.

## Hướng dẫn tiếp tục / phục hồi

- Điểm vào: `evolock/i18n.py`, `evolock/locales/`, `EvoLockApp._change_language`.
- Bản sao các file trước khi bọc `tr()` (chỉ trong thư mục tạm của phiên Claude, có thể mất): `scratchpad/pre_i18n/`.
- Muốn thêm ngôn ngữ: xem README mục "Ngôn ngữ giao diện".
