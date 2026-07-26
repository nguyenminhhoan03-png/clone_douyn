FROM python:3.10-slim

WORKDIR /app

# Cài đặt gcc, ffmpeg và các thư viện cần thiết
RUN apt-get update && apt-get install -y \
    gcc build-essential libffi-dev \
    ffmpeg \
    fonts-noto \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Cài đặt Playwright và Chromium
RUN playwright install chromium --with-deps

# Copy toàn bộ mã nguồn vào Docker
COPY . .

# Tạo thư mục database nếu chưa có
RUN mkdir -p database

# Expose port cho backend
EXPOSE 8000

# Mặc định chạy command nào đó (có thể ghi đè trong docker-compose)
CMD ["python", "main.py", "status"]
