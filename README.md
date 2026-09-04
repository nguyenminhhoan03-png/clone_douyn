# 🎬 Douyin Crawler & Multi-Platform Auto-Uploader

Tool tự động crawl video từ **Douyin** (TikTok Trung Quốc) → xử lý video (mirror, phụ đề Vietsub, thuyết minh AI, lồng nhạc, overlay) → auto post lên **TikTok**, **YouTube Shorts** và **Facebook Reels**.

> **Tài liệu hướng dẫn chuyên sâu**:
> - 📘 [Hướng dẫn cấu hình & thêm Facebook Reels](docs/HUONG_DAN_CAU_HINH_FACEBOOK_REELS.md)
> - 📖 [Hướng dẫn lệnh & vận hành hệ thống VPS](docs/COMMANDS.md)
> - 📌 [Ghi chú đồng bộ VPS & Chống trùng lặp](docs/NOTE_QUAN_TRONG.md)

---

## 📁 Cấu trúc Project

```
tiktok-upload-video/
├── config/
│   ├── settings.py              # Cấu hình chung
│   └── cookies/
│       ├── douyin_cookies.txt   # Cookies Douyin
│       └── tiktok_cookies.json  # Cookies TikTok
├── crawler/
│   └── douyin_crawler.py        # Module crawl video Douyin
├── processor/
│   └── video_processor.py       # Xử lý video (mirror, text, nhạc)
├── uploader/
│   └── tiktok_uploader.py       # Upload video lên TikTok (Playwright)
├── scheduler/
│   └── scheduler.py             # Lập lịch tự động
├── database/
│   └── db_manager.py            # SQLite quản lý dữ liệu
├── downloads/                   # Video tải về từ Douyin
├── processed/                   # Video đã xử lý, sẵn sàng post
├── music/                       # 🎵 Nhạc Việt trending (.mp3/.m4a)
├── logs/                        # Log files
├── main.py                      # CLI entry point
├── requirements.txt             # Dependencies
└── README.md                    # File này
```

---

## ⚙️ Cài đặt

### 1. Cài Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Cài Playwright browser

```bash
playwright install chromium
```

### 3. Cài FFmpeg (cần cho xử lý video)

- **Windows**: Tải từ [ffmpeg.org](https://ffmpeg.org/download.html) hoặc:
  ```bash
  choco install ffmpeg
  # hoặc
  winget install ffmpeg
  ```
- Đảm bảo `ffmpeg` có trong PATH.

---

## 🔑 Cấu hình Cookies (BẮT BUỘC)

### Cookies Douyin (để crawl video)

1. Mở Chrome, vào [douyin.com](https://www.douyin.com) và đăng nhập
2. Nhấn `F12` → tab `Application` → `Cookies` → `www.douyin.com`
3. Copy tất cả cookies vào file `config/cookies/douyin_cookies.txt`

**Format đơn giản** (mỗi dòng `key=value`):
```
sessionid=xxxxxxxx
sessionid_ss=xxxxxxxx
sid_guard=xxxxxxxx
passport_csrf_token=xxxxxxxx
```

**Hoặc format JSON**:
```json
[
  {"name": "sessionid", "value": "xxx"},
  {"name": "sessionid_ss", "value": "xxx"}
]
```

### Cookies TikTok (để upload video)

1. Mở Chrome, vào [tiktok.com](https://www.tiktok.com) và đăng nhập
2. Nhấn `F12` → tab `Console`, paste đoạn code sau:

```javascript
copy(JSON.stringify(document.cookie.split("; ").map(c => {
  const [name, ...v] = c.split("=");
  return {name, value: v.join("="), domain: ".tiktok.com", path: "/"};
})))
```

3. Paste kết quả vào file `config/cookies/tiktok_cookies.json`

---

## 🎵 Chuẩn bị Nhạc Việt

Bỏ file nhạc trending (.mp3 hoặc .m4a) vào thư mục `music/`:

```
music/
├── nhac-hot-1.mp3
├── nhac-trending-2.mp3
└── remix-viral.mp3
```

> **Gợi ý**: Tải nhạc trending từ TikTok VN, Zing MP3, NhacCuaTui. Tool sẽ random chọn nhạc cho mỗi video.

---

## 🚀 Sử dụng

### Crawl video từ Douyin

```bash
# Crawl từ URL video cụ thể
python main.py crawl --urls https://v.douyin.com/xxx https://v.douyin.com/yyy

# Crawl từ profile user Douyin (10 video mới nhất)
python main.py crawl --profile https://www.douyin.com/user/MS4wLjABxxxx --count 10

# Crawl từ file danh sách URLs
python main.py crawl --file urls.txt
```

### Xử lý video (Mirror + Text + Nhạc)

```bash
# Xử lý tất cả video đã download
python main.py process

# Xử lý với title cụ thể cho tất cả video
python main.py process --title "Nhảy đẹp quá 😍🔥"

# Giới hạn số video xử lý
python main.py process --limit 5
```

### Upload lên TikTok

```bash
# Upload video đã xử lý
python main.py post

# Giới hạn số video upload
python main.py post --limit 2
```

### Chạy tự động (Khuyến nghị)

```bash
# Chạy 1 lần: crawl → process → upload
python main.py auto --urls URL1 URL2 --once

# Chạy tự động theo lịch (24/7)
python main.py auto --file urls.txt

# URLs file format (mỗi dòng 1 URL):
# https://www.douyin.com/user/xxxx
# https://v.douyin.com/xxxx
```

### Xem trạng thái

```bash
python main.py status
python main.py status -v  # Chi tiết
```

---

## 🔄 Luồng hoạt động

```
1. CRAWL      → Tải video không watermark từ Douyin
                 ↓
2. PROCESS    → Mirror (lật ngang) video
               → Thay đổi speed nhẹ (0.97x - 1.03x)
               → Thêm text tiếng Việt overlay
               → Ghép nhạc Việt trending
               → Tăng brightness nhẹ
                 ↓
3. UPLOAD     → Mở TikTok qua Playwright
               → Đăng nhập bằng cookies
               → Upload video + caption + hashtags VN
               → Đợi 3-4 tiếng → Upload video tiếp theo
                 ↓
4. REPEAT     → Tự động lặp lại theo lịch
```

### Lịch mặc định (Auto mode)

| Giờ   | Hành động |
|-------|-----------|
| 09:00 | Crawl + Process + Post video #1 |
| 12:30 | Post video #2 |
| 18:00 | Post video #3 |
| 21:30 | Post video #4 |

> Có thể chỉnh trong `config/settings.py` → `SCHEDULER_CONFIG["post_times"]`

---

## ⚙️ Tùy chỉnh cấu hình

Chỉnh sửa file `config/settings.py`:

| Setting | Mô tả | Mặc định |
|---------|--------|----------|
| `TIKTOK_CONFIG.max_posts_per_day` | Số video post tối đa/ngày | 4 |
| `TIKTOK_CONFIG.post_interval_hours` | Khoảng cách giữa các lần post | 3-4 giờ |
| `TIKTOK_CONFIG.default_hashtags` | Hashtags mặc định | #fyp #xuhuong ... |
| `PROCESSOR_CONFIG.mirror` | Lật ngang video | True |
| `PROCESSOR_CONFIG.replace_audio` | Thay nhạc bằng nhạc Việt | True |
| `PROCESSOR_CONFIG.text_overlay.font_size` | Cỡ chữ overlay | 45 |
| `SCHEDULER_CONFIG.post_times` | Giờ post tự động | 09:00, 12:30, 18:00, 21:30 |

---

## ⚠️ Lưu ý quan trọng

1. **Cookies hết hạn**: Cookies Douyin/TikTok thường hết hạn sau 1-2 tuần. Cần cập nhật lại.
2. **Proxy Douyin**: Nếu crawl từ VN, có thể cần proxy Trung Quốc để ổn định.
3. **Giới hạn post**: Không post quá 4-5 video/ngày để tránh bị shadow ban.
4. **FFmpeg**: Cần cài FFmpeg để xử lý video (moviepy dependency).
5. **Nhạc**: Bỏ nhạc trending vào thư mục `music/` trước khi chạy process.
6. **TikTok UI changes**: Playwright automation có thể bị hỏng khi TikTok thay đổi giao diện. Cần cập nhật selectors.

---

## 🐛 Troubleshooting

| Lỗi | Nguyên nhân | Giải pháp |
|-----|-------------|-----------|
| `Cookies file not found` | Chưa cấu hình cookies | Xem phần "Cấu hình Cookies" |
| `Video download failed` | Cookies hết hạn hoặc bị block | Cập nhật cookies Douyin |
| `Not logged in` | Cookies TikTok hết hạn | Export lại cookies TikTok |
| `Cannot find file input` | TikTok thay đổi UI | Update selectors trong `tiktok_uploader.py` |
| `moviepy error` | Thiếu FFmpeg | Cài FFmpeg và thêm vào PATH |
| `Playwright error` | Chưa cài browser | Chạy `playwright install chromium` |

---

## 📊 Tips tăng Followers nhanh

1. **Post đều đặn**: 3-4 video/ngày, đúng giờ peak (9h, 12h30, 18h, 21h30)
2. **Nhạc trending**: Dùng nhạc đang hot trên TikTok VN
3. **Hashtags**: Luôn có #fyp #xuhuong #tiktokvietnam
4. **Text hook**: Title hấp dẫn, emoji bắt mắt
5. **Tương tác**: Like/comment video khác để tăng visibility
6. **Chất lượng**: Chọn video gốc chất lượng cao từ Douyin
