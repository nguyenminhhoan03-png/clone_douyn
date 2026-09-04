# DOUYIN TO TIKTOK/YOUTUBE - SYSTEM ARCHITECTURE & DEVELOPER KNOWLEDGE

> **LƯU Ý DÀNH CHO AI (SYSTEM PROMPT):** Khi bạn (AI) được yêu cầu làm việc với dự án này, **BẮT BUỘC PHẢI ĐỌC KỸ FILE NÀY** trước khi đưa ra bất kỳ thay đổi Code nào để đảm bảo không phá vỡ luồng (Flow) và kiến trúc (Architecture) đã được thiết lập sẵn.

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

### 3.1. Luồng Xác Thực & Phân Quyền (Auth & Permissions)
- Người dùng đăng nhập qua `gui.py` -> Gọi `auth_client.py` -> Backend `main.py`.
- Lấy được JWT Token và thông tin (Role, Giới hạn ngày).
- **Giới hạn (Limits):** Ở các thao tác `_start_process` và `_start_upload` trong `gui.py`, luôn kiểm tra `role`:
  - `role == "admin"`: Vô hạn.
  - `role == "user"`: Mặc định tối đa **10 Video/Ngày** (Process/Upload). Sử dụng `db_manager.get_today_processed_count` để đếm.

### 3.2. Luồng Cách Ly Dữ Liệu Theo Người Dùng (Data Isolation)
**RẤT QUAN TRỌNG:** Mọi file dữ liệu phải được lưu theo `username` của người đăng nhập hiện tại để tránh việc người dùng xem được file hoặc cấu hình của nhau.
- **Tài khoản TikTok (Cookies) & Proxies:** Lưu tại `config/cookies/<username>/`
- **Cấu hình Gemini API / Setting riêng:** Lưu tại `config/cookies/<username>/settings.json`. KHÔNG dùng `.env` chung.
- **Thư mục Tải về:** Lưu tại `downloads/<username>/` (Lấy qua `get_user_downloads_dir()` trong `settings.py`).
- **Thư mục Đã Xử lý:** Lưu tại `processed/<username>/` (Lấy qua `get_user_processed_dir()`).
- **Flow Kịch Bản Nuôi Nick:** Lưu tại `config/cookies/<username>/workflows/`.
- **Database (`videos.db`):** Tất cả các lệnh Query (Get videos, Add video, Stats) đều phải truyền biến `username=current_user` để filter riêng dữ liệu của người đó.

### 3.3. Luồng Chống Reup & AI Dubbing (Video Processor)
- File đầu não: `processor/video_processor.py`
- Sử dụng FFmpeg Native để xử lý tốc độ cao.
- **Bypass TikTok:** Đảo chiều (Mirror), Thay đổi Tốc độ (Speed).
- **Bypass YouTube:** Cắt Zoom hình (Crop 15%), Xoay hình vi mô (Micro-rotation), Thêm Nhiễu (Noise), Điều chỉnh Màu sắc (Contrast/Saturation) nhằm phá mã băm (MD5/pHash).
- **AI Dubbing & Subtitles:** Sử dụng `edge-tts` để lồng tiếng (Voiceover). Nếu có nhạc nền, sử dụng thuật toán Audio Ducking (hạ âm lượng nhạc khi có tiếng nói). Subtitle được in cứng (Hardsub) qua FFmpeg.

### 3.4. Luồng Nuôi Nick TikTok (Farm Flow)
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
