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
    caption = f"✨ {title_vi}"

    # Thêm hashtags đã dịch (tối đa 5)
    if vi_hashtags:
        caption += " " + " ".join(vi_hashtags[:5])

    # Thêm default hashtags
    if default_hashtags:
        caption += " " + " ".join(default_hashtags[:8])

    # TikTok giới hạn 2200 ký tự
    return caption[:2200]
