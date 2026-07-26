# Hướng Dẫn Cài Đặt và Chạy Tool Auto Douyin/TikTok trên VPS

File `requirements.txt` đã được fix lỗi `audioop-lts` khi cài đặt trên Docker (Python 3.10). Dưới đây là các bước từ A-Z để bạn chạy full toàn bộ tool trên VPS.

## 1. Khởi động hệ thống (Build & Run)

Bây giờ bạn chỉ cần mang source code này lên VPS (bằng github hoặc upload file lên), sau đó mở terminal của VPS, vào thư mục code và chạy lệnh:

```bash
docker-compose up -d --build
```

Lệnh này sẽ tự động tải các gói cài đặt, cài `ffmpeg`, `playwright` (trình duyệt) và khởi động 2 containers:
- `douyin_backend`: Server API (chạy port 8000)
- `douyin_worker`: Tool chạy ngầm để lấy video và upload lên TikTok.

Để kiểm tra xem 2 container đã chạy thành công chưa:
```bash
docker ps
```

Để xem log của tool tự động chạy ngầm (xem nó có báo lỗi hay đang crawl cái gì không):
```bash
docker logs -f douyin_worker
```

## 2. Cách đăng nhập TikTok trên VPS (Bypass Login bằng Cookies)

VPS không có giao diện màn hình (GUI) nên bạn không thể mở trình duyệt lên để quét mã QR hay nhập mật khẩu. Cách duy nhất và an toàn nhất là **xuất Cookies từ máy tính cá nhân** rồi chép vào VPS.

### Bước 2.1: Lấy Cookies TikTok từ máy tính của bạn
1. Mở trình duyệt Chrome/Edge trên máy tính cá nhân.
2. Truy cập [https://www.tiktok.com/](https://www.tiktok.com/) và **đăng nhập vào tài khoản** của bạn.
3. Bấm phím **F12** (hoặc chuột phải chọn Inspect/Kiểm tra) để mở Developer Tools.
4. Chuyển sang tab **Console**.
5. Copy đoạn code dưới đây, dán vào thẻ Console và nhấn Enter:

```javascript
copy(JSON.stringify(document.cookie.split("; ").map(c => {
    const [name, ...v] = c.split("=");
    return {
        name: name.trim(), 
        value: v.join("=").trim(), 
        domain: ".tiktok.com", 
        path: "/"
    };
})))
```
> Lúc này toàn bộ dữ liệu Cookies dạng JSON đã được lưu vào bộ nhớ tạm (Clipboard) của bạn.

### Bước 2.2: Chép Cookies vào VPS
1. Trên VPS, bạn mở (hoặc tạo) file theo đúng đường dẫn: `config/cookies/tiktok_cookies.json`
   *(Nếu chưa có thư mục `cookies` trong `config` thì bạn hãy tạo nó: `mkdir -p config/cookies`)*.
2. Dán toàn bộ nội dung vừa copy được vào file `tiktok_cookies.json` và lưu lại.

Ví dụ lệnh nhanh trên VPS:
```bash
nano config/cookies/tiktok_cookies.json
# Dán cookies vào, nhấn Ctrl+X, Y, Enter để lưu.
```

### Bước 2.3: Khởi động lại Bot
Sau khi có file cookies, bạn chỉ cần khởi động lại container worker để bot nhận diện phiên đăng nhập mới:
```bash
docker restart douyin_worker
```

Bạn có thể check log lại xem bot đã báo `Loaded XX TikTok cookies` chưa:
```bash
docker logs -f douyin_worker
```

## 3. Các Lệnh Quản Lý Khác

- **Dừng toàn bộ hệ thống:**
  ```bash
  docker-compose down
  ```
- **Xóa sạch dữ liệu (Cẩn thận):**
  Nếu bạn muốn xóa cả volume database thì dùng:
  ```bash
  docker-compose down -v
  ```
- **Chui vào bên trong container worker để gõ lệnh thủ công (như `python main.py status`):**
  ```bash
  docker exec -it douyin_worker bash
  # Sau khi vào được thì chạy thử:
  python main.py status
  ```

> **Lưu ý cuối:** Nhạc nền bạn hãy upload thẳng vào thư mục `music/` trên VPS. Folder này đã được đồng bộ vào trong docker. Thư mục `database/` cũng vậy, sqlite database được ánh xạ ra ngoài nên dù bạn xóa container thì danh sách video đã up cũng không bị mất.
