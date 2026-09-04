# 📋 Danh sách các Lệnh (Commands) của Tool Auto Douyin / TikTok

Tài liệu này tổng hợp toàn bộ các câu lệnh cần thiết để chạy các tính năng của Tool. Có 2 cách chạy: **Chạy trực tiếp trên máy tính** và **Chạy trên VPS qua Docker**.

---

## Phần 1: Chạy lệnh trên VPS (Dùng Docker)
Do trên VPS hệ thống được chạy ngầm bằng `docker-compose`, mọi lệnh thao tác với bot bạn đều phải dùng cấu trúc `docker exec -it douyin_worker ...` để truyền lệnh vào bên trong container.

### 1. Xem trạng thái tổng quan
Xem bot đã cào bao nhiêu video, bao nhiêu chờ up, bao nhiêu thành công:
```bash
docker exec -it douyin_worker python main.py status
```
Xem chi tiết (kèm danh sách 10 video gần nhất):
```bash
docker exec -it douyin_worker python main.py status -v
```

### 2. Cào video (Crawl) thủ công
Nếu bạn không muốn bot tự động cào mà muốn chỉ định link:
```bash
# Cào từ 1 hoặc nhiều link cụ thể 
docker exec -it douyin_worker python main.py crawl --urls "link1" "link2"

# Cào 10 video mới nhất từ Profile 1 user
docker exec -it douyin_worker python main.py crawl --profile "link_profile" --count 10

# Cào từ danh sách link lưu trong file urls.txt
docker exec -it douyin_worker python main.py crawl --file urls.txt
```

### 3. Xử lý video (Process) thủ công
Xử lý các video vừa cào (chèn chữ, ghép nhạc, lật video...):
```bash
# Xử lý tất cả video đang chờ
docker exec -it douyin_worker python main.py process

# Xử lý và ép chung 1 dòng Caption cho tất cả video
docker exec -it douyin_worker python main.py process --title "Cre: Douyin. Video xịn quá!"
```

### 4. Upload video (Post) thủ công
```bash
# Up tất cả các video đã xử lý xong lên TikTok/YouTube
docker exec -it douyin_worker python main.py post

# Up giới hạn 2 video rồi nghỉ
docker exec -it douyin_worker python main.py post --limit 2
```

### 5. Khởi động chế độ AUTO (Chạy tự động ngầm 24/7)
Thực chất file `docker-compose.yml` của bạn đã được cấu hình mặc định chạy lệnh auto này rồi. Nhưng nếu bạn muốn test chạy 1 vòng chu trình (Crawl -> Process -> Post) rồi nghỉ thì dùng lệnh:
```bash
docker exec -it douyin_worker python main.py auto --once
```

---

## Phần 2: Các Lệnh Quản Lý VPS Cơ Bản

- **Xem log bot (xem bot đang báo lỗi hay đang up video):**
  ```bash
  docker logs -f douyin_worker
  ```
  *(Nhấn `Ctrl + C` để thoát màn hình xem log)*

- **Khởi động lại bot (Thường dùng sau khi vừa cập nhật Cookies/Code):**
  ```bash
  docker restart douyin_worker
  ```

- **Tắt hệ thống:**
  ```bash
  docker-compose down
  ```

- **Bật hệ thống & Cập nhật Code mới nhất:**
  ```bash
  git pull origin main
  docker-compose up -d --build
  ```

---

## Phần 3: Chạy trên Máy tính cá nhân (Local)
Nếu bạn không chạy Docker mà chạy trực tiếp code Python trên máy tính Windows/Mac:

1. Chạy giao diện cửa sổ (GUI):
   ```bash
   python gui.py
   ```
2. Chạy Terminal (CLI) - Các lệnh tương tự hệt như trên VPS nhưng không cần chữ `docker exec`:
   ```bash
   python main.py status
   python main.py crawl --urls "link"
   python main.py auto --once
   ```
