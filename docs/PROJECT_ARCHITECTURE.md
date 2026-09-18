# DOUYIN TO TIKTOK/YOUTUBE - SYSTEM ARCHITECTURE & DEVELOPER KNOWLEDGE

> **LƯU Ý DÀNH CHO AI (SYSTEM PROMPT):** Khi bạn (AI) được yêu cầu làm việc với dự án này, **BẮT BUỘC PHẢI ĐỌC KỸ FILE NÀY** và [docs/KNOWN_BUGS_AND_FIXES.md](file:///e:/Project_ItWebDev/Python/tiktok-upload-video/docs/KNOWN_BUGS_AND_FIXES.md) trước khi đưa ra bất kỳ thay đổi Code nào để đảm bảo không phá vỡ luồng (Flow) và kiến trúc (Architecture) đã được thiết lập sẵn.

## 1. TỔNG QUAN DỰ ÁN (OVERVIEW)
Tool Python sử dụng `CustomTkinter` cho giao diện người dùng (GUI), kết hợp `FastAPI` làm Backend quản lý bản quyền (License). Chức năng chính:
- Tải video Douyin không watermark (Dùng API web và `yt-dlp`).
- Xử lý video chống Reup bằng FFmpeg (Chỉnh tốc độ, Mirror, Crop, Phụ đề AI, Lồng tiếng AI).
- Tự động Upload lên TikTok/YouTube sử dụng `Playwright`.
- **Farm Flow (Nuôi Nick):** Chạy tương tác (Lướt, Like, Follow) theo kịch bản Flow Builder dạng kéo thả.
- **Phân quyền đa người dùng (Multi-tenant):** Dữ liệu của từng User/Role được cách ly hoàn toàn.

---

## 2. CẤU TRÚC THƯ MỤC (DIRECTORY STRUCTURE)
```text
tiktok-upload-video/
├── backend/                  # Server FastAPI (Quản lý User, License, gọi API AI (Groq/Gemini))
│   ├── main.py               # Chứa các endpoint Auth & Groq proxy
│   └── database.py           # SQLite db lưu trữ thông tin User (auth.db)
├── config/
│   ├── settings.py           # Biến cấu hình chung, quản lý hàm get_user_downloads_dir...
│   └── cookies/              # Thư mục chứa dữ liệu Cách ly (Isolated) của từng User
│       └── <username>/       # Dữ liệu tài khoản TikTok/YouTube, settings.json, workflows.
├── crawler/
│   └── douyin_crawler.py     # Tải video Douyin, lấy Info bằng httpx & yt-dlp
├── database/
│   ├── db_manager.py         # Quản lý file SQLite (videos.db) lưu trạng thái video (crawled, processed, posted)
│   └── videos.db             # DB chứa 3 bảng chính: crawled_videos, posted_videos, daily_stats
├── processor/
│   ├── video_processor.py    # Chứa FFmpeg commands chống Reup, Lồng tiếng, Subtitles
│   └── subtitle_generator.py # Sinh phụ đề bằng AI
├── uploader/
│   ├── tiktok_uploader.py    # Chạy Playwright upload TikTok & Thực thi Kịch bản Farm (Nuôi nick)
│   └── youtube_uploader.py   # Upload qua Google Data API / Playwright (YouTube)
├── gui.py                    # File chính giao diện - Chứa toàn bộ các Tabs (Crawl, Process, Upload, Auto, Settings, Farm)
├── gui_flows.py              # File Giao diện Flow Builder (Kéo thả khối chức năng Nuôi Nick)
└── auth_client.py            # Client kết nối tới backend, giữ trạng thái đăng nhập (auth_client.user_info)
```

---

## 3. CÁC LUỒNG HOẠT ĐỘNG CHÍNH (CORE WORKFLOWS)

### 3.1. Luồng Xác Thực, Bản Quyền & Phân Quyền (Auth & Licensing)
- Người dùng đăng nhập qua `gui.py` -> Gọi `auth_client.py` -> Backend `main.py`.
- **Tài khoản mới đăng ký (Free Trial 10 ngày)**:
  - Khi đăng ký tài khoản qua `/register`, hệ thống tự động gán gói Free và thời hạn 10 ngày: `plan_expires_at = now + 10 days`.
  - Hết thời hạn 10 ngày, tài khoản chuyển sang trạng thái hết hạn (`is_expired = True`). Các tab tác vụ (Crawl, Process, Upload, Auto, Farm) sẽ tự động khóa và điều hướng người dùng sang trang quét mã QR thanh toán để gia hạn.
- **Hạn mức xử lý (Process Quota)**:
  - `role == "admin"`: Toàn quyền, vô hạn lượt.
  - `role == "vip"` hoặc `role == "pro"` (Gói bản quyền trả phí): Không giới hạn lượt render video.
  - `role == "user"` (Gói Free dùng thử 10 ngày): Giới hạn tối đa **5 Video/Ngày** (kiểm tra qua `db_manager.get_today_processed_count` và lưu vết HWID theo ngày). Hạn mức tự động hồi 5 video sau 00:00 mỗi ngày.
- **Cấu hình AI Dịch Thuật Mặc Định**:
  - Đối với tài khoản gói Free, cấu hình AI mặc định được ưu tiên là **"Cloud API trước ➔ Dự phòng Ollama"** (`cloud_first`).
  - Hệ thống sử dụng Cloud API có sẵn trên máy (Vilao / Gemini / Groq), nếu gặp sự cố hoặc hết quota sẽ tự động chuyển sang Ollama Local để cứu hộ không làm gián đoạn luồng xử lý.

### 3.2. Luồng Cách Ly Dữ Liệu Theo Người Dùng (Data Isolation)
**RẤT QUAN TRỌNG:** Mọi file dữ liệu phải được lưu theo `username` của người đăng nhập hiện tại để tránh việc người dùng xem được file hoặc cấu hình của nhau.
- **Tài khoản TikTok (Cookies) & Proxies:** Lưu tại `config/cookies/<username>/`
- **Cấu hình Gemini API / Setting riêng:** Lưu tại `config/cookies/<username>/settings.json`. KHÔNG dùng `.env` chung.
- **Thư mục Tải về:** Lưu tại `downloads/<username>/` (Lấy qua `get_user_downloads_dir()` trong `settings.py`).
- **Thư mục Đã Xử lý:** Lưu tại `processed/<username>/` (Lấy qua `get_user_processed_dir()`).
- **Flow Kịch Bản Nuôi Nick:** Lưu tại `config/cookies/<username>/workflows/`.
- **Database (`videos.db`):** Tất cả các lệnh Query (Get videos, Add video, Stats) đều phải truyền biến `username=current_user` để filter riêng dữ liệu của người đó.

### 3.3. Luồng Crawl Video Douyin (Crawler Architecture)
- File đầu não: `crawler/douyin_crawler.py`
- Tải video không watermark qua multi-service fallback (musicaldown, savetik, snapdouyin, dlpanda) kết hợp yt-dlp native.
- **Cơ chế Cookie & Session Security**:
  - Douyin yêu cầu cookie phiên thiết bị `s_v_web_id` (`verify_{hex}_{rand}`).
  - Hệ thống tự động kiểm tra `config/cookies/douyin_cookies.txt`, nếu thiếu sẽ tự sinh mã hợp lệ theo thuật toán ByteDance và nối vào file.
  - Trong các lượt retry của `yt-dlp`, tuyệt đối bảo lưu `cookiefile` (không pop cookie) để tránh bị cơ chế anti-bot Douyin chặn `Fresh cookies needed`.

### 3.4. Luồng Chống Reup, Phụ Đề AI & Lồng Tiếng AI Dubbing (Video Processor)
- File đầu não: `processor/video_processor.py`, `processor/subtitle_generator.py`, `utils/subtitle_detector.py`, `utils/translator.py`, `utils/tts_engine.py`
- Sử dụng FFmpeg Native để xử lý tốc độ cao.
- **Bypass TikTok / YouTube Shorts**:
  - Đảo chiều (Mirror), Thay đổi Tốc độ (Speed 0.97x - 1.03x).
  - Cắt Zoom hình (Crop 15%), Xoay hình vi mô (Micro-rotation), Thêm Nhiễu (Noise), Điều chỉnh Màu sắc (Contrast/Saturation) nhằm phá mã băm (MD5/pHash/SSIM).
- **Làm Mờ Phụ Đề Gốc Thông Minh (Smart Subtitle Blur & AI Auto-Detect)**:
  - Module: `utils/subtitle_detector.py` (tích hợp OpenCV Native).
  - Thuật toán: Trích xuất keyframe, downscale về 360p siêu tốc (~0.2s), áp dụng Canny Edge Detection và phân tích hình chiếu cạnh ngang (Horizontal Edge Projection) để cô lập chính xác dải tọa độ Y của phụ đề tiếng Trung cũ.
  - Hệ thống áp dụng bộ lọc làm mờ Gaussian Blur (`gblur=sigma=18`) vừa khít dòng chữ (độ dày chỉ ~7% - 9% chiều cao video), chấm dứt hoàn toàn tình trạng dán mảng mờ đen 15-20% làm mất thẩm mỹ video.
  - **5 Presets Vị Trí Mờ trên Giao Diện GUI**:
    1. `🤖 Tự động (AI Auto-Detect)`: Quét tự động từng video, độ dày co giãn thông minh (`Auto` ~8%).
    2. `Chuẩn Douyin (Cách đáy ~20%)`: Tọa độ Y tâm ~75.7% (cách đáy 20%), độ dày chuẩn 8.5%, phù hợp phần lớn video ngắn Douyin.
    3. `Phụ đề cao (Tránh UI TikTok)`: Tọa độ Y tâm ~60.7% (cách đáy 35%), né hoàn toàn vùng caption dài, thanh âm thanh và các nút like/share của TikTok.
    4. `Dưới cùng (Đáy video)`: Mờ sát mép đáy video (độ dày tùy biến, mặc định 15%).
    5. `Trên cùng (Đỉnh video)`: Mờ sát mép trên cùng (độ dày 8.5%) cho video có sub/tiêu đề treo ở đỉnh.
  - Cơ chế Reactive UI: Khi đổi vị trí mờ, ô `Độ dày` tự động cập nhật giá trị tương ứng (`Auto`, `8%`, `15%`) và hỗ trợ nhập thủ công nếu muốn tùy biến. Khi tắt switch Làm mờ, toàn bộ công cụ mờ sẽ tự động chuyển sang trạng thái disabled.
- **Căn Chỉnh Phụ Đề Tiếng Việt Thích Ứng (Adaptive MarginV Alignment)**:
  - Module: `processor/video_processor.py`
  - Dropdown `_opt_sub_pos` gồm 4 tùy chọn: `Đè lên vùng mờ` (mặc định), `Cao (Tránh TikTok UI)`, `Dưới cùng (Chuẩn đáy)`, `Giữa màn hình`.
  - Khi chọn `Đè lên vùng mờ`: Hệ thống tự động tính tâm dải mờ `center_y_ratio = blur_y_start + (blur_h / 2.0)` và chuyển đổi thành `MarginV = int(video_height * (1.0 - center_y_ratio))` (hoặc `Alignment=8` nếu dải mờ ở đỉnh). Đảm bảo phụ đề dịch tiếng Việt luôn in cứng (Hardsub) đè chuẩn xác 100% vào giữa dải mờ, che phủ trọn vẹn chữ Trung cũ mà không làm lệch thẩm mỹ.
  - Khi tắt làm mờ: Phụ đề tự động hạ về vị trí chuẩn Douyin (cách đáy 18%), không bị nhảy bừa vào giữa màn hình.
- **Trích xuất âm thanh & Nhận diện tiếng nói (Whisper)**:
  - Tự động phát hiện GPU CUDA, nếu không có sẽ dùng CPU đa luồng với model `medium` hoặc `base`.
  - Bộ lọc âm chuẩn hóa động DynAudNorm (`highpass=f=80,dynaudnorm=f=125:g=15:p=0.95:m=10.0`) giúp khuếch đại lời thì thầm, tiếng nói nhỏ và tự sự.
  - **Tắt `vad_filter=False` & Ngưỡng âm học `no_speech_threshold=0.6`**: Bắt trọn 100% tiếng nói, la hét, khóc mếu, giọng hoạt hình hài hước của nhân vật trên nền nhạc kịch tính mà không bị Silero VAD cắt bỏ âm thanh.
  - **Phân bổ thời gian & Giới hạn thời lượng (`eff_end`)**: Tách câu theo độ dài ký tự thực tế và cắt bỏ đuôi im lặng dư thừa, ngăn phụ đề treo lâu trên màn hình.
  - **Lọc trùng lặp liên tiếp (Anti-Hallucination)**: Tự động triệt tiêu các câu lặp lại do Whisper sinh ra khi gặp nhạc nền.
- **Dịch Phụ Đề AI & Cơ Chế Cứu Hộ 2 Tầng (Auto-Rescue Subtitle)**:
  - **Cloud AI (Groq / Gemini)**: Quy trình 2-Pass (Pass 1 sửa lỗi Whisper tiếng Trung, Pass 2 dịch sang văn phong Việt hóa mượt mà). Tự động nhận diện API key (`gsk_` cho Groq, `AIza` cho Gemini) bất kể thứ tự cấu hình.
  - **Local Offline AI (Ollama - Qwen2.5)**: Chế độ **1-Pass Siêu Tốc** (vừa sửa lỗi vừa dịch trong 1 lần gọi duy nhất với prompt tiếng Trung tinh gọn ~20 dòng, context 4096, predict 2048, giới hạn 25 câu/lô, cấm `<think>...</think>`, dùng tối đa 8 threads CPU, timeout 35s). Giúp giảm 50% thời gian xử lý và chống đóng băng ứng dụng khi CPU quá tải.
  - **Cứu hộ Tầng 1 (Toàn lô)**: Nếu Ollama/Cloud AI lỗi hoặc timeout 35s sau retry, hệ thống tự động kích hoạt Google Translate cứu hộ toàn bộ lô câu để quy trình không bao giờ bị dừng giữa chừng.
  - **Cứu hộ Tầng 2 (Từng câu sót chữ Hán)**: Quét toàn bộ file SRT bằng regex chữ Hán `[\u4e00-\u9fff]`. Câu nào còn sót chữ Hán (do AI bỏ sót hoặc giữ nguyên) sẽ lập tức được dịch riêng qua Google Translate. Đảm bảo 100% video ra lò sạch bóng tiếng Trung.
- **Đối Chiếu Sub và Voice Thời Gian Thực Lên GUI**:
  - Tích hợp loguru sink `_gui_log_sink` đẩy trực tiếp bảng đối chiếu câu gốc - câu dịch - giọng đọc TTS lên màn hình hiển thị Log của GUI.
- **Lồng Tiếng AI (AI Voiceover Dubbing) & Chống Câm Tiếng**:
  - **Microsoft Edge TTS**: Miễn phí 100%, không cần API key, giọng đọc tự nhiên đa dạng (`vi-VN-NamMinhNeural`, `vi-VN-HoaiMyNeural`), hỗ trợ chế độ Đa giọng thoại nam/nữ theo kịch bản.
  - **Vbee TTS**: Giọng đọc thương mại, yêu cầu cấu hình `VBEE_API_KEY`.
  - **Bộ lọc bảo vệ TTS**: Tự động dịch sạch chữ Hán sang tiếng Việt trước khi đưa vào Edge TTS để tránh Edge TTS nói tiếng Trung hoặc câm tiếng.
  - **Cơ chế Auto-Fallback & Retry**: Tự động fallback sang Edge TTS nếu Vbee lỗi/thiếu key; giới hạn retry tối đa 2 lần khi gặp lỗi `No audio was received` của Edge TTS, đảm bảo video 100% không bị mất tiếng thuyết minh.
- **Audio Ducking & Hardsub**:
  - Ghép nhạc nền trending với thuật toán Audio Ducking (tự động hạ âm lượng nhạc nền khi có giọng thuyết minh AI).
  - Subtitle tiếng Việt được in cứng (Hardsub) trực tiếp vào video bằng FFmpeg.

### 3.5. Luồng Nuôi Nick TikTok (Farm Flow)
- Người dùng tự vẽ kịch bản bằng Giao diện Nodes kéo thả tại `gui_flows.py` (FarmTab bên `gui.py`).
- Kịch bản lưu dưới dạng file JSON (VD: `scroll_like_follow.json`).
- Khi bấm Chạy, gửi tên File kịch bản xuống `TikTokUploader.execute_farm_flow()`.
- Lệnh được Parser đọc, duyệt qua từng Block (Scroll, Random Delay, Like, Follow) và thực thi bằng `Playwright` thông qua việc tìm các Data-TestID hoặc Locators tương ứng.
- **Lưu ý:** TikTok thay đổi DOM liên tục, nên các Locator trong `tiktok_uploader.py` (ví dụ nút Like, Follow) luôn phải dùng cơ chế Đa điều kiện (Multiple fallbacks).

---

## 4. QUY TẮC CẦN NHỚ KHI CODE (CODING CONVENTIONS)
1. **Tuyệt đối KHÔNG thay đổi kiến trúc thư mục:** Các file `DOWNLOADS_DIR` hay `PROCESSED_DIR` đã được chuyển thành hàm động. Không được gán cứng (hardcode) đường dẫn chung.
2. **Cập nhật UI trong GUI.py:** Bất cứ khi nào chuyển Tab hoặc Đăng nhập lại, phải thiết kế hàm Refresh danh sách (ví dụ `_load_accounts()`, `_load_videos()`) để giao diện load đúng dữ liệu của user mới, tránh hiện tượng cache nhầm dữ liệu của User cũ.
3. **Threading (Đa luồng):** Thao tác nặng (Crawl, Process bằng FFmpeg, Upload Playwright) bắt buộc phải dùng `_run_in_thread()` để không làm đơ (freeze) giao diện CustomTkinter chính. Log phải được push về UI qua `self._log()`.
4. **Mở rộng Limit:** Nếu muốn đổi giới hạn (như 10 thành 20), thì đổi trực tiếp logic trong hàm `_start_process` và `_start_upload` ở file `gui.py`.

*File này được tạo để đảm bảo tính đồng bộ của hệ thống. Luôn bám sát các Flow trên.*
