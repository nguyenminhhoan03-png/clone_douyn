# 📘 HƯỚNG DẪN CẤU HÌNH & THÊM TÀI KHOẢN FACEBOOK REELS

Tài liệu này hướng dẫn chi tiết từ A - Z cách cấu hình Fanpage, lấy mã Token chuẩn từ Meta và kết nối vào hệ thống **DouyinBot** để tự động upload video lên **Facebook Reels**.

---

## 1. Tổng quan cơ chế hoạt động

- Hệ thống sử dụng **Facebook Graph API (v19.0+)** để đăng trực tiếp video lên Facebook Reels mà không cần mở trình duyệt, giúp tốc độ nhanh, ổn định và không chiếm chuột/màn hình.
- Để đăng video lên một Fanpage, Meta yêu cầu **Page Access Token** có các quyền bắt buộc:
  - `pages_manage_posts` (Quyền đăng bài & video lên Trang)
  - `publish_video` (Quyền tải lên tệp video)
  - `pages_show_list` (Quyền xem danh sách Trang)
  - `pages_read_engagement` (Quyền đọc tương tác)

---

## 2. Cách lấy Page Access Token chuẩn từ Meta for Developers

Đây là phương pháp **chuẩn và khuyên dùng nhất** vì Token hoạt động ổn định và lâu dài.

### Bước 1: Bật quyền `pages_manage_posts` trong Meta App
1. Truy cập [Meta for Developers](https://developers.facebook.com/apps/) $\rightarrow$ Chọn App của bạn (Ví dụ: `nmh03`).
2. Vào mục **Use cases** (hoặc truy cập link: `https://developers.facebook.com/apps/<APP_ID>/use-cases/`).
3. Tại Use case **Manage everything on your Page** (hoặc *Content management*), bấm **Customize** (hoặc **Add**).
4. Tìm và bấm **Add** cạnh quyền **`pages_manage_posts`**.

---

### Bước 2: Sinh Token trên Graph API Explorer
1. Truy cập công cụ [Facebook Graph API Explorer](https://developers.facebook.com/tools/explorer/).
2. Ở cột bên phải:
   - **Meta App**: Chọn App của bạn.
   - **User or Page**: Chọn **`User Token`**.
3. Ở mục **Permissions**, bấm **Add a Permission** $\rightarrow$ Chọn danh mục **Events Groups Pages** $\rightarrow$ Tích chọn:
   - ✅ `pages_manage_posts`
   - ✅ `publish_video`
   - ✅ `pages_show_list`
   - ✅ `pages_read_engagement`
4. Bấm nút xanh **`Generate Access Token`** $\rightarrow$ Facebook sẽ hiện cửa sổ pop-up hỏi quyền $\rightarrow$ Bấm **Tiếp tục / Cho phép tất cả**.

---

### Bước 3: Lấy Token riêng của Page
1. Ở thanh địa chỉ truy vấn ở giữa màn hình, nhập:
   ```text
   me/accounts?fields=id,name,access_token,tasks
   ```
2. Bấm nút **`Submit`** màu xanh.
3. Trong khung kết quả JSON trả về, tìm đúng Fanpage của bạn:
   - **`id`**: ID của Fanpage (Ví dụ: `1348394841683090`).
   - **`name`**: Tên Fanpage (Ví dụ: `Lướt Là Nghiện`).
   - **`access_token`**: Chuỗi token riêng của Page (Bắt đầu bằng `EAAt...` hoặc `EAA...`).

> **Tính năng tự động thông minh của Tool**: Kể cả khi bạn lỡ copy nhầm User Token (ở ô Access Token phía trên), Tool vẫn có thể tự động gọi `/me/accounts` để đổi sang đúng Page Access Token cho bạn!

---

## 3. Cách thêm và quản lý Fanpage trong Giao diện Tool

### Thêm Fanpage mới:
1. Mở phần mềm $\rightarrow$ Vào tab **👥 Accounts (Quản lý tài khoản)** $\rightarrow$ Chọn tab con **Facebook**.
2. Điền thông tin:
   - **Page ID**: Nhập ID Fanpage (Ví dụ: `1348394841683090`).
   - **Tên gợi nhớ**: Tùy chọn đặt tên nhận diện (Ví dụ: `Page Gái Xinh`, `Lướt là nghiện`).
   - **Access Token**: Dán mã Token (hoặc Cookie) vào ô.
3. Bấm **🔍 Kiểm tra & Thêm** $\rightarrow$ Hệ thống sẽ xác thực và lưu vào file `facebook_1.json` trong thư mục `config/cookies/<username>/`.

### Sửa / Cập nhật Token khi hết hạn:
1. Trong danh sách Fanpage, bấm nút **✏️ Sửa** trên thẻ Fanpage cần đổi Token.
2. Form bên dưới sẽ tự động nạp thông tin cũ $\rightarrow$ Dán Token mới vào ô **Access Token**.
3. Bấm nút **💾 Lưu Thay Đổi** (hoặc bấm **❌ Hủy Sửa** nếu không muốn cập nhật).

---

## 4. Cách chọn Fanpage để Upload Video

1. Vào tab **📤 Upload**.
2. Trên mỗi thẻ Video đã qua xử lý, có thanh **Dedicated Platform Bar**:
   - 🎵 **TikTok**: `[ Không up ▾ ]`
   - 🎬 **YouTube**: `[ Không up ▾ ]`
   - 📘 **Facebook**: Chọn tài khoản Fanpage cần đăng (Ví dụ: `facebook_1.json` hoặc `Lướt là nghiện`).
3. Nếu video nào **không muốn đăng lên Facebook**, bạn chỉ cần chọn `Không up` hoặc gạt tắt công tắc **Facebook** ở cột cấu hình bên phải.
4. Bấm nút **▶ Bắt đầu Upload**.

---

## 5. Xử lý các lỗi thường gặp (Troubleshooting)

### 🔴 Lỗi `OAuthException (Code 1 / 190) - Invalid request / Session expired`
- **Nguyên nhân**: Token Facebook đã hết hạn hoặc phiên đăng nhập tài khoản trên trình duyệt đã bị đăng xuất / đổi mật khẩu.
- **Xử lý**: Vào tab **Accounts $\rightarrow$ Facebook**, bấm nút **✏️ Sửa** và dán Token mới.

### 🔴 Lỗi `OAuthException (Code 200) - Lack of pages_manage_posts permission`
- **Nguyên nhân**: Token chưa được cấp quyền quản lý bài viết của Trang (`pages_manage_posts`).
- **Xử lý**: Làm theo **Bước 1 & Bước 2** ở Mục 2 của tài liệu này để bật quyền `pages_manage_posts` trong App Dashboard và sinh lại Token.

### 🔴 Lỗi `Invalid Scopes: manage_pages`
- **Nguyên nhân**: Quyền cũ `manage_pages` đã bị Meta khai tử và thay thế bằng `pages_manage_posts` & `pages_show_list`.
- **Xử lý**: Chỉ sử dụng các quyền mới như đã liệt kê ở Mục 2.
