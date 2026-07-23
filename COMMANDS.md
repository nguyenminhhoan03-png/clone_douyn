# 📋 Danh sách các Lệnh (Commands) của Project DouyinBot

Tài liệu này tổng hợp toàn bộ các câu lệnh cần thiết để chạy, cấu hình và triển khai dự án DouyinBot từ máy tính cá nhân (Local) cho đến máy chủ (VPS).

---

## 1. Môi trường Local (Máy tính cá nhân - Windows/Mac)

### 1.1 Cài đặt ban đầu
```bash
# Cài đặt các thư viện Python cần thiết
pip install -r requirements.txt

# Cài đặt trình duyệt Chromium cho Playwright (dùng để auto upload)
playwright install chromium --with-deps
```

### 1.2 Chạy giao diện (GUI)
Nếu bạn muốn dùng tool bằng giao diện trực quan:
```bash
python gui.py
```

### 1.3 Các lệnh CLI (Dòng lệnh) với `main.py`
Nếu không dùng GUI, bạn có thể chạy bằng dòng lệnh:

**1.3.1 Xem trạng thái hệ thống:**
```bash
# Xem trạng thái chung
python main.py status

# Xem chi tiết cấu hình, số lượng video...
python main.py status -v
```

**1.3.2 Chức năng Crawl (Tải video):**
```bash
# Tải từ 1 hoặc nhiều link URL cụ thể
python main.py crawl --urls https://v.douyin.com/xxx https://v.douyin.com/yyy

# Tải 10 video mới nhất từ Profile của 1 user
python main.py crawl --profile https://www.douyin.com/user/MS4wLjABxxxx --count 10

# Tải video từ danh sách link lưu trong file txt
python main.py crawl --file urls.txt
```

**1.3.3 Chức năng Process (Xử lý, lật, ghép nhạc, chèn text):**
```bash
# Xử lý tất cả video trong thư mục downloads
python main.py process

# Xử lý giới hạn 5 video
python main.py process --limit 5

# Xử lý và set caption chung cho tất cả video
python main.py process --title "Nhảy đẹp quá 😍🔥"
```

**1.3.4 Chức năng Upload (Đăng lên TikTok):**
```bash
# Đăng tất cả video đã xử lý (nằm trong thư mục processed)
python main.py post

# Đăng giới hạn 2 video
python main.py post --limit 2
```

**1.3.5 Chức năng Auto (Chạy tự động toàn bộ quy trình):**
```bash
# Chạy 1 lần duy nhất: Crawl -> Process -> Upload
python main.py auto --urls URL1 URL2 --once

# Chạy tự động lặp lại theo lịch (treo tool)
python main.py auto --file urls.txt
```

---

## 2. Môi trường Máy chủ (VPS - Linux) chạy bằng Docker

### 2.1 Clone code và Build Image
```bash
# Clone code từ Github về
git clone https://github.com/nguyenminhhoan03-png/clone_douyn.git

# Di chuyển vào thư mục project
cd clone_douyn

# Build Docker Image với tên là clone-douyn (Lưu ý có dấu chấm . ở cuối)
docker build -t clone-douyn .
```

### 2.2 Chạy Container (Deploy)
Lệnh này sẽ chạy project ngầm trên VPS và map các thư mục dữ liệu ra ngoài để không bị mất khi khởi động lại:
```bash
docker run -d \
  --name clone_douyn_app \
  --restart unless-stopped \
  -v $(pwd)/database:/app/database \
  -v $(pwd)/downloads:/app/downloads \
  -v $(pwd)/processed:/app/processed \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/config:/app/config \
  clone-douyn
```

### 2.3 Các lệnh quản lý Docker Container
```bash
# Xem danh sách các container đang chạy
docker ps

# Xem log hoạt động của tool (để biết tool đang tải hay đăng video nào)
docker logs -f clone_douyn_app

# Khởi động lại tool
docker restart clone_douyn_app

# Dừng tool
docker stop clone_douyn_app

# Bật lại tool
docker start clone_douyn_app

# Xoá container (không xoá data vì đã map volume)
docker rm -f clone_douyn_app
```

### 2.4 Chạy lệnh CLI trong Container
Nếu bạn muốn dùng các lệnh CLI ở mục 1.3 ngay trên VPS:
```bash
# Cấu trúc: docker exec -it <tên_container> <lệnh_python>
docker exec -it clone_douyn_app python main.py status
docker exec -it clone_douyn_app python main.py crawl --file urls.txt
```

---

## 3. Các lệnh Git cơ bản để cập nhật Code
Khi bạn có thay đổi ở máy tính cá nhân (ví dụ: sửa code, thêm cấu hình):

**Trên máy tính (Push code):**
```bash
git add .
git commit -m "Update code"
git push origin main
```

**Trên VPS (Kéo code mới và Deploy lại):**
```bash
# Di chuyển vào thư mục code
cd clone_douyn

# Kéo code mới nhất về
git pull origin main

# Build lại Image
docker build -t clone-douyn .

# Xoá container cũ đi
docker rm -f clone_douyn_app

# Chạy lại container với lệnh Run ở mục 2.2
docker run -d \
  --name clone_douyn_app \
  --restart unless-stopped \
  -v $(pwd)/database:/app/database \
  -v $(pwd)/downloads:/app/downloads \
  -v $(pwd)/processed:/app/processed \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/config:/app/config \
  clone-douyn
```
