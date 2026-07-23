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

def translate_srt_with_gemini(srt_content: str, api_key: str) -> str:
    """
    Dịch toàn bộ file SRT bằng Google Gemini (LLM) để đảm bảo chuẩn ngữ cảnh.
    """
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        # Sử dụng model gemini-2.5-flash cho tốc độ nhanh và chi phí rẻ/miễn phí
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = (
            "Bạn là một chuyên gia Review Phim TikTok chuyên nghiệp tại Việt Nam. "
            "Dưới đây là nội dung file SRT tiếng Trung của một đoạn review phim. "
            "Hãy dịch toàn bộ sang tiếng Việt với văn phong giật gân, lôi cuốn, mượt mà như văn nói mạng xã hội. "
            "Yêu cầu BẮT BUỘC:\n"
            "1. TUYỆT ĐỐI GIỮ NGUYÊN cấu trúc thời gian (timestamps) và số thứ tự của file SRT. Chỉ thay đổi phần chữ tiếng Trung thành tiếng Việt.\n"
            "2. TUYỆT ĐỐI KHÔNG dùng đại từ 'Tôi' để gọi nhân vật, tự hiểu ngữ cảnh và gọi là 'Anh ta', 'Cô ta', 'Nam chính', 'Nữ chính', 'Bọn họ' v.v.\n"
            "3. Không thêm bất kỳ lời bình luận hay giải thích nào ở đầu và cuối, chỉ trả về nội dung SRT.\n\n"
            "Nội dung SRT:\n"
            f"{srt_content}"
        )
        
        logger.info("Đang gửi toàn bộ kịch bản cho Gemini phân tích ngữ cảnh...")
        response = model.generate_content(prompt)
        
        if response and response.text:
            logger.info("Gemini đã dịch xong kịch bản (Chuẩn ngữ cảnh 100%)")
            return response.text.strip()
        else:
            logger.warning("Gemini trả về rỗng, fallback về bản gốc.")
            return srt_content
    except Exception as e:
        logger.error(f"Lỗi khi dịch bằng Gemini: {e}")
        return srt_content
