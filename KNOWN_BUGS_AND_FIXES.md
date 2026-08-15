# TIKTOK AUTO-UPLOADER - KNOWN BUGS & FIXES

Tài liệu này tổng hợp lại toàn bộ những lỗi (bugs) hóc búa, các edge-cases và cách giải quyết (Architecture Decisions) trong quá trình phát triển tool TikTok Auto-Uploader (đặc biệt là phần Livestream Seeder và Quản lý Tài khoản).
Đọc kỹ tài liệu này trước khi code tính năng mới để tránh lặp lại lỗi cũ (regression bugs).

---

## 1. Lỗi Treo Trình Duyệt (Timeout `new_page()`) với Camoufox trên Windows
- **Vấn đề**: Khi khởi chạy Camoufox (Firefox) thông qua Playwright trên môi trường Windows, đặc biệt là khi mở nhiều luồng (multiprocessing/threading) cùng lúc, tiến trình Render của trình duyệt hay bị kẹt (hang), dẫn đến lỗi `TimeoutError` khi gọi `await context.new_page()`.
- **Nguyên nhân**: Xung đột của chế độ Content Sandbox trên Windows đối với engine Firefox tuỳ chỉnh.
- **Giải pháp**: Bắt buộc phải **tắt Content Sandbox** bằng biến môi trường trước khi launch Camoufox.
- **Code áp dụng**:
  ```python
  import os
  custom_env = os.environ.copy()
  custom_env["MOZ_DISABLE_CONTENT_SANDBOX"] = "1"
  camoufox_args = {"env": custom_env, ...}
  ```
  *(Lưu ý: Mặc dù tắt Sandbox làm giảm bảo mật, nhưng đây là bắt buộc để Camoufox không bị crash trên Windows khi chạy đa luồng).*

## 2. Lỗi `407 Proxy Authentication Required` (Lỗi do ký tự `@` trong mật khẩu)
- **Vấn đề**: Khi sử dụng Proxy có chứa ký tự `@` trong mật khẩu (VD: `Hoanphe1@`), Camoufox văng lỗi 407 ngay trước khi trình duyệt kịp mở lên.
- **Nguyên nhân**: Thuộc tính `geoip=True` của Camoufox sử dụng thư viện `requests` của Python ở bên dưới để lấy thông tin toạ độ IP. Thư viện `requests` bị "ngu" khi parse URL Proxy dạng `http://user:pass@ip:port` nếu mật khẩu có chứa chữ `@`. Nó sẽ nhận diện sai điểm phân tách, gửi sai thông tin đăng nhập lên server Proxy.
- **Giải pháp**: **Vô hiệu hoá `geoip=False`** khi khởi tạo Camoufox. Playwright tự quản lý Proxy cực kỳ tốt và không bị lỗi parse chữ `@` này.
- **Code áp dụng**:
  ```python
  camoufox_args = {
      "headless": False,
      "geoip": False, # Bắt buộc False để tránh lỗi parse chữ @ trong mật khẩu Proxy
      ...
  }
  ```

## 3. Lỗi TikTok quét Bot & Đá văng khỏi Livestream (Cookie Cross-Contamination)
- **Vấn đề**: Tài khoản xem Livestream bị TikTok phát hiện là Bot và sút văng ra trang chủ ngay khi vào phòng Live.
- **Nguyên nhân**: Tool trước đây dùng chung 1 file Cookie (VD: `tiktok_acc.json`) cho cả Chromium (chạy Farm) và Camoufox (chạy Seeding). TikTok cực kỳ nhạy cảm với việc thay đổi Engine Trình duyệt. Việc dùng Cookie của Chrome nhét vào Firefox khiến hệ thống Anti-bot của TikTok kích hoạt.
- **Giải pháp (Senior++ Architecture)**: 
  - Tách biệt hoàn toàn Cookie Storage: 
    - Cookie đăng nhập bằng Chrome (Farm) lưu vào `tiktok_{acc}.json`.
    - Cookie đăng nhập bằng Camoufox (Livestream) lưu vào `camoufox_{acc}.json`.
  - Thiết kế UI (Trong `gui.py`) hiển thị nút Login độc lập trực tiếp tại Tab Farm và Tab Livestream để người dùng không bị nhầm lẫn.

## 4. Lỗi Race Condition `name '_camoufox_init_lock' is not defined`
- **Vấn đề**: Khi bấm Start Seeding với nhiều tài khoản, Playwright báo lỗi thiếu Lock.
- **Nguyên nhân**: Hàm khởi tạo bất đồng bộ của Playwright/Camoufox bị đụng độ tài nguyên khi chạy trên đa luồng (Multi-threading + Asyncio).
- **Giải pháp**: Định nghĩa biến Global `_camoufox_init_lock = asyncio.Lock()` ở cấp module (đầu file `livestream_seeder.py`) và dùng `async with _camoufox_init_lock:` để ép việc khởi động trình duyệt chạy tuần tự.

## 5. Lỗi Scope Biến (UnboundLocalError) trong Tkinter/Python
- **Vấn đề**: Báo lỗi `UnboundLocalError: cannot access local variable 'SUCCESS' where it is not associated with a value` khi render giao diện Tab.
- **Nguyên nhân**: Do thói quen import thư viện ở giữa hàm (`import json`, `from config.settings import SUCCESS`). Python phân tích (compile) các biến local ở mức độ toàn hàm. Nếu biến trùng tên với global (ở đầu file đã có `SUCCESS = "#xxx"`) thì Python coi nó là biến local và gây lỗi nếu gọi biến đó trước dòng import.
- **Giải pháp**: 
  - Dọn dẹp các dòng `import` rác.
  - Luôn luôn đặt `import` ở đầu file hoặc đầu hàm. Không đặt xen kẽ giữa các vòng lặp tạo UI (`for acc in accounts:`).

---
*Lưu ý cho AI Assistant: Luôn đọc file này trước khi propose các thay đổi kiến trúc hoặc debug các lỗi liên quan đến Playwright/Camoufox.*
