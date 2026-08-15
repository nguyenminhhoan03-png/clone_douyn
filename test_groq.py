import os
from dotenv import load_dotenv
load_dotenv('e:/Project_ItWebDev/Python/tiktok-upload-video/.env')
api_key = os.getenv('GEMINI_API_KEY')

import requests
prompt = """Bạn là chuyên gia Review Phim/Video ngắn TikTok chuyên nghiệp tại Việt Nam.
Hãy dịch các câu tiếng Trung sau sang tiếng Việt. Yêu cầu dịch thoát ý, mượt mà, đúng ngữ cảnh mạng xã hội Việt Nam.
YÊU CẦU BẮT BUỘC (Nếu vi phạm sẽ gây lỗi hệ thống):
1. TUYỆT ĐỐI giữ nguyên cấu trúc 'ID|nội dung dịch'. Không thêm bớt bất kỳ dòng nào.
2. TUYỆT ĐỐI không gộp các dòng lại với nhau.
3. KHÔNG dịch thô. Chuyển đổi từ lóng Douyin sang ngôn ngữ TikTok Việt Nam (VD: 'tổng tài', 'khuê mật' -> 'bạn thân').
4. NHẬN DIỆN NHÂN VẬT: Dựa vào ngữ cảnh, hãy thêm nhãn [M] (Nam), [F] (Nữ), hoặc [N] (Người kể chuyện/Không rõ) vào ngay sau dấu |. 
Ví dụ gốc: '1|你好帅哥'
Ví dụ dịch: '1|[F] Chào anh đẹp trai nhé.'
CHÚ Ý CUỐI CÙNG: Không giải thích, không bình luận, CHỈ trả về danh sách đã dịch.

Nội dung cần dịch:
1|这个女孩站了很久
2|似乎进不去
3|谢谢
4|这个回眸真的让我心动
5|刚搬来这里吗
6|是啊，我刚搬来
7|你知道路吗？我带你去吧
"""

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}
data = {
    "model": "llama-3.3-70b-versatile",
    "messages": [
        {"role": "user", "content": prompt}
    ],
    "temperature": 0.3
}
try:
    resp = requests.post("https://api.groq.com/openai/v1/chat/completions", json=data, headers=headers, timeout=30)
    print(resp.json().get("choices", [{}])[0].get("message", {}).get("content", ""))
except Exception as e:
    print(f"Error: {e}")
