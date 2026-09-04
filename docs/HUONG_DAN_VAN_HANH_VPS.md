# 📘 HƯỚNG DẪN VẬN HÀNH TOÀN DIỆN (LOCAL + VPS)

## 🌟 1. Mô Hình Vận Hành Chuẩn
- **Máy tính cá nhân (Local):** 
  - Crawl Douyin, Xử lý Render (Sub AI, Nhạc Việt, Lật video...) ➔ Tự động đẩy lên Google Drive.
  - Quản lý Tài khoản (Thêm nick, gán Proxy) & Tạo Kịch bản Nuôi Nick (Flow Builder).
- **VPS (Server 24/7):** 
  - Chạy ẩn hoàn toàn (Headless mode).
  - Tự động Đăng bài theo lịch hẹn.
  - Tự động Farm / Nuôi nick theo Kịch bản đã sync từ máy tính (2 nick song song).

---

## 🚀 2. Quy Trình Đồng Bộ Dữ Liệu (Local ➜ VPS)

### A. Đồng bộ Kịch bản Nuôi Nick (config/flows.json):
Mỗi khi bạn tạo hoặc sửa kịch bản nuôi nick trong GUI dưới máy tính, chỉ cần bắn file này lên VPS:
```powershell
scp config/flows.json root@103.77.242.146:~/clone_douyn/config/
```

### B. Đồng bộ file `batch_farm.py` (Script Nuôi nick đa tài khoản):
```powershell
scp batch_farm.py root@103.77.242.146:~/clone_douyn/
```

### C. Đồng bộ Database & Cookies:
```powershell
# Bắn database (khi có mẻ video mới cần post):
scp -r database root@103.77.242.146:~/clone_douyn/

# Bắn Cookies & Proxy (khi thêm nick mới):
Compress-Archive -Path "config/cookies/admin_example_com/*.json" -DestinationPath "cookies.zip" -Force
scp cookies.zip root@103.77.242.146:~/clone_douyn/
```
*(Trên VPS giải nén: `unzip -o ~/clone_douyn/cookies.zip -d ~/clone_douyn/config/cookies/admin_example_com/`)*

---

## 🌾 3. Lệnh Chạy Farm / Nuôi Nick Trên VPS (Headless - 2 Nick Song Song)

### Cách 1: Chạy ngay lập tức (2 nick cùng lúc):
```bash
docker exec -it douyin_worker python batch_farm.py --concurrency 2
```

### Cách 2: Chọn cụ thể Kịch bản muốn chạy:
```bash
docker exec -it douyin_worker python batch_farm.py --concurrency 2 --flow "Mặc định (Lướt xu hướng 15p)"
```

### Cách 3: Hẹn giờ tự động Farm hàng ngày (Crontab trên VPS):
Mở crontab: `crontab -e` và thêm lịch:
```cron
# Tự động Farm nick lúc 14:00 chiều mỗi ngày (2 luồng song song)
0 14 * * * docker exec douyin_worker python batch_farm.py --concurrency 2 >> /root/clone_douyn/logs/cron_farm.log 2>&1
```

---

## ⚡ 4. Lệnh Đăng Bài Tự Động Đa Nền Tảng (TikTok + Facebook + YouTube)

### A. Chạy bằng tay ngay lập tức:
```bash
# Đăng cả 3 nền tảng (TikTok -> Facebook Reels -> YouTube Shorts):
docker exec -it douyin_worker python batch_post.py --platform all

# Hoặc chạy riêng từng nền tảng:
docker exec -it douyin_worker python batch_post.py --platform tiktok
docker exec -it douyin_worker python batch_post.py --platform facebook
docker exec -it douyin_worker python batch_post.py --platform youtube
```

### B. Hẹn giờ tự động 4 khung giờ vàng (Crontab trên VPS):
Mở `crontab -e` và thêm dòng:
```cron
# Tự động đăng cả 3 mạng lúc 9h, 12h, 18h, 21h hàng ngày:
0 9,12,18,21 * * * docker exec -i douyin_worker python batch_post.py --platform all >> /root/batch_post.log 2>&1
```

### C. Xem log đăng bài:
```bash
tail -f /root/batch_post.log
```

---

## 💡 5. Tối Ưu Cho VPS 2 Core - 2GB RAM
Chạy 4 lệnh này trên VPS để bật 2GB RAM ảo (Swap), đảm bảo treo Farm nhiều tiếng không lo tràn RAM:
```bash
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' | tee -a /etc/fstab
```
