# 🛑 QUY TẮC BẮT BUỘC CHO TẤT CẢ AI ASSISTANT (GEMINI / ANTIGRAVITY / CLAUDE / CURSOR)

## 1. QUY TẮC BẢO TOÀN MÃ NGUỒN (CRITICAL - DO NOT OVERWRITE CODE)

**NGHIÊM CẤM TUYỆT ĐỐI** AI tự động chạy các lệnh Git làm mất mã nguồn hoặc hoàn tác thay đổi chưa commit của người dùng:
- ❌ **TUYỆT ĐỐI CẤM:**
  - `git checkout -- <file>` hoặc `git checkout .` hoặc `git checkout -f`
  - `git restore .` hoặc `git restore <file>`
  - `git reset --hard` hoặc bất kỳ lệnh reset nào
  - `git clean -fd` hoặc `git clean -f`
  - `git stash drop` hoặc các lệnh xóa stash
- Khi người dùng hoặc AI đang chỉnh sửa code, **mọi thao tác phải bảo toàn code hiện có**.
- Không được phép tự ý "revert về bản cũ" khi gặp lỗi. Phải phân tích lỗi, đọc trace log và sửa trực tiếp tại vị trí lỗi.

## 2. NGUYÊN TẮC THAO TÁC FILE & TERMINAL
- Chỉ sử dụng các công cụ chỉnh sửa file (`replace_file_content`, `multi_replace_file_content`, `write_to_file`) với phạm vi can thiệp tối thiểu và chính xác.
- Khi cần kiểm tra lịch sử commit, chỉ dùng các lệnh mang tính chất đọc (`git log`, `git status`, `git diff`).
- Luôn tôn trọng các cấu hình của người dùng trong `.env`, `config/`, và `proxies.json`.
