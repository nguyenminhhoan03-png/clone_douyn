# 📌 BÍ KÍP ĐỒNG BỘ VPS, PROXY & QUẢN LÝ CRONJOB

> [!CAUTION]
> ### 🛑 QUY TẮC BẤT KHẢ XÂM PHẠM CHO TẤT CẢ AI ASSISTANT (GEMINI / CLAUDE / CHATGPT / CURSOR):
> - **NGHIÊM CẤM TUYỆT ĐỐI** tự ý chạy các lệnh Git có thể làm mất code, rollback hoặc ghi đè thay đổi chưa commit của người dùng:
>   - ❌ **CẤM:** `git checkout -- <file>`, `git checkout .`, `git checkout -f`
>   - ❌ **CẤM:** `git restore .`, `git restore <file>`, `git restore --staged`
>   - ❌ **CẤM:** `git reset --hard`, `git reset --merge`
>   - ❌ **CẤM:** `git clean -fd`, `git clean -f`
>   - ❌ **CẤM:** `git stash drop`, `git stash pop` (khi không được yêu cầu)
> - **MỌI THAY ĐỔI TRONG CODE:** Phải sửa trực tiếp qua công cụ edit file (`replace_file_content` / `multi_replace_file_content`). Khi gặp lỗi hoặc xung đột, phải tìm đúng nguyên nhân để fix hoặc báo cáo người dùng, **KHÔNG ĐƯỢC TỰ TIỆN HOÀN TÁC / XÓA CODE CỦA NGƯỜI DÙNG.**

---

## 1. Đồng Bộ Database để Chống Đăng Trùng Video
Khi bạn chạy test bằng giao diện Tool trên máy tính, máy tính sẽ tự động ghi nhận những video nào đã đăng thành công vào `database/videos.db`.
Nếu bạn lên VPS đăng tiếp mà **KHÔNG chép file `videos.db` lên**, VPS sẽ tưởng là video đó chưa đăng và **đăng lại lần nữa gây ra trùng lặp (spam)**.

**Lệnh chép Database lên VPS (chạy trên PowerShell máy tính):**
```powershell
scp database/videos.db root@103.77.242.146:~/clone_douyn/database/videos.db
```

---

## 2. Cách Đồng Bộ Cookies & Proxies An Toàn & Chuẩn Xác Lên VPS

### ⚠️ Lưu ý về Nick TikTok:
- Tool trên máy tính chỉ lưu các file `tiktok_*.json` tương ứng với các nick đang hiển thị trên giao diện (tab Accounts).
- File `proxies.json` lưu cấu hình Proxy của từng nick.
- Code `batch_post.py` có bộ lọc thông minh: **Chỉ chạy các nick có trong `proxies.json`** (tự động loại trừ nick rác, nick cũ đã từng xóa).

### Lệnh đồng bộ (Chạy trên PowerShell máy tính):
```powershell
cd e:\Project_ItWebDev\Python\tiktok-upload-video

# Bắn toàn bộ Cookies (TikTok, Facebook, YouTube, Drive) & Proxy lên VPS:
scp config/cookies/admin_example_com/*.json root@103.77.242.146:~/clone_douyn/config/cookies/admin_example_com/
```

### Dọn dẹp nick rác cũ trên VPS (Nếu trước đây lỡ sync nick cũ/camoufox):
Chạy trên **Terminal VPS**:
```bash
rm -f ~/clone_douyn/config/cookies/admin_example_com/camoufox_*.json
```

---

## 3. Quản lý & Sửa Proxy Trực Tiếp Trên VPS

Nếu bạn muốn kiểm tra hoặc sửa proxy trực tiếp trên VPS mà không cần vào GUI:
```bash
nano ~/clone_douyn/config/cookies/admin_example_com/proxies.json
```
- Định dạng chuẩn:
  ```json
  {
    "tiktok_ancradai.json": "103.179.188.222:19683:2fp5:2fp5",
    "tiktok_charlesccg9zthomas.json": "103.179.188.222:28084:9ly8:9ly8"
  }
  ```
- Nhấn `Ctrl + O` $\rightarrow$ `Enter` để Lưu, nhấn `Ctrl + X` để Thoát.

---

## 4. Đăng Bài Tự Động Đa Nền Tảng (Multi-Platform Auto-Post)
Hệ thống hỗ trợ đăng tự động tuần tự cả 3 mạng: **TikTok $\rightarrow$ Facebook Reels $\rightarrow$ YouTube Shorts**.

### A. Lệnh chạy trực tiếp bằng tay trên VPS:
```bash
# 1. Đăng cho tất cả 3 nền tảng (Mỗi nick/page/kênh 2 video):
docker exec -it douyin_worker python batch_post.py --platform all

# 2. Hoặc chạy riêng từng nền tảng:
docker exec -it douyin_worker python batch_post.py --platform tiktok
docker exec -it douyin_worker python batch_post.py --platform facebook
docker exec -it douyin_worker python batch_post.py --platform youtube

# 3. Tùy chỉnh số lượng video mỗi tài khoản (mặc định là 2):
docker exec -it douyin_worker python batch_post.py --platform all --vids-per-acc 3
```

### B. Cài đặt Cronjob Giờ Vàng (Tự động 4 lần/ngày):
Mở crontab trên VPS: `crontab -e`
Dán đúng 1 dòng này vào:
```cron
# Tự động đăng cả 3 mạng vào các khung giờ vàng 9h, 12h, 18h, 21h:
0 9,12,18,21 * * * docker exec -i douyin_worker python batch_post.py --platform all >> /root/batch_post.log 2>&1
```

### C. Lệnh kiểm tra Log Đăng bài:
```bash
# Xem trực tiếp realtime:
tail -f /root/batch_post.log

# Xem 100 dòng gần nhất:
tail -n 100 /root/batch_post.log

# Làm sạch file log khi cần:
> /root/batch_post.log
```

---

## 5. Cơ Chế Chống Sập Đa Tầng (Fault Tolerance)
Hệ thống được bọc bảo vệ độc lập toàn diện:
1. **Cấp video:** Nếu 1 video bị lỗi mạng hoặc 404 trên Drive $\rightarrow$ Tự động dọn dẹp file rác $\rightarrow$ Nhảy sang video tiếp theo của nick đó!
2. **Cấp tài khoản:** Nếu 1 nick TikTok bị hỏng cookie/proxy $\rightarrow$ Tự đóng browser $\rightarrow$ Chuyển sang nick tiếp theo!
3. **Cấp nền tảng:** TikTok xong $\rightarrow$ Chuyển sang Facebook Reels $\rightarrow$ Facebook xong $\rightarrow$ Chuyển sang YouTube Shorts! Lỗi ở nền tảng nào sẽ tự ghi log và không làm ảnh hưởng các nền tảng còn lại.

---

## 6. Quản lý Cronjob Nuôi Nick Tự Động (Batch Farm)

```cron
# Nuôi nick tự động 2 luồng: 06:30 sáng và 17:00 chiều mỗi ngày
30 6 * * * docker exec douyin_worker python batch_farm.py --concurrency 2 >> /root/clone_douyn/logs/cron_farm.log 2>&1
0 17 * * * docker exec douyin_worker python batch_farm.py --concurrency 2 >> /root/clone_douyn/logs/cron_farm.log 2>&1
```

### Đảm bảo VPS chạy đúng Giờ Việt Nam:
```bash
timedatectl set-timezone Asia/Ho_Chi_Minh
systemctl restart cron
```
