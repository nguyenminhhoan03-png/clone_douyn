"""
Translator - Dịch text từ tiếng Trung (Douyin) sang tiếng Việt
Sử dụng Google Translate API miễn phí (không cần API key).
"""
import re

import httpx
from loguru import logger


def translate_text(text: str, src: str = "zh-CN", dest: str = "vi") -> str:
    """
    Dịch text sang ngôn ngữ đích sử dụng Google Translate API miễn phí.

    Args:
        text: Văn bản cần dịch
        src: Ngôn ngữ nguồn (default: zh-CN = tiếng Trung)
        dest: Ngôn ngữ đích (default: vi = tiếng Việt)

    Returns:
        Văn bản đã dịch, hoặc text gốc nếu dịch thất bại
    """
    if not text or not text.strip():
        return text

    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": src,
            "tl": dest,
            "dt": "t",
            "q": text.strip(),
        }

        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            resp = client.get(url, params=params)
            if resp.status_code == 200:
                result = resp.json()
                translated = "".join(
                    item[0] for item in result[0] if item and item[0]
                )
                
                # Bộ lọc thuật ngữ Review Phim chuyên dụng (Fix lỗi Google Dịch)
                if dest == "vi":
                    replacements = {
                        "phân tử": "phần tử", # Vd: phần tử khủng bố, không phải phân tử hóa học
                        "nam vương": "nam chính",
                        "người đàn ông": "nam chính",
                        "cô gái": "nữ chính",
                        "người phụ nữ": "nữ chính",
                        "tiểu tam": "kẻ thứ ba",
                        "máy phát điện": "người phát điện",
                        "đại thông minh": "tên ngốc",
                        "khuê mật": "bạn thân",
                        "cảnh sát trưởng": "cảnh sát",
                        "xã hội đen": "giang hồ",
                        "lão đại": "đại ca",
                        "tổng tài": "chủ tịch",
                        "thiết bị": "hệ thống",
                        "nhạc mẫu": "mẹ vợ",
                        "nhạc phụ": "bố vợ",
                        "bạn trai cũ": "người yêu cũ",
                        "bạn gái cũ": "người yêu cũ",
                        "bạn trai": "người yêu",
                        "bạn gái": "người yêu",
                    }
                    for old, new in replacements.items():
                        # Thay thế không phân biệt hoa thường một cách tương đối
                        translated = translated.replace(old, new)
                        translated = translated.replace(old.capitalize(), new.capitalize())
                
                logger.debug(f"Translated: '{text[:50]}' → '{translated[:50]}'")
                return translated.strip()
            else:
                logger.warning(f"Translation API returned {resp.status_code}")
                return text
    except Exception as e:
        logger.warning(f"Translation failed: {e}")
        return text


def translate_description(desc: str) -> str:
    """
    Dịch description video từ tiếng Trung sang tiếng Việt.
    Tự động tách hashtags ra, dịch phần text, giữ nguyên emoji.

    Args:
        desc: Description gốc (tiếng Trung)

    Returns:
        Description đã dịch sang tiếng Việt (không kèm hashtags)
    """
    if not desc:
        return ""

    # Tách hashtags ra (không dịch hashtags ở đây)
    clean_text = re.sub(r"#\S+", "", desc).strip()

    # Xóa @mentions
    clean_text = re.sub(r"@\S+", "", clean_text).strip()

    if not clean_text or len(clean_text) < 2:
        return ""

    # Dịch phần text chính
    translated = translate_text(clean_text, src="auto", dest="vi")
    return translated.strip()


def translate_hashtags(tags_str: str) -> list:
    """
    Dịch hashtags từ tiếng Trung sang tiếng Việt.

    Args:
        tags_str: String dạng "tag1 tag2 tag3" (không có dấu #)

    Returns:
        List hashtags tiếng Việt dạng ["#tag1_vi", "#tag2_vi", ...]
    """
    if not tags_str or not tags_str.strip():
        return []

    tags = tags_str.strip().split()
    translated_tags = []

    for tag in tags:
        tag = tag.strip()
        if not tag:
            continue

        try:
            translated = translate_text(tag, src="auto", dest="vi")
            # Clean: xóa khoảng trắng, ký tự đặc biệt
            clean_tag = re.sub(r"[^\w\u00C0-\u024F\u1E00-\u1EFF]", "", translated)
            if clean_tag and len(clean_tag) > 1:
                translated_tags.append(f"#{clean_tag}")
        except Exception:
            continue

    return translated_tags


def build_vietnamese_caption(title: str, tags: str,
                              default_hashtags: list = None) -> str:
    """
    Tạo caption tiếng Việt hoàn chỉnh cho TikTok.

    Args:
        title: Title gốc (tiếng Trung)
        tags: Tags gốc (string, khoảng trắng ngăn cách)
        default_hashtags: Hashtags mặc định thêm vào

    Returns:
        Caption tiếng Việt hoàn chỉnh (≤ 2200 ký tự)
    """
    # Dịch title
    title_vi = translate_description(title)
    if not title_vi or len(title_vi) < 3:
        title_vi = title  # Giữ nguyên nếu dịch fail

    # Dịch hashtags
    vi_hashtags = translate_hashtags(tags) if tags else []

    # Build caption
    translated_tags = translate_hashtags(tags) if tags else []

    # Thêm hashtags đã dịch (tối đa 5)
    if translated_tags:
        translated_tags = translated_tags[:5]

    if not default_hashtags:
        default_hashtags = ["#fyp", "#xuhuong", "#reviewphim"]

    tags_str = " ".join(default_hashtags + translated_tags)
    caption = f"✨ {translated_title}\n\n{tags_str}"
    return caption

def translate_srt_with_gemini(payload_text: str, api_key: str) -> str:
    """
    Dịch text payload (dạng ID|text) thông qua SaaS Backend.
    """
    from auth_client import auth_client
    try:
        prompt = (
            "Bạn là chuyên gia Review Phim/Video ngắn TikTok chuyên nghiệp tại Việt Nam.\n"
            "Hãy dịch các câu tiếng Trung sau sang tiếng Việt. Yêu cầu dịch thoát ý, mượt mà, đúng ngữ cảnh mạng xã hội Việt Nam.\n"
            "YÊU CẦU BẮT BUỘC (Nếu vi phạm sẽ gây lỗi hệ thống):\n"
            "1. TUYỆT ĐỐI giữ nguyên cấu trúc 'ID|nội dung dịch'. Không thêm bớt bất kỳ dòng nào.\n"
            "2. TUYỆT ĐỐI không gộp các dòng lại với nhau.\n"
            "3. KHÔNG dịch sát nghĩa (word-for-word) hay dịch thô máy móc. Hãy chuyển đổi từ lóng Douyin sang ngôn ngữ GenZ/TikTok Việt Nam (VD: 'tổng tài', 'trà xanh', 'cẩu lương', 'tiểu tam', 'khuê mật' -> 'bạn thân').\n"
            "4. Câu văn phải ngắn gọn, súc tích, giật gân, nhịp điệu nhanh để làm giọng đọc AI.\n"
            "5. Không dùng đại từ 'Tôi' để gọi nhân vật trừ khi đó là góc nhìn thứ nhất.\n"
            "6. Không giải thích, không bình luận, CHỈ trả về danh sách đã dịch.\n\n"
            "Nội dung cần dịch:\n"
            f"{payload_text}"
        )
        
        logger.info("Đang gửi danh sách text lên Backend Proxy (Gemini)...")
        
        text = auth_client.generate_ai(prompt)
        if text:
            logger.info("Gemini đã dịch xong kịch bản (Chuẩn ngữ cảnh 100%)")
            return text.strip()
        else:
            logger.warning("Gemini trả về rỗng, fallback về bản gốc.")
            return payload_text
    except Exception as e:
        logger.error(f"Lỗi khi dịch bằng Gemini Proxy: {e}")
        return None

def generate_youtube_metadata_with_gemini(original_title: str, api_keys: list) -> dict:
    """Sử dụng Gemini (qua SaaS Backend) để tạo Tiêu đề Clickbait và SEO Metadata."""
    import json
    from loguru import logger
    from auth_client import auth_client
    
    prompt = (
        "Bạn là chuyên gia SEO YouTube Shorts và Viral Marketing tại Việt Nam. "
        "Dựa vào nội dung gốc tiếng Trung sau đây, hãy sáng tạo siêu dữ liệu "
        "(metadata) cho video YouTube Shorts để tối đa hóa lượt xem (giật tít, gây tò mò, bắt trend GenZ).\n\n"
        f"Nội dung gốc: {original_title}\n\n"
        "YÊU CẦU BẮT BUỘC:\n"
        "1. Tiêu đề (title): Dưới 80 ký tự, phải siêu giật tít, có 1-2 emoji nổi bật.\n"
        "2. Mô tả (description): 2-3 câu ngắn gọn, kêu gọi tương tác (vd: Nhớ Đăng ký kênh nhé).\n"
        "3. Tags (tags): 5-7 hashtag tiếng Việt hoặc tiếng Anh không dấu, viết liền (không có dấu #).\n"
        "4. CHỈ TRẢ VỀ JSON hợp lệ với định dạng chính xác như sau (không kèm markdown, không giải thích):\n"
        '{"title": "...", "description": "...", "tags": ["...", "..."]}'
    )
    
    try:
        text = auth_client.generate_ai(prompt)
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
            
        data = json.loads(text.strip())
        if "title" in data and "description" in data and "tags" in data:
            logger.info("✅ Đã tạo YouTube SEO Metadata bằng Gemini thành công!")
            return data
    except Exception as e:
        logger.warning(f"Lỗi tạo YT Metadata qua Backend Proxy: {e}")
        
    return None
