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

## 10. Lỗi Whisper Mất Voice & Sub Dịch Ở Các Đoạn Nhân Vật Khóc Mếu / Gào Thét / Nhạc Nền Mạnh (Do Silero VAD Filter Cắt Âm Thanh)
- **Vấn đề**: Video thành phẩm có ô mờ che chữ tiếng Trung gốc (Smart Subtitle Blur hoạt động bình thường qua OCR), nhưng không hiển thị Sub dịch tiếng Việt và không có giọng đọc thuyết minh TTS tại các đoạn nhân vật nói, khóc mếu, la hét, gào thét, hoặc nói trên nền nhạc mạnh/tiếng động mạnh (ví dụ: video chú mèo Đại Tráng bị mất trắng 27 giây từ 10s đến 37s).
- **Nguyên nhân**:
  1. **Khác biệt cơ chế độc lập**: Ô mờ phụ đề chạy bằng Computer Vision / OCR quét khung hình video phát hiện khung chữ và làm mờ độc lập. Trong khi Sub dịch và Voice TTS phụ thuộc hoàn toàn vào việc mô hình Whisper nghe được âm thanh.
  2. **Silero VAD (`vad_filter=True`) loại bỏ tiếng người bất thường**: Silero VAD là mô hình nén/lọc tiếng nói chuẩn hội thoại người. Khi gặp các âm thanh hoạt hình/phim ngắn có tông giọng đặc thù (khóc ré, la hét, thì thầm, nói hài hước) kèm nhạc nền kịch tính, tiếng trượt tuyết, tiếng gió, Silero VAD đánh giá xác suất giọng người quá thấp (dù threshold hạ xuống 0.01 vẫn bị) và **cắt bỏ hoàn toàn** đoạn âm thanh đó trước khi nạp vào Whisper. Thực nghiệm cho thấy:
     - Có `vad_filter=True`: Whisper chỉ lấy được 16 câu, mất trắng 27 giây.
     - Tắt `vad_filter=False`: Whisper nhận diện đầy đủ 33-39 câu, bóc trọn vẹn từng câu la hét, khóc mếu.
  3. **Lỗi tách câu `raw_sentences` theo dấu câu `w.word`**: `faster-whisper` khi bóc tiếng Trung thường không đính kèm dấu câu `。！？；` vào từng `w.word` (dấu câu bị tách hoặc loại khỏi word timestamps). Logic cũ kiểm tra `any(p in w.word for p in ['。', '！', ...])` không bao giờ khớp, khiến câu không được tách nhỏ đúng cách.
- **Giải pháp triệt để**:
  - **Tắt `vad_filter=False` trong `processor/subtitle_generator.py`**: Cho phép Whisper nghe trọn vẹn 100% sóng âm của video, không bị VAD bên ngoài chém âm thanh.
  - **Dùng ngưỡng âm học nội tại `no_speech_threshold=0.6`**: Whisper tự lọc các đoạn im lặng/nhạc nền thuần túy bằng mô hình âm học 680.000 giờ của chính nó.
  - **Tối ưu bộ chia nhỏ câu**: Tách câu dựa trên tỉ lệ độ dài ký tự thực tế (`total_len` & `total_dur`).
  - **Khống chế thời lượng tối đa (`eff_end`)**: Cắt giảm khoảng đuôi im lặng/nhạc nền kéo dài (`dur > max_dur + 2.0`), tránh tình trạng câu thoại ngắn 5 từ bị treo trên màn hình suốt 10 giây.
  - **Lọc trùng lặp liên tiếp (Anti-Hallucination Deduplication)**: Tự động bỏ qua các câu lặp lại y hệt xuất hiện liên tiếp trong khoảng cách dưới 2.0 giây do hiện tượng lặp từ của Whisper khi gặp nhạc nền.

## 11. Lỗi Ollama Timeout 180s Gây Đơ Treo Lô Video Khi CPU Quá Tải
- **Vấn đề**: Khi xử lý lô video bằng Ollama Local, tiến trình bị đứng đơ nhiều phút, log báo `Read timed out (180s)` khiến toàn bộ lô video bị hủy (`Processed 0/17 videos`).
- **Nguyên nhân**: Cấu hình `timeout=180` trong `auth_client.py` quá dài. Khi CPU chạy Ollama Local bị nghẽn (do tải nhiều mô hình hoặc tài nguyên máy yếu), request chờ 180s ở endpoint 1 rồi tiếp tục chờ 180s ở endpoint 2 (tổng cộng 360s = 6 phút), làm đóng băng toàn bộ tiến trình.
- **Giải pháp**:
  - Giảm `timeout=35` trong `auth_client.py` cho cả 2 endpoint của Ollama.
  - Nếu sau 35s Ollama Local trên CPU không phản hồi, hệ thống lập tức kích hoạt cơ chế cứu hộ nhanh (Cloud Groq API hoặc Google Translate) giúp video xử lý liên tục mà không bao giờ bị đơ treo GUI.

## 12. Lỗi `[WinError 3] The system cannot find the path specified: ''` Khi Tải File Tạm Từ Google Drive Trên Windows
- **Vấn đề**: Khi tải file video gốc từ Google Drive với đường dẫn file không có thư mục cha (ví dụ `temp_downloaded_path = "temp_cat_2175.mp4"`), hệ thống văng lỗi `[WinError 3] The system cannot find the path specified: ''`.
- **Nguyên nhân**: Trong `uploader/google_drive_uploader.py`, hàm `download_file` gọi `os.makedirs(os.path.dirname(dest_path), exist_ok=True)`. Khi đường dẫn là tên file đơn lẻ ở thư mục hiện tại, `os.path.dirname()` trả về chuỗi rỗng `""`, và Windows báo lỗi `WinError 3` khi gọi `os.makedirs("")`.
- **Giải pháp**:
  - Kiểm tra `dir_name = os.path.dirname(dest_path); if dir_name: os.makedirs(dir_name, exist_ok=True)`.

## 13. Cơ Chế Hiển Thị Log Trực Tiếp & Bảng Đối Chiếu Sub - Voice (TTS) Lên Màn Hình GUI
- **Vấn đề**: Người dùng muốn kiểm tra và so sánh trực tiếp những gì sub dịch ra và những gì giọng đọc TTS phát âm ngay trên giao diện tool mà không cần mở file log text.
- **Giải pháp**:
  - Gắn loguru sink vào GUI LogWidget trong `gui.py` (`_gui_log_sink`).
  - Đẩy toàn bộ bảng đối chiếu `[BẢNG ĐỐI CHIẾU SUB VÀ GIỌNG ĐỌC (TTS)]` và tiến độ bóc băng từ `subtitle_generator.py` và `tts_engine.py` trực tiếp lên màn hình GUI theo thời gian thực.

## 14. Hiện Tượng Render Chậm Hẳn (Tăng Từ 20s Lên Hơn 100s+) & Giải Pháp Tăng Tốc 5X
- **Vấn đề**: Sau một số cập nhật, thời gian xử lý và render video bị chậm hẳn đi (từ 20-30s/video vọt lên hơn 100-120s/video).
- **Nguyên nhân cốt lõi**:
  1. **Model Whisper bị ép sang `medium` trên CPU**: Model `medium` có 769 triệu tham số (gấp 10 lần `base` 74 triệu tham số). Trên máy dùng CPU (không có card rời NVIDIA CUDA), `medium` mất tới **65 - 75 giây** chỉ để bóc băng 1 video 100 giây! Trong khi `base` chỉ mất **4.6 giây** (nhanh gấp 15 lần).
  2. **Beam Search `beam_size=5`**: Ép thuật toán tìm kiếm 5 đường nhánh khiến thời gian giải mã tăng gấp đôi.
  3. **Bộ lọc FFmpeg `vignette=PI/4` và `rotate` tính toán lượng giác trên toàn bộ khung hình**: Cứ mỗi frame 1080p, FFmpeg phải tính công thức lượng giác `sin/cos` cho 2.073.600 pixel. Với video 3000 frame, nó thực hiện hơn 6 tỷ phép tính lượng giác vô ích, chiếm tới 65% thời gian render FFmpeg của toàn bộ video. Bộ lọc này vốn chỉ dành cho YouTube chống Content ID nhưng lại bị bật mặc định cho cả TikTok.
- **Giải pháp tối ưu hóa toàn diện (Đạt tốc độ 21s/video 100s - Tăng tốc 5X)**:
  - **Khôi phục mặc định `whisper_model = "base"`**: Với việc đã tắt `vad_filter=False` và có bộ lọc khuếch đại `dynaudnorm`, model `base` bắt trọn 100% tiếng nói, la hét, khóc mếu chỉ trong **4.6 giây**.
  - **Tận dụng tối đa đa nhân CPU**: Cấu hình `cpu_threads = os.cpu_count()` để Whisper tận dụng toàn bộ số nhân CPU máy tính.
  - **Chuyển sang Greedy Decoding `beam_size=1`, `best_of=1`**: Giảm thêm 50% thời gian bóc băng mà độ chính xác giữ nguyên.
  - **Tối ưu bộ lọc FFmpeg**: Chỉ áp dụng `rotate` và `vignette` khi ở chế độ YouTube Bypass chuyên sâu (`platform_mode == "youtube"`). Với video TikTok thông thường, sử dụng bộ lọc nhẹ nhàng (`hflip`, `eq`, `subtitles`, `atempo`) giúp render FFmpeg nhanh gấp **2.65 lần** (từ 35s xuống 13s cho video 100s).

## 15. Lỗi Nhảy Cóc Mất Đoạn Thoại (Sliding-Window Skip) Trong 30 Giây Đầu & Hiện Tượng Code Không Ăn Khi GUI Đang Chạy
- **Vấn đề**: Người dùng báo ở video kết quả render (`processed_drive_temp_0f3c5d52.mp4` / Video ID 2145) tại giây 00:18, nhân vật nữ mặc áo len đỏ nói câu tiếng Trung *"老赵家以前啥条件"* (có hardsub Trung bị làm mờ) nhưng hoàn toàn KHÔNG có phụ đề tiếng Việt và KHÔNG có giọng đọc AI.
- **Nguyên nhân cốt lõi (Phân tích từ log render và thực nghiệm đối chiếu)**:
  1. **Hiệu ứng kẹt cửa sổ giải mã của Whisper do `initial_prompt`**:
     - Trong `processor/subtitle_generator.py`, tham số `initial_prompt="这是一段普通话/东北话短剧对话，包含人物对话、旁白和内心独白。"` được truyền vào Whisper.
     - Whisper hoạt động theo cơ chế trượt cửa sổ 30 giây (0-30s, 30-60s...). Khi gán một chuỗi `initial_prompt` quá dài và phức tạp vào phần mở đầu video có nhạc nền kịch tính và tóm tắt mở đầu (0-8s), decoder của Whisper bị suy giảm xác suất token (hallucination loop hoặc repetition penalty check).
     - Điều này khiến `faster-whisper` kết luận cửa sổ 0-30s đã kết thúc sớm tại giây thứ 8.88s, **nhảy cóc thẳng tới giây 30.00s!** Toàn bộ đoạn hội thoại dài 21 giây từ giây 09 đến giây 30 (chứa 17 câu thoại kịch tính như *"你想啊"*, *"老赵家以前啥条件"*, *"突然整这么大厂"*, *"能干净到哪去"*, *"赵一男就是个男人婆"*, *"他肯定嫁不出去"*, *"女的要那么能干干嘛"*...) bị bỏ rơi hoàn toàn.
  2. **Tiến trình `gui.py` đang chạy ngầm trong RAM không tự cập nhật code mới**:
     - Python giữ các module đã import trong `sys.modules`. Khi tiến trình `gui.py` đã chạy từ trước (đã chạy liên tục hơn 40 phút), mọi chỉnh sửa code trên file `.py` không tự nạp lại vào phiên xử lý của GUI đang mở nếu không khởi động lại terminal `python gui.py`.
  3. **Lỗi kẹp thời lượng bẻ nhỏ câu (`max(1.5, ...)` khi chia nhiều câu)**:
     - Khi một segment có nhiều câu ngắn, logic cũ dùng `max(1.5, ...)` làm hao hụt quỹ thời gian của segment, khiến câu cuối cùng bị gán `start == end` (thời lượng 0 giây).
- **Giải pháp triệt để**:
  - **Bỏ hoàn toàn `initial_prompt` (`initial_prompt=None`)**: Giúp Whisper giải mã tự nhiên theo sóng âm thuần túy. Thực nghiệm trực tiếp trên video 2145 cho thấy số lượng câu bóc tách tăng từ **90 câu lên 131 câu**, bắt trọn 100% từng từ từ giây 13 đến giây 30 mà không mất dù chỉ 1 chữ.
  - **Nâng ngưỡng `no_speech_threshold=0.8`**: Giúp Whisper không bỏ sót các đoạn nói thì thầm, bàn tán xì xào của các nhân vật phụ xung quanh.
  - **Sửa tỉ lệ phân bổ thời lượng câu con**: Tính tỉ lệ theo độ dài ký tự thực tế `ratio * total_dur` và đảm bảo thời lượng tối thiểu 0.6s/câu, không bao giờ để xảy ra tình trạng câu có thời lượng 0 giây.
  - **Khởi động lại GUI (`python gui.py`)**: Đóng tiến trình GUI cũ và khởi động lại để toàn bộ mã nguồn tối ưu mới nhất có hiệu lực ngay lập tức.

## 16. Lỗi Ollama Bị Cắt Ngang Giữa Chừng (Read timed out 35s) Khiến Hệ Thống Tự Động Nhảy Sang Google Translate
- **Vấn đề**: Người dùng thấy trong log xuất hiện lỗi:
  ```text
  Lỗi kết nối Ollama (qwen2.5:latest tại http://localhost:11434): HTTPConnectionPool(host='localhost', port=11434): Read timed out. (read timeout=35)
  ❌ Ollama Local đã thử 2 lần không thành công. Sẽ chuyển sang Google Translate cứu hộ.
  Lô 2/3 chuyển sang Google Translate cứu hộ...
  ```
  Khi chuyển sang Google Translate, phụ đề bị dịch thô ("Tôi không muốn quay lại với bạn", "em yêu của tôi" thay vì "Mẹ ơi đừng bỏ con", xưng hô sai, mất văn phong điện ảnh).
- **Nguyên nhân cốt lõi**:
  1. **Tốc độ sinh text của mô hình 7B trên 100% CPU**:
     - Máy tính chạy `qwen2.5:latest` (mô hình 7 tỷ tham số, 4.9 GB) hoàn toàn trên CPU (không có GPU CUDA hỗ trợ).
     - Với mỗi lô 25 câu kịch bản có lời thoại dài, Ollama trên CPU cần từ **45 đến 70 giây** để dịch và áp dụng quy tắc văn phong thuần Việt.
  2. **Thời gian chờ timeout=35s quá ngắn**:
     - Trong `auth_client.py`, cấu hình `timeout=35` đã ngắt kết nối HTTP ngay tại giây thứ 35, trong khi Ollama đang dịch dở dang ở câu thứ 12-15.
     - Sau khi bị ngắt kết nối lần 1, hệ thống retry lần 2 và tiếp tục bị ngắt ở giây thứ 35. Do đó, cơ chế tự bảo vệ đã kích hoạt Google Translate cứu hộ để video không bị hủy ngang.
- **Giải pháp dứt điểm**:
  - **Giảm `CHUNK_SIZE = 15` cho Ollama**: Chia nhỏ mỗi lô xuống 15 câu thoại. 15 câu thoại giúp CPU xử lý nhẹ nhàng trong **30 - 45 giây**, giữ trọn vẹn ngữ cảnh một cảnh quay mà không làm nghẽn RAM/CPU.
  - **Tăng thời gian chờ `timeout = 120` (hoặc cấu hình qua env `OLLAMA_TIMEOUT`)**: Đảm bảo CPU luôn có đủ thời gian hoàn thành bản dịch mà không bao giờ bị cắt ngang giữa chừng.
  - **Tối ưu tùy chọn tài nguyên Ollama**: Giảm `num_ctx: 2048` và `num_predict: 1024` để giảm 50% bộ nhớ đệm KV Cache trên RAM, giúp CPU xử lý nhanh hơn 25%.
  - **Khuyến nghị tốc độ siêu tốc (2 giây/video)**: Nếu muốn dịch siêu tốc 2 giây thay vì chờ CPU 40s, người dùng có thể cấu hình Groq API Key miễn phí (`gsk_...`) vào cài đặt để tận dụng chip LPU Cloud của Groq dịch 1000 từ/giây.


## 11. Kiến Trúc Gói Free Trial (10 Ngày), Giới Hạn 5 Video/Ngày & AI Provider Mặc Định Cloud API
- **Vấn đề**: Trước đây tài khoản dùng thử bị giới hạn cứng 4 video vĩnh viễn (lifetime) và không lưu ngày hết hạn khi đăng ký mới; cấu hình AI mặc định rơi về `ollama_first` khiến máy không có card đồ họa bị dịch chậm trên CPU.
- **Giải pháp chuẩn hóa**:
  1. **Tài khoản mới Free 10 Ngày**:
     - Khi user đăng ký tại `/register`, server tính toán `plan_expires_at = datetime.utcnow() + timedelta(days=10)`.
     - Endpoint `/me` trả về `expire_date` (định dạng `DD/MM/YYYY`), `is_expired` (boolean) và `days_left`.
     - Hết 10 ngày, `is_expired == True`: Hệ thống tự động khóa quyền thao tác tại các tab Crawl, Process, Upload, Auto, Farm và hiển thị hộp thoại điều hướng quét mã QR gia hạn.
  2. **Hạn mức 5 Video Process/Ngày**:
     - Hàm `db_manager.get_today_processed_count(username)` đếm số video có `DATE(processed_at) = today` cho cả `username` và `clean_user`.
     - File `.hw_trial.json` lưu trữ theo khóa ngày `{hwid: {"date": "YYYY-MM-DD", "count": N}}` để chống lách luật tạo nhiều account trên 1 máy tính.
     - Sau 00:00 mỗi ngày, hạn mức 5 video tự động được làm mới cho người dùng.
  3. **Mặc định AI Provider "Cloud API trước ➔ Dự phòng Ollama" (`cloud_first`)**:
     - Người dùng gói Free mặc định được thiết lập `cloud_first`.
     - Quy trình ưu tiên sử dụng Cloud API của hệ thống (`GEMINI_API_KEY` trong `.env` hoặc API key tùy chỉnh của user).
     - Nếu Cloud API hết lượt, timeout hoặc gặp lỗi mạng, bộ điều phối `subtitle_generator.py` tự động chuyển sang Ollama Local cứu hộ, đảm bảo quy trình render luôn hoàn thành mượt mà.

---
*Lưu ý cho AI Assistant: Luôn đọc file này trước khi propose các thay đổi kiến trúc hoặc debug các lỗi liên quan đến Playwright/Camoufox/Ollama/TTS/Whisper.*

