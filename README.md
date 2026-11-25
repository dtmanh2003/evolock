# EvoLock

Ứng dụng desktop giúp duy trì nhịp học tập bằng cách chặn ứng dụng gây xao nhãng, mở khóa theo thời gian hoặc nhiệm vụ hoàn thành, và phân tích thói quen bằng AI Coach.

EvoLock được viết bằng **Python + Tkinter**, dành cho **Windows**. Giao diện và nội dung AI Coach hiện chủ yếu bằng tiếng Nhật. Dữ liệu được lưu bằng JSON trên máy, không cần máy chủ cơ sở dữ liệu.

## Bắt đầu nhanh

Trên Windows, nhấp đúp `Mo_EvoLock.bat` để mở ứng dụng. File tự tìm Python trong `venv/`, rồi `.venv/`, và chạy từ đúng thư mục dự án. Giữ cửa sổ console trong lúc dùng; nếu khởi động lỗi, cửa sổ giữ lại thông báo để kiểm tra.

Mỗi thư mục dữ liệu chỉ cho phép một phiên EvoLock chạy để tránh ghi đè dữ liệu. Nếu mở thêm, ứng dụng sẽ báo phiên đã chạy; kiểm tra cửa sổ hoặc khay hệ thống. Sau khi cập nhật source, thoát phiên cũ và mở lại để dùng bản mới.

Mở PowerShell tại thư mục dự án. Nếu đang dùng môi trường `venv/` có sẵn trên máy này:

```powershell
.\venv\Scripts\python.exe main.py
```

Khi chuyển sang máy khác hoặc cần cài mới, tạo môi trường riêng. Môi trường hiện có của dự án dùng Python 3.12; mã nguồn sử dụng cú pháp Python 3.10 trở lên.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Không cần kích hoạt môi trường để chạy các lệnh trên. Python cần có Tkinter. Ứng dụng dùng `winreg` và Windows API nên chưa hỗ trợ chạy trực tiếp trên macOS/Linux.

Với một bản source mới chưa có dữ liệu cá nhân, có thể khởi tạo danh sách chặn mẫu:

```powershell
if (-not (Test-Path .\data\blocked.json)) {
    Copy-Item .\data\blocked.example.json .\data\blocked.json
}
```

Nếu không có `blocked.json`, danh sách chặn ban đầu rỗng; cấu hình mẫu ở trên dành cho người thiết lập ứng dụng. Các file dữ liệu khác được tạo khi chức năng tương ứng lưu dữ liệu.

Một cách khởi động khác từ thư mục gốc:

```powershell
.\.venv\Scripts\python.exe -m evolock
```

## Chức năng chính

| Chức năng | Hành vi hiện tại |
| --- | --- |
| Phiên học và giờ nghỉ/chơi | Mặc định 30 phút học và 30 phút mở khóa; điều chỉnh trên tab Khóa. Hết giờ mở khóa, blocker bật lại. |
| Chặn ứng dụng | Quét process khoảng mỗi 3 giây, kết thúc process có tên trong danh sách chặn. Dùng danh sách đã cấu hình trong `data/blocked.json`; không hiển thị process hoặc bộ chọn ứng dụng trên giao diện người dùng. |
| Smart Block | Phân loại tiêu đề cửa sổ trình duyệt bằng `all-MiniLM-L6-v2`, kết hợp ngoại lệ tra cứu và whitelist kênh YouTube. |
| Screen AI | Chụp màn hình để lấy tín hiệu học/giải trí qua Ollama hoặc Anthropic; dùng cùng logic chặn trình duyệt. |
| Nhiệm vụ | Thêm, hoàn thành, xóa và gợi ý tên theo nhóm. Xác nhận hoàn thành một nhiệm vụ sẽ mở khóa và bắt đầu giờ chơi. |
| Game hóa | EXP, cấp độ, streak, thưởng hoạt động đầu ngày, hệ số streak và 10 thành tích. |
| AI Coach | Phân tích lịch sử học/chơi, nhiệm vụ, nhật ký xao nhãng và các lần dừng học; lưu kết quả gần nhất để xem lại. |
| Bảo vệ bằng Gmail | Nhập một Gmail nhận mã; mỗi lần bấm `学習開始` app gửi mã 6 số tới đó, muốn dừng sớm hoặc đổi cài đặt phải nhập mã. Mặc định tắt cho tới khi lưu Gmail và có nguồn gửi. Mã cục bộ tự đặt (cách cũ) vẫn chạy nếu đã bật từ trước nhưng không còn hiện trong Cài đặt. |
| Tích hợp Windows | Khay hệ thống, tùy chọn khởi động cùng Windows và watchdog chạy riêng. |
| Mascot | Nhân vật hoạt hình từ các frame PNG trong `assets/mascot_frames/`. |

**Lưu ý khi dùng:** blocker gọi `proc.kill()`, có thể làm mất nội dung chưa lưu trong ứng dụng bị chặn. Đây là công cụ hỗ trợ tự kỷ luật; người có quyền sửa source/dữ liệu hoặc dừng process vẫn có thể thay đổi hành vi của nó.

## Cách sử dụng

| Tab | Nội dung |
| --- | --- |
| `集中` — Tập trung | Đặt thời gian, bắt đầu/dừng học, xem bộ đếm và nhật ký. |
| `タスク` — Nhiệm vụ | Nhóm học tập, công việc, đọc sách, vận động và khác; quản lý nhiệm vụ và gợi ý tên. |
| `記録` — Thống kê | Thẻ cấp độ/EXP, 4 ô số liệu, biểu đồ học 7 ngày gần nhất và lưới thành tích. |
| `AIコーチ` — AI Coach | Bảng điều khiển: ô số liệu, lời nhận xét của coach, biểu đồ (học theo ngày, theo giờ, giờ mất tập trung, app hay mở) và các phát hiện kèm gợi ý. Biểu đồ tính bằng code nên hiện ngay cả khi chưa gọi AI; `今すぐ分析` chỉ tạo lời nhận xét. |
| `設定` — Cài đặt | Gmail nhận mã, nguồn gửi (mục thu gọn), khởi động cùng Windows và quyền đọc màn hình. Mục tiêu học mỗi ngày không còn chỉnh ở đây (mặc định nội bộ 120 phút; việc gợi ý mức học là của AI Coach). |

1. Lưu công việc trong các ứng dụng có thể bị chặn; danh sách do cấu hình nội bộ quản lý.
2. Đặt thời gian học và thời gian chơi.
3. Bấm `学習開始` để học. Nếu đã bật bảo vệ bằng Gmail, app gửi mã tới Gmail đã lưu trước khi bắt đầu; nếu gửi lỗi có thể thử lại, hủy hoặc `保護なしで開始` (ghi vào log; ai cũng chọn được nên chỉ nên dùng khi thật sự cần).
4. Hết giờ học hoặc hoàn thành nhiệm vụ, ứng dụng mở khóa và tự chạy AI Coach.
5. Hết giờ chơi, ứng dụng chặn lại và chờ bạn bắt đầu phiên học tiếp theo.

Khi đang học và có mật khẩu/mã phiên, nút đóng cửa sổ chỉ thu nhỏ. Trong các trường hợp khác, nếu có tray thì cửa sổ ẩn vào khay hệ thống. Chọn `終了` ở tray để thoát; ứng dụng kiểm tra mã/mật khẩu theo trạng thái hiện tại.

Khi đang học hoặc đang khóa, xóa ứng dụng khỏi danh sách chặn cần xác thực theo cơ chế mã phiên/mật khẩu hiện có. Dùng mã phiên để quản lý danh sách không tiêu thụ mã đó và không ghi nhầm thành lần dừng học.

## AI và Gmail

### Smart Block và Screen AI

- Smart Block tải model `all-MiniLM-L6-v2` trong luồng nền; lần đầu có thể cần mạng để tải model. Phần này dùng `sentence-transformers` và `scikit-learn`.
- Whitelist YouTube dựa vào tên kênh tách từ **tiêu đề cửa sổ**, không kiểm tra trực tiếp URL hay nội dung từng tab.
- Screen AI gọi Ollama tại `http://localhost:11434/api/generate` nếu có `ollama_model`; nếu không có model thì dùng `anthropic_api_key`.
- Model Ollama dành cho Screen AI phải nhận được ảnh. AI Coach có thể dùng model văn bản riêng trong `coach_ollama_model`; nếu để trống sẽ dùng chung `ollama_model`.
- Khoảng chờ giữa các lần phân tích màn hình là 10 giây sau khi lần gọi trước hoàn tất, cộng thời gian xử lý. Nhãn giao diện hiển thị khoảng 10 giây.
- Khi Screen AI lỗi liên tiếp 3 lần, blocker không còn dùng tín hiệu đó để quyết định và xét theo thông tin tiêu đề nếu có.
- Với trình duyệt có tiêu đề, ngoại lệ tra cứu/whitelist được ưu tiên. Ngoài các ngoại lệ, tín hiệu giải trí từ một trong hai bộ phân loại được tích lũy trước khi chặn.

Khi Smart Block tắt và Screen AI tắt/không dùng được, danh sách chặn được áp dụng trực tiếp cho cả trình duyệt. Khi Screen AI còn hoạt động, trình duyệt vẫn có thể được cho phép theo kết quả phân loại.

**Giới hạn hiện tại:** Screen AI không tạo ngoại lệ cho ứng dụng ngoài nhóm trình duyệt; các ứng dụng đó vẫn bị kết thúc nếu nằm trong danh sách chặn. Trong chế độ Smart Block, process trình duyệt không có tiêu đề vẫn được bỏ qua nếu Screen AI không dùng được, để tránh chặn nhầm process phụ.

### AI Coach

AI Coach chọn backend theo cấu hình:

1. Có model Ollama: gọi `http://localhost:11434/api/chat`.
2. Không có model Ollama nhưng có API key: gọi Anthropic.
3. Không cấu hình backend hoặc backend được chọn gặp lỗi: phân tích offline theo quy tắc.

Nếu đã chọn Ollama mà gọi lỗi, mã hiện tại chuyển thẳng sang offline, không thử tiếp Anthropic. Model Anthropic được ghi trong source hiện là `claude-haiku-4-5-20251001` cho cả Coach và Screen AI.

**Cách Coach tạo nội dung (`evolock/services/ai_coach.py`):**

- `select_window` chọn 7 ngày gần nhất. Nếu 7 ngày đó không có phiên nào, Coach lùi về tuần học gần nhất có dữ liệu và ghi rõ "lần học cuối cách đây N ngày" thay vì báo "không có dữ liệu".
- `compute_findings` do code tính sẵn các phát hiện `{fact, hint}`: so với tuần trước, khung giờ học tập trung, số ngày đạt mục tiêu, số lần mất tập trung, ứng dụng gây xao nhãng nhiều nhất, số lần dừng học sớm và lý do phổ biến. Log xao nhãng ghi mỗi lần quét 3 giây, nên `_episodes` gộp các sự kiện liên tiếp cùng ứng dụng thành một lần mất tập trung (470 sự kiện thô ≈ 12 lần).
- Model (Ollama/Anthropic) chỉ diễn đạt lại các phát hiện này (`COACH_SYSTEM_PROMPT` cấm suy đoán nguyên nhân hoặc tự tính lại số). Báo cáo offline dùng cùng danh sách phát hiện nên số liệu giống nhau ở mọi backend.

Để dùng Ollama, chạy dịch vụ Ollama và nhập tên model đã có trên máy trong `設定`. Có thể dùng `ollama serve` khi dịch vụ chưa chạy. Không cần cấu hình AI bên ngoài để sử dụng phân tích offline.

### Gmail và mở khóa

**Luồng:** `設定` có một ô Gmail nhận mã. Lưu địa chỉ xong, nếu nguồn gửi đã sẵn sàng thì bảo vệ tự bật và app gửi thử một mã. Mỗi lần học app gửi mã mới; dừng sớm/thoát app cần mã đó kèm lý do (ghi vào nhật ký dừng sớm). Các việc quản lý khi không học (đổi Gmail nhận mã, tắt bảo vệ, sửa danh sách chặn) cần một mã mới gửi tới Gmail **hiện tại**, nên người không đọc được hộp thư không đổi được địa chỉ sang của mình. Đang trong phiên học thì không đổi/tắt bảo vệ được. Mã không được hiện trên máy: hộp thoại chỉ ghi địa chỉ đã che (`pa****@gmail.com`).

**Nguồn gửi:** thư được gửi từ tài khoản Google đã đăng nhập ở mục "送信元の設定" tới Gmail nhận mã (có thể là cùng một tài khoản). Có hai cách gửi, cấu hình trong mục thu gọn của `設定`; mọi bí mật nằm trong Windows Credential Manager (service `EvoLock`), không nằm trong `config.json`:

1. **Đăng nhập Google (OAuth, khuyến nghị, không cần App Password)** — `evolock/integrations/gmail_oauth.py`. Cần tạo một lần **OAuth Client ID loại "Desktop app"** trong Google Cloud Console, bật Gmail API, rồi nhập Client ID/Secret vào `設定`, bấm `保存` và `Googleでログイン`. Trình duyệt mở trang đồng ý của Google; ứng dụng chỉ nhận refresh token (scope `gmail.send`) và gửi qua Gmail API bằng HTTPS, không đi qua SMTP. Lưu ý: nếu app Google ở trạng thái "Testing" thì token hết hạn sau 7 ngày; chuyển sang "In production" để không hết hạn (app chưa xác minh chỉ hiện cảnh báo).
2. **App Password qua SMTP** (cách cũ, dự phòng) — STARTTLS cổng 587, rồi SSL cổng 465 nếu không kết nối được. Khi đã bắt đầu đăng nhập mà thất bại thì dừng, không thử lại ở cổng khác để tránh thêm lần đăng nhập sai. Khoảng trắng trong App Password được bỏ khi lưu và khi gửi.

Khi đã đăng nhập Google, `send_code_email` dùng OAuth; nếu chưa thì dùng App Password. Lỗi được dịch thành thông báo tiếng Nhật rõ nghĩa (sai mật khẩu, Google ngắt kết nối, mất mạng, chưa bật Gmail API...). Luồng bắt đầu học hiện không tự gửi Gmail; nút `テスト送信` là nơi kiểm tra.

Mật khẩu chính, mã khẩn cấp và mã phiên được băm PBKDF2-HMAC-SHA256 với salt, 100.000 vòng. Mật khẩu local mới tạo còn được lưu qua `keyring` để xem lại bằng nút `確認`; mã khẩn cấp cần được ghi lại khi hiển thị.

## Ngôn ngữ giao diện

`設定` → mục "言語 / Language / Ngôn ngữ" chọn **日本語** (mặc định), **Tiếng Việt** hoặc **English**. Lựa chọn lưu trong `config.json` (khóa `language`) và có hiệu lực sau khi khởi động lại app (widget Tk được dựng một lần lúc khởi động).

- Mã nguồn dùng tiếng Nhật làm văn bản gốc: `tr("日本語")` trong `evolock/i18n.py` trả về bản dịch của ngôn ngữ đang chọn, hoặc chính câu gốc nếu thiếu bản dịch (không bao giờ làm app lỗi). Chuỗi có tham số dùng chỉ số: `tr("学習 {0}分").format(n)`.
- Bảng dịch: `evolock/locales/vi.py`, `en.py` (`MESSAGES = {câu tiếng Nhật: bản dịch}`). **Thêm ngôn ngữ mới:** tạo `locales/<mã>.py`, thêm vào `LANGUAGES` và `_catalog()` trong `i18n.py`.
- `tests/test_i18n.py` quét toàn bộ source: mọi chuỗi trong `tr()` phải có bản dịch ở mọi ngôn ngữ, placeholder `{n}` phải khớp, và bản dịch không dùng tới sẽ bị báo. Khi thêm chữ mới vào giao diện hãy bọc `tr()` rồi thêm vào cả `vi.py` và `en.py`.
- Dữ liệu lưu giữ nguyên tiếng Nhật (loại nhiệm vụ, lý do dừng sớm, tên cấp bậc/thành tích) và chỉ được dịch khi hiển thị, nên đổi ngôn ngữ không làm hỏng dữ liệu hay phép so sánh.
- AI Coach: các phát hiện, báo cáo ngoại tuyến và khung giờ được dịch theo ngôn ngữ; với Ollama/Anthropic, prompt vẫn bằng tiếng Nhật kèm chỉ thị "trả lời bằng tiếng Việt/Anh". Kết quả phân tích đã lưu trước khi đổi ngôn ngữ vẫn giữ ngôn ngữ cũ cho đến lần phân tích tiếp theo.
- Chưa dịch: các chuỗi nội bộ của `blocker.py` (lý do ghi vào nhật ký hoạt động, vì chúng được lưu vào dữ liệu), nội dung do người dùng nhập (tên nhiệm vụ, tên kênh), và nhận xét AI đã lưu từ trước. Tab `集中` đã bọc `tr()` và nằm trong phạm vi test nhưng chưa được dựng thử để kiểm tra bố cục ở tiếng Việt/Anh (chữ Việt dài hơn chữ Nhật).

## Cấu trúc thư mục

```text
evolock/
├── main.py                    # Điểm khởi động tương thích lệnh cũ
├── watchdog.py                # Điểm khởi động watchdog
├── requirements.txt
├── README.md
├── AGENTS.md                  # Quy tắc làm việc và bàn giao cho agent
├── CLAUDE.md                  # Hướng dẫn để Claude đọc cùng quy tắc
├── evolock/                   # Package source đang dùng
│   ├── __main__.py            # python -m evolock
│   ├── paths.py               # Đường dẫn dữ liệu, asset, launcher
│   ├── ui/app.py              # Tkinter và điều phối trạng thái
│   ├── services/              # Blocker, AI Coach, timer, game hóa
│   ├── storage/               # Config, nhiệm vụ, lịch sử, nhật ký JSON
│   └── integrations/          # Gmail/keyring, Registry, watchdog
├── data/                      # Dữ liệu người dùng; không đưa lên Git
│   └── blocked.example.json   # Danh sách chặn mẫu, có thể chia sẻ
├── assets/
│   ├── mascot_frames/         # Frame PNG dùng khi chạy
│   └── source_media/          # GIF/MP4 nguồn
├── tests/                     # Kiểm tra import, launcher, đọc/ghi dữ liệu
├── docs/
│   ├── ARCHITECTURE.md        # Bản đồ source và quy ước mở rộng
│   └── ABOUT.legacy.txt       # Tài liệu cũ để tham khảo
├── share_agent/              # Nhật ký thay đổi dùng chung Codex/Claude
├── archive/                   # Backup, bản sao đồng bộ và bytecode cũ
├── logs/                      # Log khởi động cũ
├── output/presentations/      # EvoLock_Product_Roadmap.pptx
├── venv/                      # Môi trường Python đang có trên máy
└── venv_broken_1790218479/     # Môi trường cũ; không dùng để khởi động
```

Các thư mục công cụ ẩn như `.claude/`, `.codex-build/` được giữ riêng. Chi tiết module và ánh xạ đường dẫn cũ → mới có trong [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Độ bền dữ liệu và cài đặt

- JSON được ghi vào file tạm cùng thư mục, flush/fsync rồi thay file đích; bản hợp lệ trước lần ghi được giữ trong `<tên-file>.json.bak`.
- Nếu JSON không đọc được hoặc không phải object, ứng dụng báo lỗi và giữ file gốc; không tự reset dữ liệu hay tự phục hồi backup. Thoát app, giữ bản hỏng rồi đối chiếu `.bak` trước khi phục hồi có chọn lọc.
- Backup có thể chứa cùng thông tin riêng tư như dữ liệu gốc; giữ trong `data/`. Ghi nguyên tử không phải transaction giữa nhiều file và không thay thế backup ngoài máy.
- Lựa chọn Smart Block/Screen AI được lưu qua lần mở app. Screen AI chỉ hoạt động khi người dùng bật và có ít nhất một backend. Đổi model/API key không tự bật lại lựa chọn đã tắt.
- Timer chỉ có một lần chạy đang hoạt động; dừng/reset làm mất hiệu lực cả callback cũ đã xếp hàng cho giao diện.
- Bộ lọc nhật ký N ngày lấy hôm nay và N−1 ngày trước, loại ngày tương lai; N không dương trả danh sách rỗng.

## Dữ liệu và cấu hình

Tất cả đường dẫn runtime được xác định trong `evolock/paths.py` theo vị trí dự án, không phụ thuộc thư mục PowerShell hiện tại.

| File trong `data/` | Vai trò |
| --- | --- |
| `config.json` | Cấu hình, hash/salt, địa chỉ Gmail, API key, ghi chú, model AI, kết quả Coach và gợi ý tên nhiệm vụ. |
| `blocked.json` | Danh sách tên process, dạng `{"apps": ["steam.exe"]}`. |
| `whitelist.json` | Danh sách kênh, dạng `{"channels": ["Khan Academy"]}`. |
| `tasks.json` | Nhiệm vụ và trạng thái hoàn thành. |
| `stats.json` | EXP, level, streak, số phút học và thành tích. |
| `history.json` | Phiên học/chơi; phiên dưới 1 phút không được ghi. |
| `pw_log.json` | Tối đa 300 sự kiện dùng mật khẩu/mã khẩn cấp. |
| `activity_log.json` | Tối đa 500 sự kiện cảnh báo/chặn. |
| `overrides.json` | Tối đa 300 lần dừng bằng mã phiên, lý do và thời gian dự kiến/thực tế. |

`anthropic_api_key` và `password_note` được lưu dạng văn bản trong JSON. Dữ liệu lịch sử và nhật ký cũng không mã hóa. Không chia sẻ nguyên `data/`, `archive/` hoặc bản sao `config*-WIN-*.json`. `.gitignore` đã loại các thư mục dữ liệu cá nhân, môi trường ảo và log.

Khi dùng Anthropic cho Screen AI, ảnh chụp màn hình được gửi tới dịch vụ đó; với AI Coach, dữ liệu tổng hợp được gửi tới backend đã chọn. Source xử lý ảnh trong bộ nhớ, không chủ động ghi ảnh chụp ra file. Backend Ollama dùng địa chỉ localhost trong source.

Để sao lưu, thoát ứng dụng rồi sao chép `data/`. Gmail App Password và mật khẩu local lưu trong Credential Manager cần được thiết lập lại khi chuyển máy; sao chép JSON không mang theo các credential này.

## Quy tắc EXP

| Hoạt động | EXP |
| --- | --- |
| Hoàn thành nhiệm vụ | Cơ bản +50 |
| Học | Cơ bản +20 cho mỗi 10 phút trọn vẹn trong phiên được ghi |
| Hoạt động được ghi nhận đầu tiên trong ngày | +10 |
| Dùng mã khẩn cấp | −100, có thể giảm level; tối thiểu level 1 và EXP 0 |

EXP nhiệm vụ và học được nhân theo streak: từ 7 ngày ×1,25; từ 14 ngày ×1,5; từ 30 ngày ×2. Mỗi cấp cần `level × 100` EXP để lên cấp tiếp theo.

## Phát triển và kiểm tra

```powershell
.\venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

Nếu cài mới bằng `.venv`, thay `venv` bằng `.venv`. Bộ kiểm tra dùng thư mục tạm để đọc/ghi, mock GUI/process/AI, kiểm tra import, trạng thái chặn, xác thực, lịch sử giờ nghỉ, chuyển ngày, nhận diện watchdog và khóa giữa các process Python riêng. Không đóng ứng dụng thật hay gửi email. Các kiểm tra này không thay thế kiểm thử trực tiếp giao diện, AI, Gmail và Windows startup.

Đọc [AGENTS.md](AGENTS.md) trước khi sửa. Sau mỗi lượt sửa, ghi bàn giao vào [share_agent/](share_agent/README.md) và cập nhật [CHANGELOG](share_agent/CHANGELOG.md) để agent khác tiếp tục được.

## Xử lý sự cố

| Hiện tượng | Cách kiểm tra |
| --- | --- |
| `No pyvenv.cfg file` | Log cũ đã gặp lỗi môi trường. Tạo `.venv` mới theo phần cài đặt; không dùng `venv_broken_*`. |
| `cannot import name 'CountdownTimer' from 'timer'` | Log cũ cho thấy xung đột với `win32/timer.pyd`. Source mới dùng `evolock.services.timer`; chạy launcher gốc, không chạy bản trong `archive/`. |
| Thiếu thư viện | Dùng đúng `python.exe` của môi trường để chạy `-m pip install -r requirements.txt`. |
| Không chặn được ứng dụng | Kiểm tra tên process thực tế, danh sách chặn, ngoại lệ browser và quyền truy cập process. Lỗi `AccessDenied` được bỏ qua trong blocker. |
| YouTube được phân loại sai | Whitelist phụ thuộc định dạng tiêu đề; model AI có thể phân loại sai. Kiểm tra nhật ký và cấu hình lại danh sách. |
| Ollama không phản hồi | Kiểm tra dịch vụ tại localhost:11434 và tên model. Screen AI cần model nhận ảnh; Coach có thể dùng model riêng. |
| Gmail không gửi được | Kiểm tra cấu hình App Password/keyring, mạng và nút gửi thử. Dùng lựa chọn local hoặc hủy khi ứng dụng báo lỗi. |
| Ứng dụng tự mở lại sau khi thoát | Có thể watchdog đang chạy. Watchdog kiểm tra mỗi 15 giây và mở lại `main.py`. |

Tùy chọn startup trong ứng dụng chỉ đăng ký `main.py` qua Registry của người dùng hiện tại. Watchdog là tiến trình riêng, chỉ chạy khi bạn chủ động khởi động `python watchdog.py` hoặc tạo shortcut startup cho nó.

Watchdog kiểm tra khóa phiên đang chạy, đồng thời nhận diện `main.py` và `python -m evolock` trong dự án, kể cả cờ Python như `-B`. Các launcher dùng chung khóa `data/.instance.lock`; không xóa file khóa khi ứng dụng đang chạy. Windows tự giải phóng khóa khi process kết thúc.

Thư mục hiện chưa có file `LICENSE`. `docs/ABOUT.legacy.txt` và slide roadmap là tài liệu tham khảo; một số mô tả có thể khác hành vi source hiện tại.

Giao diện đã bỏ ô ghi chú mật khẩu và danh sách/chọn process. Mật khẩu dự phòng vẫn có các nút tạo, xem và xóa. Dữ liệu ghi chú cũ được giữ nguyên để không tự xóa dữ liệu người dùng.

## Giao diện tập trung

Màn hình chính làm nổi bật đồng hồ và nút bắt đầu, có mức học/nghỉ chọn nhanh 25/5, 50/10 và 90/15 phút. Lịch sử và thông tin vận hành mở khi cần. Cửa sổ mặc định 640×820, thay đổi kích thước được; tất cả tab có thanh cuộn. Trong Cài đặt, phần kết nối AI/whitelist/watchdog nằm trong mục nâng cao; mục tiêu ngày vẫn nằm ngoài mục nâng cao. Giao diện tiếp tục dùng tiếng Nhật và giữ nguyên luồng xác thực hiện tại.

## Luồng bảo vệ phiên học hiện tại

> **Cập nhật 2026-11-19:** ô bật/đổi mã bảo vệ cục bộ đã được gỡ khỏi Cài đặt, thay bằng bảo vệ bằng mã gửi tới Gmail (xem mục "Gmail và mở khóa"). Các đoạn dưới đây mô tả cơ chế mã cục bộ; cơ chế đó vẫn chạy nếu cấu hình cũ đã bật `protection_enabled`, nhưng không còn cách đổi/tắt trên giao diện.

Mặc định `protection_enabled=false`, kể cả cấu hình cũ chưa có khóa này. Mật khẩu và credential cũ vẫn được giữ, nhưng không tự bắt buộc cho phiên mới. Học bình thường bắt đầu ngay; dừng sớm hoặc thoát giữa phiên có hai lựa chọn “Tiếp tục học” và “Kết thúc sớm”. Lịch sử vẫn theo quy tắc hiện có (phiên dưới một phút chưa được ghi).

Bật “早めに終了するときにコードを求める” trong Cài đặt để tự đặt mã 6 chữ số và nhập lại xác nhận. Mã được băm như mật khẩu trước đây; không lưu mã mới dưới dạng rõ trong Credential Manager. Khi bảo vệ bật, đổi mã/tắt bảo vệ phải xác thực mã hiện tại. Không đổi thiết lập trong phiên học. Khi không học, thoát ứng dụng không yêu cầu mã.

Nút tạo mật khẩu ngẫu nhiên, xem/xóa và liên kết mã khẩn cấp đã bỏ khỏi giao diện thông thường. Cần tự giữ mã đã đặt; luồng phục hồi mã bị quên chưa được thiết kế lại. Phần Gmail nằm trong mục cũ thu gọn, chỉ dùng cấu hình/gửi thử; mô tả SMTP phía trên là chi tiết cơ chế cũ, không còn là luồng bắt đầu học. Dịch vụ gửi mã chỉ cần địa chỉ Gmail vẫn chưa triển khai.

Cập nhật giao diện: các mục model, API key, watchdog và whitelist đã bỏ khỏi Cài đặt người dùng. Xem [cấu hình dành cho developer](docs/DEVELOPER_SETTINGS.md). Bộ xử lý vẫn dùng cấu hình hiện có; việc ẩn UI không tự cài model hoặc dịch vụ email.


### Quyền đọc màn hình và thời lượng

Trong Cài đặt, mục quyền riêng tư cho phép bật/tắt AI đọc màn hình và hiển thị nơi xử lý ảnh. Mặc định không đọc màn hình; cả cấu hình cũ cũng cần xác nhận nơi xử lý một lần. Nếu đổi từ xử lý tại máy sang Anthropic, cần bật và đồng ý lại. Tắt sẽ ngừng các lần đọc mới; yêu cầu đã gửi có thể tiếp tục hoàn tất. Cấu hình model/API vẫn thuộc phần dành cho nhà phát triển.

Thời gian học/nghỉ phải là số nguyên từ 1 đến 1440 phút; nhập sai sẽ được báo ngay dưới ô khi bấm bắt đầu. Phiên học mới lưu mã định danh để phần thưởng chưa lưu xong có thể được tiếp tục khi mở lại ứng dụng, tránh cộng điểm trùng.
