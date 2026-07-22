FROM python:3.14.5-slim

WORKDIR /app

# Cài đặt ffmpeg (để xử lý video) và các font chữ (để chèn text tiếng Việt/Trung)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    fonts-noto \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Cài đặt thư viện Python
RUN pip install --no-cache-dir -r requirements.txt

# Cài đặt Chromium và các thư viện cần thiết cho Playwright (để tự động upload)
RUN playwright install chromium --with-deps

COPY . .

# Chạy bằng giao diện dòng lệnh (CLI) vì VPS không có màn hình GUI
CMD ["python", "main.py", "status"]
