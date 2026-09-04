# 📚 TÀI LIỆU HƯỚNG DẪN & FULL LỆNH DOCKER (DOUYIN & TIKTOK BOT)

Tài liệu này tổng hợp toàn bộ các câu lệnh quản lý, vận hành và tự động hóa hệ thống trên VPS bằng **Docker / Docker Compose**.

---

## 📑 MỤC LỤC
1. [Quản lý Container (Khởi động, Build, Dừng, Xem Log)](#1-quản-lý-container-docker)
2. [Đồng bộ Dữ liệu từ Máy tính lên VPS (SCP)](#2-đồng-bộ-dữ-liệu-máy-tính--vps-scp)
3. [Lệnh Tự Động Hóa (Full Pipeline)](#3-lệnh-tự-động-hóa-full-pipeline)
4. [Lệnh Crawl Video Douyin (Profile & Video URLs)](#4-lệnh-crawl-video-douyin)
5. [Lệnh Xử lý & Render Video (Processor)](#5-lệnh-xử-lý--render-video)
6. [Lệnh Upload Video (TikTok & YouTube Shorts)](#6-lệnh-upload-video-lên-mạng-xã-hội)
7. [Kiểm tra Thống kê & Trạng thái Hệ thống](#7-kiểm-tra-thống-kê--trạng-thái-hệ-thống)
8. [Cấu hình Proxy & Đa Tài Khoản](#8-cấu-hình-proxy--đa-tài-khoản)
9. [Xử lý Sự Cố Thường Gặp (Troubleshooting)](#9-xử-lý-sự-cố-thường-gặp)

---

## 1. Quản lý Container Docker

### Khởi động & Build lại hệ thống:
```bash
# Build lại image và chạy ngầm (Khuyên dùng khi vừa git pull code mới)
docker compose up -d --build

# Khởi động lại các container đang chạy
docker compose up -d
```

### Xem trạng thái các container:
```bash
docker ps
```

### Khởi động lại từng Container:
```bash
# Khởi động lại Worker (Bot Auto Crawl & Post)
docker restart douyin_worker
# Hoặc: docker compose restart worker

# Khởi động lại Backend API
docker restart douyin_backend
# Hoặc: docker compose restart backend
```

### Xem Live Logs (Nhật ký hoạt động thời gian thực):
```bash
# Xem log Bot Worker (Xem đang cào, render hay upload cái gì)
docker logs -f douyin_worker

# Xem log Backend API
docker logs -f douyin_backend

# Xem 100 dòng log gần nhất
docker logs --tail 100 douyin_worker
```
> *(Nhấn `Ctrl + C` để thoát màn hình xem log mà không làm gián đoạn bot)*

### Dừng & Xóa Container:
```bash
# Dừng toàn bộ hệ thống
docker compose down

# Dừng và xóa luôn toàn bộ container cũ
docker compose down --remove-orphans
```

---

## 2. Đồng bộ Dữ liệu Máy tính ➜ VPS (SCP)

*Chạy các lệnh này trên **PowerShell / Terminal máy tính cá nhân** của bạn:*

```powershell
# Chuyển vào thư mục dự án trên máy
cd e:\Project_ItWebDev\Python\tiktok-upload-video

# 1. Bắn toàn bộ thư mục config (gồm Cookie TikTok, Cookie Douyin, Client Secret, Proxies)
scp -r config root@103.77.242.146:~/clone_douyn/

# 2. Bắn file cấu hình môi trường .env
scp .env root@103.77.242.146:~/clone_douyn/.env

# 3. Bắn file danh sách link urls.txt
scp urls.txt root@103.77.242.146:~/clone_douyn/urls.txt

# 4. Bắn toàn bộ file nhạc trong thư mục music/
scp music/* root@103.77.242.146:~/clone_douyn/music/

# 5. Bắn riêng lẻ 1 file cookie TikTok cụ thể
scp config/cookies/tiktok_1.json root@103.77.242.146:~/clone_douyn/config/cookies/
```

---

## 3. Lệnh Tự Động Hóa (Full Pipeline)

Bot tự động thực hiện trọn gói chu trình: **Crawl ➔ Xử lý Render ➔ Upload TikTok/YouTube**.

### A. Chạy 1 chu trình ngay lập tức (Test tức thì không cần chờ lịch):
```bash
# Chạy chu trình với danh sách link trong file urls.txt
docker exec -it douyin_worker python main.py auto --file urls.txt --once

# Chạy chu trình với các link chỉ định trực tiếp
docker exec -it douyin_worker python main.py auto --urls "https://v.douyin.com/xxx/" --once
```

### B. Chế độ Chạy Ngầm 24/7 theo Lịch (Đã mặc định bật trong Container):
Mặc định `douyin_worker` sẽ tự động chạy:
- **Crawl định kỳ:** Mỗi 12 tiếng một lần.
- **Upload video:** Vào 4 khung giờ vàng mỗi ngày: **`09:00`**, **`12:30`**, **`18:00`**, **`21:30`** (Múi giờ `Asia/Ho_Chi_Minh`).

---

## 4. Lệnh Crawl Video Douyin

Nếu muốn ra lệnh cho bot cào video thủ công mà chưa cần đăng ngay:

### Cào toàn bộ video từ Profile Douyin của một Creator:
```bash
# Cào 10 video mới nhất của user
docker exec -it douyin_worker python main.py crawl --profile "https://www.douyin.com/user/MS4wLjABAAAA..." --count 10

# Cào 20 video mới nhất của user
docker exec -it douyin_worker python main.py crawl --profile "https://www.douyin.com/user/MS4wLjABAAAA..." --count 20
```

### Cào video từ file danh sách `urls.txt`:
```bash
docker exec -it douyin_worker python main.py crawl --file urls.txt
```

### Cào 1 hoặc nhiều link video cụ thể:
```bash
docker exec -it douyin_worker python main.py crawl --urls "https://v.douyin.com/abc/" "https://v.douyin.com/xyz/"
```

---

## 5. Lệnh Xử lý & Render Video

Render video để chống vi phạm bản quyền: Lật ngang (Mirror), tăng tốc nhẹ, tăng sáng, ghép nhạc Việt từ `music/`, tạo sub AI / thuyết minh AI.

```bash
# Xử lý toàn bộ video vừa crawl đang ở trạng thái chờ
docker exec -it douyin_worker python main.py process

# Xử lý giới hạn tối đa 5 video
docker exec -it douyin_worker python main.py process --limit 5

# Xử lý video và gắn kèm Title / Caption tiếng Việt cố định
docker exec -it douyin_worker python main.py process --title "Cre: Douyin. Nhảy đỉnh quá các bạn ơi! 😍"
```

---

## 6. Lệnh Upload Video Lên Mạng Xã Hội

Bot sử dụng Playwright (chế độ Headless) kết hợp Cookie & Proxy để tải video lên kênh.

```bash
# Upload 1 video đã xử lý lên TikTok
docker exec -it douyin_worker python main.py post --limit 1

# Upload tối đa 3 video
docker exec -it douyin_worker python main.py post --limit 3
```

---

## 7. Kiểm tra Thống kê & Trạng thái Hệ thống

```bash
# Xem bảng tổng quan (Số video đã cào, đã render, đã post)
docker exec -it douyin_worker python main.py status

# Xem chi tiết danh sách 10 video gần nhất kèm trạng thái
docker exec -it douyin_worker python main.py status -v
```

### Truy cập trực tiếp vào bên trong Container (Bash Terminal):
```bash
docker exec -it douyin_worker bash

# Khi đã ở bên trong container, bạn gõ lệnh trực tiếp:
python main.py status -v
python main.py auto --file urls.txt --once

# Thoát ra ngoài VPS:
exit
```

---

## 8. Cấu hình Proxy & Đa Tài Khoản

### Gán Proxy riêng cho từng Nick TikTok:
Tạo file `config/cookies/proxies.json` trên VPS:
```json
{
  "tiktok_1.json": "http://user:pass@103.77.242.10:8080",
  "tiktok_2.json": "http://103.77.242.11:8080",
  "tiktok_cookies.json": "socks5://103.77.242.12:1080"
}
```

### Gán Proxy cho Douyin Crawler (Nếu cần vượt chặn IP):
Thêm vào file `.env`:
```env
DOUYIN_PROXY=http://user:pass@ip:port
```

---

## 9. Xử lý Sự Cố Thường Gặp

| Vấn đề | Nguyên nhân | Cách khắc phục |
| :--- | :--- | :--- |
| **`No such file: tiktok_cookies.json`** | Chưa có file cookie đúng tên | Dùng lệnh `scp -r config/cookies root@VPS:...` để bắn đủ cookie lên VPS. |
| **`Fresh cookies are needed`** | Video Douyin bị ẩn/xóa hoặc hết hạn cookie Douyin | Cập nhật lại file `douyin_cookies.txt` hoặc đổi link video/profile khác trong `urls.txt`. |
| **`Chưa có nhạc Việt trong thư mục`** | Thư mục `music/` đang trống | Bắn file `.mp3`/`.m4a` vào thư mục `music/` bằng SCP. |
| **`no such service: douyin_worker`** | Nhầm tên service và container | Dùng `docker restart douyin_worker` hoặc `docker compose restart worker`. |
| **`Command 'docker-compose' not found`** | Bản Docker mới dùng lệnh cách | Dùng `docker compose` (có dấu cách) thay vì gạch nối `-`. |
