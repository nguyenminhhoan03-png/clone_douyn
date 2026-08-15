import requests, json

headers = {
    'Authorization': 'Bearer YOUR_API_KEY_HERE',
    'Content-Type': 'application/json'
}

data = {
    'model': 'qwen/qwen3.6-27b',
    'messages': [
        {
            'role': 'system',
            'content': (
                'Bạn là biên kịch lồng tiếng chuyên nghiệp hàng đầu Việt Nam, chuyên Việt hóa video ngắn Douyin/TikTok Trung Quốc.\n'
                'Phong cách của bạn: tự nhiên, truyền cảm, đúng ngữ cảnh cảm xúc, giống người Việt nói chuyện thật.\n'
                'Bạn KHÔNG BAO GIỜ dịch máy móc từng từ. Bạn luôn dịch THOÁT Ý theo cách người Việt thực sự nói.\n'
            )
        },
        {
            'role': 'user',
            'content': (
                'Dịch các câu tiếng Trung dưới đây sang tiếng Việt. Đây là phụ đề từ VIDEO NGẮN Douyin (drama tình cảm).\n'
                '1. BẮT BUỘC thực hiện theo 2 bước: Phân tích trước, Dịch sau.\n'
                '   - Bước 1: Viết 1 đoạn [PHÂN TÍCH] ngắn (2-3 câu) để xác định xem ai đang nói chuyện với ai, mối quan hệ là gì, cảm xúc của họ ra sao.\n'
                '   - Bước 2: Viết [BẢN DỊCH]. Trong bản dịch BẮT BUỘC GIỮ NGUYÊN cấu trúc ID|nội dung dịch. Không thêm/bớt dòng.\n'
                '2. Dịch THOÁT Ý, tự nhiên như người Việt nói. KHÔNG dịch word-by-word.\n\n'
                'Ví dụ Output:\n'
                '[PHÂN TÍCH]\nĐây là cuộc nói chuyện giữa cô gái và người yêu cũ (tra nam). Cô gái đang rất giận dữ và thất vọng.\n\n'
                '[BẢN DỊCH]\n'
                '1|[F] Đồ tồi, anh lừa dối tôi!\n'
                '2|[M] Xin em nghe anh giải thích đã.\n\n'
                'Nội dung cần dịch:\n'
                '1|你好帅哥\n'
                '2|我想你了\n'
                '3|我们一起去吃饭吧\n'
                '4|渣男都是这样的\n'
                '5|我在车上 一点都不冷\n'
                '6|宝贝你在哪里\n'
                '7|总裁大人对我太好了\n'
                '8|闺蜜你怎么哭了\n'
            )
        }
    ],
    'temperature': 0.4,
    'max_tokens': 2048
}

resp = requests.post(
    'https://api.groq.com/openai/v1/chat/completions',
    json=data, headers=headers, timeout=30
)

if resp.status_code == 200:
    result = resp.json()
    text = result['choices'][0]['message']['content']
    print("=== KẾT QUẢ DỊCH BẰNG QWEN 3.6 ===")
    print(text)
    print("\n=== SO SÁNH VỚI LLAMA 3.3 ===")
    
    # Test lại bằng LLaMA để so sánh
    data['model'] = 'llama-3.3-70b-versatile'
    resp2 = requests.post(
        'https://api.groq.com/openai/v1/chat/completions',
        json=data, headers=headers, timeout=30
    )
    if resp2.status_code == 200:
        text2 = resp2.json()['choices'][0]['message']['content']
        print(text2)
else:
    print(f"Error {resp.status_code}: {resp.text}")
