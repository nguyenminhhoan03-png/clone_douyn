# TIKTOK AUTO-UPLOADER - KNOWN BUGS & FIXES

Tài liệu này tổng hợp lại toàn bộ những lỗi (bugs) hóc búa, các edge-cases và cách giải quyết (Architecture Decisions) trong quá trình phát triển tool TikTok Auto-Uploader (đặc biệt là phần Livestream Seeder và Quản lý Tài khoản).
Đọc kỹ tài liệu này trước khi code tính năng mới để tránh lặp lại lỗi cũ (regression bugs).

---

## 1. Lỗi Treo Trình Duyệt (Timeout `new_page()`) với Camoufox trên Windows
- **Vấn đề**: Khi khởi chạy Camoufox (Firefox) thông qua Playwright trên môi trường Windows, đặc biệt là khi mở nhiều luồng (multiprocessing/threading) cùng lúc, tiến trình Render của trình duyệt hay bị kẹt (hang), dẫn đến lỗi `TimeoutError` khi gọi `await context.new_page()`.
- **Nguyên nhân**: Xung đột của chế độ Content Sandbox trên Windows đối với engine Firefox tuỳ chỉnh.
- **Giải pháp**: Bắt buộc phải **tắt Content Sandbox** bằng biến môi trường trước khi launch Camoufox.
- **Code áp dụng**:
  ```python
  import os
  custom_env = os.environ.copy()
  custom_env["MOZ_DISABLE_CONTENT_SANDBOX"] = "1"
  camoufox_args = {"env": custom_env, ...}
  ```
  *(Lưu ý: Mặc dù tắt Sandbox làm giảm bảo mật, nhưng đây là bắt buộc để Camoufox không bị crash trên Windows khi chạy đa luồng).*

## 2. Lỗi `407 Proxy Authentication Required` (Lỗi do ký tự `@` trong mật khẩu)
- **Vấn đề**: Khi sử dụng Proxy có chứa ký tự `@` trong mật khẩu (VD: `Hoanphe1@`), Camoufox văng lỗi 407 ngay trước khi trình duyệt kịp mở lên.
- **Nguyên nhân**: Thuộc tính `geoip=True` của Camoufox sử dụng thư viện `requests` của Python ở bên dưới để lấy thông tin toạ độ IP. Thư viện `requests` bị "ngu" khi parse URL Proxy dạng `http://user:pass@ip:port` nếu mật khẩu có chứa chữ `@`. Nó sẽ nhận diện sai điểm phân tách, gửi sai thông tin đăng nhập lên server Proxy.
- **Giải pháp**: **Vô hiệu hoá `geoip=False`** khi khởi tạo Camoufox. Playwright tự quản lý Proxy cực kỳ tốt và không bị lỗi parse chữ `@` này.
- **Code áp dụng**:
  ```python
  camoufox_args = {
      "headless": False,
      "geoip": False, # Bắt buộc False để tránh lỗi parse chữ @ trong mật khẩu Proxy
      ...
  }
  ```

## 3. Lỗi TikTok quét Bot & Đá văng khỏi Livestream (Cookie Cross-Contamination)
- **Vấn đề**: Tài khoản xem Livestream bị TikTok phát hiện là Bot và sút văng ra trang chủ ngay khi vào phòng Live.
- **Nguyên nhân**: Tool trước đây dùng chung 1 file Cookie (VD: `tiktok_acc.json`) cho cả Chromium (chạy Farm) và Camoufox (chạy Seeding). TikTok cực kỳ nhạy cảm với việc thay đổi Engine Trình duyệt. Việc dùng Cookie của Chrome nhét vào Firefox khiến hệ thống Anti-bot của TikTok kích hoạt.
- **Giải pháp (Senior++ Architecture)**: 
  - Tách biệt hoàn toàn Cookie Storage: 
    - Cookie đăng nhập bằng Chrome (Farm) lưu vào `tiktok_{acc}.json`.
    - Cookie đăng nhập bằng Camoufox (Livestream) lưu vào `camoufox_{acc}.json`.
  - Thiết kế UI (Trong `gui.py`) hiển thị nút Login độc lập trực tiếp tại Tab Farm và Tab Livestream để người dùng không bị nhầm lẫn.

## 4. Lỗi Race Condition `name '_camoufox_init_lock' is not defined`
- **Vấn đề**: Khi bấm Start Seeding với nhiều tài khoản, Playwright báo lỗi thiếu Lock.
- **Nguyên nhân**: Hàm khởi tạo bất đồng bộ của Playwright/Camoufox bị đụng độ tài nguyên khi chạy trên đa luồng (Multi-threading + Asyncio).
- **Giải pháp**: Định nghĩa biến Global `_camoufox_init_lock = asyncio.Lock()` ở cấp module (đầu file `livestream_seeder.py`) và dùng `async with _camoufox_init_lock:` để ép việc khởi động trình duyệt chạy tuần tự.

## 5. Lỗi Scope Biến (UnboundLocalError) trong Tkinter/Python
- **Vấn đề**: Báo lỗi `UnboundLocalError: cannot access local variable 'SUCCESS' where it is not associated with a value` khi render giao diện Tab.
- **Nguyên nhân**: Do thói quen import thư viện ở giữa hàm (`import json`, `from config.settings import SUCCESS`). Python phân tích (compile) các biến local ở mức độ toàn hàm. Nếu biến trùng tên với global (ở đầu file đã có `SUCCESS = "#xxx"`) thì Python coi nó là biến local và gây lỗi nếu gọi biến đó trước dòng import.
- **Giải pháp**: 
  - Dọn dẹp các dòng `import` rác.
  - Luôn luôn đặt `import` ở đầu file hoặc đầu hàm. Không đặt xen kẽ giữa các vòng lặp tạo UI (`for acc in accounts:`).

## 6. Lỗi Douyin báo `Fresh cookies (not necessarily logged in) are needed`
- **Vấn đề**: Khi crawl video Douyin bằng yt-dlp, tool báo lỗi `ERROR: [Douyin] ...: Fresh cookies (not necessarily logged in) are needed` dù đã copy cookie từ Cookie-Editor.
- **Nguyên nhân**: 
  1. Douyin yêu cầu bắt buộc phải có cookie phiên thiết bị là `s_v_web_id` (dạng `verify_{hex_time}_{random_chars}`). Khi export cookie tài khoản thông thường, trường này thường bị thiếu hoặc không thuộc domain `.douyin.com`.
  2. Trong hàm `_ytdlp_extract_info`, ở lần thử thứ 2 (attempt 2), code cũ gọi `opts.pop("cookiefile")` để thử không dùng cookie, khiến Douyin chặn ngay lập tức.
- **Giải pháp**:
  - Tự động kiểm tra file `config/cookies/douyin_cookies.txt`: Nếu chưa có `s_v_web_id`, tool tự động sinh mã `verify_...` hợp lệ theo thuật toán của ByteDance và ghi nối vào file cookie.
  - Sửa hàm `_ytdlp_extract_info` và `_build_ydl_opts`: Tuyệt đối không xóa bỏ `cookiefile` khi retry.

## 7. Lỗi Timeout 180s (`Read timed out`) & Lâu Lắc khi Dịch bằng Ollama Local
- **Vấn đề**: Khi dịch phụ đề bằng Ollama Local (model `qwen2.5` trên CPU), tiến trình bị treo hơn 6 phút rồi văng lỗi `HTTPConnectionPool: Read timed out (read timeout=180)`, sau đó rớt về Google Translate dịch sai nghĩa thô thiển.
- **Nguyên nhân**:
  1. Prompt dịch cũ dài hơn 600 dòng (~3.500 tokens) được thiết kế cho Cloud AI (Groq/Gemini). Khi đưa vào CPU nạp, CPU phải mất hơn 3 phút chỉ để tính ma trận Attention cho prompt.
  2. Model Qwen có xu hướng sinh hàng nghìn token suy nghĩ ngầm (`<think>...</think>`), chiếm dụng CPU làm nghẽn quá trình sinh kết quả thật.
  3. Quy trình chạy 2-Pass độc lập (Pass 1 sửa Whisper tiếng Trung, Pass 2 dịch tiếng Việt) khiến CPU phải gọi AI gấp đôi (6 lần gọi cho video 55 câu).
  4. Context Window mặc định quá lớn, không ép số luồng đa nhân CPU.
- **Giải pháp (Tối ưu hóa Ollama Local Siêu Tốc)**:
  - **Tách riêng prompt tinh gọn cho Ollama**: Chuyển prompt sang tiếng Trung ngắn gọn (~20 dòng, ~150 tokens) giúp CPU nạp prompt trong 0.5 giây.
  - **Cắt bỏ hoàn toàn `<think>`**: Thêm lệnh cấm think ở System Instruction và gán `stop: ["<think>", "</think>"]`.
  - **Tối ưu phần cứng trong `auth_client.py`**: Cấu hình `num_ctx: 2048`, `num_predict: 800`, `num_thread: 8` (dùng tối đa 8 nhân CPU), ưu tiên gọi native endpoint `/api/generate`.
  - **Chuyển sang chế độ 1-Pass Siêu Tốc**: Tích hợp việc sửa lỗi nghe sai của Whisper và dịch thẳng sang tiếng Việt trong 1 lần gọi duy nhất. Giảm 50% thời gian xử lý (từ 102s xuống 59s/lô).
  - Cung cấp sẵn script `test_ai_ollama.py` để test nhanh tốc độ và chất lượng dịch độc lập.

## 8. Lỗi Video Xuất Ra Bị Mất Tiếng Thuyết Minh AI (`Không tạo được segment TTS nào`)
- **Vấn đề**: Video xử lý xong có phụ đề Vietsub nhưng hoàn toàn không có giọng đọc thuyết minh lồng tiếng AI. Log ghi: `WARNING: Không tạo được segment TTS nào`.
- **Nguyên nhân**:
  - Người dùng chọn các giọng của **Vbee** (như `Vbee - Đa giọng (Đoản kịch)`, `Vbee - Ngọc Huyền`) trong khi chưa đăng ký và điền `VBEE_API_KEY` vào file `.env`.
  - API Vbee từ chối toàn bộ request không có token xác thực.
- **Giải pháp**:
  - Khuyến nghị sử dụng bộ giọng **Microsoft Edge TTS** miễn phí 100% không cần key (chọn `Đa giọng (Đoản kịch)`, `Giọng Nam`, `Giọng Nữ`).
## 9. Lỗi Edge TTS Báo `No audio was received` và Kẹt Vòng Lặp Do Sót Câu Tiếng Trung
- **Vấn đề**: Khi lồng tiếng video, terminal spam liên tục:
  `TTS seg74_c0 attempt 7 error 'No audio was received. Please verify that your parameters are correct.'`
  `TTS seg175_c0 failed (我也玩不了了): No audio was received...`
  Tiến trình xử lý bị kẹt hàng chục phút chỉ để retry các câu tiếng Trung thất bại.
- **Nguyên nhân**:
  1. **Ollama trả về rỗng nhưng code cũ return `payload_text`**: Trong `utils/translator.py`, khi Ollama gặp lỗi ở 1 chunk (như chunk từ 175 trở đi), code cũ `return payload_text` (chính là tiếng Trung gốc) khiến hệ thống tưởng dịch thành công và ghi thẳng tiếng Trung vào phụ đề SRT.
  2. **Hạn mức `num_predict: 800` quá ngắn**: Lô 25 câu tiếng Việt cần ~1200 tokens. Mức 800 tokens khiến Ollama bị hết quota ở câu cuối cùng (câu thứ 25 của lô, tức câu 74), dẫn đến câu 74 không kịp sinh ra và bị rớt về tiếng Trung `死是死消气`.
  3. **Voice tiếng Việt từ chối chữ Hán**: Edge TTS với giọng Việt (`vi-VN-NamMinhNeural` / `vi-VN-HoaiMyNeural`) không hỗ trợ ký tự tiếng Trung, trả về lỗi `No audio was received. Please verify that your parameters are correct.`.
  4. **Retry quá nhiều lần vô ích**: Bộ đệm retry 7 lần với backoff lên đến 10s khiến mỗi câu tiếng Trung bị kẹt hơn 60s (12 câu kẹt hơn 12 phút).
- **Giải pháp toàn diện**:
  - **Tăng token trong `auth_client.py`**: Tăng `num_ctx: 4096`, `num_predict: 2048`, `max_tokens: 2048` để Ollama sinh trọn vẹn 25 câu mà không bị cụt đuôi.
  - **Báo lỗi chuẩn trong `utils/translator.py`**: Khi Ollama lỗi hoặc rỗng, `return None` để kích hoạt cơ chế fallback thay vì trả về text tiếng Trung.
  - **Cơ chế Cứu trợ Chunk & Từng Câu (Rescue System)**:
    - Trong `subtitle_generator.py`: Nếu chunk nào AI không phản hồi, tự động dùng Google Translate dịch cứu trợ lô đó.
    - Duyệt qua từng câu trong SRT: Nếu câu nào còn sót ký tự chữ Hán `[\u4e00-\u9fff]`, tự động dịch khẩn cấp sang tiếng Việt bằng Google Translate ngay lập tức. Đảm bảo phụ đề 100% là tiếng Việt sạch sẽ.
  - **Lớp phòng thủ an toàn tại `utils/tts_engine.py`**: Nếu text chuyển vào TTS vẫn còn chữ Hán, tự động dịch sang tiếng Việt trước khi gửi cho Edge TTS. Đồng thời giới hạn lỗi `No audio was received` chỉ thử lại tối đa 2 lần để tránh kẹt thời gian.

---
*Lưu ý cho AI Assistant: Luôn đọc file này trước khi propose các thay đổi kiến trúc hoặc debug các lỗi liên quan đến Playwright/Camoufox/Ollama/TTS.*
