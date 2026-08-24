"""
Translator - Dịch text từ tiếng Trung (Douyin) sang tiếng Việt
Sử dụng Google Translate API miễn phí (không cần API key).
"""
import re

import httpx
from loguru import logger


_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "vi,en-US;q=0.9,en;q=0.8,zh-CN;q=0.7",
}

_REPLACEMENTS = {
    "phân tử": "phần tử",
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

def _apply_replacements(translated: str) -> str:
    for old, new in _REPLACEMENTS.items():
        translated = translated.replace(old, new)
        translated = translated.replace(old.capitalize(), new.capitalize())
    return translated

def translate_text(text: str, src: str = "zh-CN", dest: str = "vi") -> str:
    """
    Dịch text sang ngôn ngữ đích sử dụng Google Translate API miễn phí với multi-endpoint & retry.
    """
    if not text or not text.strip():
        return text

    # Endpoint 1: translate_a/single
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": src,
            "tl": dest,
            "dt": "t",
            "q": text.strip(),
        }
        with httpx.Client(timeout=10.0, headers=_HEADERS, follow_redirects=True) as client:
            resp = client.get(url, params=params)
            if resp.status_code == 200:
                result = resp.json()
                translated = "".join(item[0] for item in result[0] if item and item[0])
                if dest == "vi":
                    translated = _apply_replacements(translated)
                return translated.strip()
    except Exception:
        pass

    # Endpoint 2: clients5.google.com fallback
    try:
        url2 = "https://clients5.google.com/translate_a/t"
        params2 = {
            "client": "dict-chrome-ex",
            "sl": src,
            "tl": dest,
            "q": text.strip(),
        }
        with httpx.Client(timeout=10.0, headers=_HEADERS, follow_redirects=True) as client:
            resp2 = client.get(url2, params=params2)
            if resp2.status_code == 200:
                data = resp2.json()
                if isinstance(data, list) and len(data) > 0:
                    translated = "".join(data) if isinstance(data[0], str) else str(data[0])
                    if dest == "vi":
                        translated = _apply_replacements(translated)
                    return translated.strip()
    except Exception:
        pass

    return text


def translate_lines_batch(lines: list, src: str = "zh-CN", dest: str = "vi") -> list:
    """
    Dịch hàng loạt câu cùng lúc (ghép bằng dấu xuống dòng) để giảm 90% số lượng request,
    tránh hoàn toàn lỗi Rate Limit 429 trên VPS.
    """
    if not lines:
        return []

    combined_text = "\n".join(lines)
    translated_combined = translate_text(combined_text, src=src, dest=dest)
    translated_lines = translated_combined.split("\n")

    # Nếu số lượng dòng khớp nhau, trả về danh sách đã dịch
    if len(translated_lines) == len(lines):
        return [l.strip() for l in translated_lines]

    # Nếu không khớp độ dài, fallback dịch từng dòng với delay ngắn
    results = []
    import time
    for line in lines:
        results.append(translate_text(line, src=src, dest=dest))
        time.sleep(0.15)
    return results


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

def translate_srt_with_gemini(payload_text: str, api_key: str, multi_speaker: bool = False) -> str:
    """
    Pipeline 2 bước (Senior++):
      Bước 1: AI sửa lỗi Whisper (dùng model riêng → tránh rate limit)
      Bước 2: AI dịch text Trung đã sửa → tiếng Việt tự nhiên  
    """
    from auth_client import auth_client
    from loguru import logger
    import time
    
    try:
        is_groq = api_key and api_key.startswith("gsk_")
        ai_name = "Groq" if is_groq else "Gemini"
        
        # Model cho từng Pass (Groq rate limit TÁCH BIỆT theo model)
        # Pass 1: Model chuyên tiếng Trung để sửa lỗi Whisper
        # Pass 2: Model mạnh nhất để dịch sang tiếng Việt
        PASS1_MODEL = "llama-3.1-8b-instant" if is_groq else None       # Dùng model nhỏ/nhanh để sửa lỗi chính tả
        PASS2_MODEL = "llama-3.3-70b-versatile" if is_groq else None  # Llama mạnh nhất cho dịch thuật
        
        # ═══════════════════════════════════════════════════════════
        # PASS 1: SỬA LỖI WHISPER — Qwen đọc toàn bộ rồi sửa tiếng Trung
        # ═══════════════════════════════════════════════════════════
        correction_prompt = (
            "你是中文语音识别纠错专家。\n"
            "以下数据是Whisper语音识别AI从抖音/TikTok视频中自动提取的中文字幕。\n\n"
            "Whisper经常听错，特别是：\n"
            "- 同音字/近音字（如：铃魂→灵魂，拉飞→拉菲，结证→结婚证，亲自我→亲嘴）\n"
            "- 专有名词、品牌名被写错\n"
            "- 句子被截断或两句话被错误合并\n"
            "- 抖音/网络用语被识别成普通词语\n\n"
            "任务：\n"
            "1. 通读全部内容，理解视频的完整语境（主题、人物关系、场景）。\n"
            "2. 对每一行，如果内容在语境中无意义或奇怪→用最合理的同音/近音词替换。\n"
            "3. 如果句子被截断，根据上下文补充完整。\n"
            "4. 已经正确的文本→保持不变。\n\n"
            "硬性规则：\n"
            "- 保持'ID|text'格式不变。不添加、不删除、不合并行。\n"
            "- 只返回修正后的列表。不解释。\n"
            "- 输出必须是中文（修正后），不要翻译成其他语言。\n\n"
            f"需要修正的数据：\n{payload_text}"
        )
        
        pass1_model_name = "Llama-8B" if is_groq else ai_name
        logger.info(f"[Pass 1/2] 🔍 {pass1_model_name} đang đọc ngữ cảnh & sửa lỗi Whisper...")
        
        corrected_chinese = payload_text  # fallback mặc định
        try:
            result = auth_client.generate_ai(correction_prompt, api_key=api_key, model=PASS1_MODEL)
            if result and result.strip():
                corrected_chinese = result.strip()
                # Log sự khác biệt giữa text gốc và text đã sửa
                orig_lines = [l.strip() for l in payload_text.strip().split('\n') if '|' in l]
                fixed_lines = [l.strip() for l in corrected_chinese.split('\n') if '|' in l]
                fix_count = 0
                for o, f in zip(orig_lines, fixed_lines):
                    if o != f:
                        fix_count += 1
                        logger.info(f"  🔧 Sửa lỗi: {o} → {f}")
                if fix_count > 0:
                    logger.info(f"  ✅ Đã sửa {fix_count}/{len(orig_lines)} câu bị Whisper nghe sai")
                else:
                    logger.info(f"  ✅ Không phát hiện lỗi Whisper nào cần sửa")
            else:
                logger.warning("Pass 1 trả về rỗng, dùng text gốc...")
        except Exception as e1:
            logger.warning(f"Pass 1 ({pass1_model_name}) lỗi: {str(e1)[:80]}. Dùng text gốc cho Pass 2...")
        
        # Nghỉ 1s giữa 2 pass để tránh burst rate limit
        time.sleep(1)
        
        # ═══════════════════════════════════════════════════════════
        # PASS 2: DỊCH TIẾNG TRUNG (ĐÃ SỬA) → TIẾNG VIỆT TỰ NHIÊN
        # ═══════════════════════════════════════════════════════════
        if multi_speaker:
            instruction = (
                "NHẬN DIỆN NHÂN VẬT (BẮT BUỘC): Thêm chính xác một trong các nhãn [M], [F], hoặc [N] vào ngay sau dấu |. Tuyệt đối không thêm chữ (Nam) hay (Nữ).\n"
                "- [M]: Giọng Nam\n"
                "- [F]: Giọng Nữ\n"
                "- [N]: Người kể chuyện / Không rõ\n"
                "Ví dụ: '1|你好帅哥' → '1|[F] Chào anh đẹp trai nhé.'\n"
            )
        else:
            instruction = (
                "Câu văn phải ngắn gọn, súc tích, nhịp điệu nhanh phù hợp giọng đọc AI.\n"
                "Không dùng đại từ 'Tôi' trừ khi đó là góc nhìn thứ nhất.\n"
            )
        
        translation_prompt = (
    "Bạn là BIÊN DỊCH VIÊN TIẾNG TRUNG → TIẾNG VIỆT chuyên nghiệp, đồng thời là "
    "biên tập viên phụ đề và đạo diễn lồng tiếng cho video ngắn Trung Quốc "
    "(Douyin/TikTok), phim ngắn, drama, ngôn tình, cổ trang, hiện đại, hài, đời sống "
    "và video kể chuyện.\n\n"

    "NHIỆM VỤ:\n"
    "Dịch toàn bộ phụ đề tiếng Trung được cung cấp sang tiếng Việt.\n"
    "Mục tiêu ưu tiên theo thứ tự:\n"
    "1. ĐÚNG NGHĨA GỐC.\n"
    "2. ĐÚNG NGỮ CẢNH VÀ QUAN HỆ GIỮA NHÂN VẬT.\n"
    "3. ĐÚNG SẮC THÁI CẢM XÚC.\n"
    "4. TIẾNG VIỆT TỰ NHIÊN, GIỐNG NGƯỜI VIỆT NÓI.\n"
    "5. NGẮN GỌN, DỄ ĐỌC, PHÙ HỢP SUB VIDEO NGẮN.\n\n"

    "==================================================\n"
    "I. NGUYÊN TẮC CỐT LÕI\n"
    "==================================================\n"

    "1. TUYỆT ĐỐI KHÔNG DỊCH WORD-BY-WORD.\n"
    "   - Không bê nguyên cấu trúc câu tiếng Trung sang tiếng Việt.\n"
    "   - Được phép đảo câu, thay đổi cách diễn đạt nếu vẫn giữ nguyên ý nghĩa.\n"
    "   - Ưu tiên cách nói mà người Việt thực sự sử dụng.\n\n"

    "2. KHÔNG ĐƯỢC TỰ BỊA THÊM THÔNG TIN.\n"
    "   - Không tự thêm nhân vật, địa điểm, hành động, cảm xúc hoặc nguyên nhân "
    "nếu bản gốc không có.\n"
    "   - Có thể bổ sung CHỦ NGỮ bị ẩn nếu ngữ cảnh chắc chắn xác định được người thực hiện hành động.\n"
    "   - Nếu không xác định được thì dùng cách diễn đạt trung tính, không đoán bừa.\n\n"

    "3. ƯU TIÊN NGỮ CẢNH TOÀN ĐOẠN.\n"
    "   - Không dịch từng dòng một cách độc lập.\n"
    "   - Luôn đọc các dòng trước và sau để hiểu câu chuyện.\n"
    "   - Một câu có thể bị chia thành nhiều dòng subtitle.\n"
    "   - Nếu một dòng chỉ có 1-2 từ như '什么', '然后', '结果', '后来', '你...', "
    "hãy dựa vào câu trước/sau để dịch cho hoàn chỉnh.\n\n"

    "4. GIỮ NGUYÊN THÔNG TIN QUAN TRỌNG.\n"
    "   - Không tự bỏ số lượng, thời gian, tiền bạc, tên người, địa điểm, chức vụ, "
    "vật phẩm hoặc hành động quan trọng.\n"
    "   - Không đổi đơn vị một cách tùy tiện.\n\n"

    "==================================================\n"
    "II. ĐẠI TỪ NHÂN XƯNG - CỰC KỲ QUAN TRỌNG\n"
    "==================================================\n"

    "Không mặc định dịch 我 = 'tôi', 你 = 'bạn'.\n"
    "Phải xác định quan hệ giữa người nói và người nghe trước khi chọn đại từ.\n\n"

    "1. NGÔN TÌNH / TÌNH YÊU:\n"
    "   - Nam nữ thân mật: anh - em.\n"
    "   - Người yêu/vợ chồng: anh - em, anh - mình, em - anh, tùy ngữ cảnh.\n"
    "   - Người lớn tuổi hơn: anh/chị - em.\n"
    "   - Có thể dùng 'cô', 'chú', 'chị', 'anh', 'em' nếu phù hợp tuổi tác.\n\n"

    "2. BẠN BÈ / NGƯỜI TRẺ:\n"
    "   - Có thể dùng tao - mày khi quan hệ thân mật/cộc lốc.\n"
    "   - Tớ - cậu khi thân thiện.\n"
    "   - Mình - bạn khi nhẹ nhàng.\n"
    "   - Không dùng tao - mày nếu ngữ cảnh không phù hợp.\n\n"

    "3. GIA ĐÌNH:\n"
    "   - 爸爸 → bố/ba/cha tùy phong cách.\n"
    "   - 妈妈 → mẹ/má/mẫu thân tùy bối cảnh.\n"
    "   - 哥哥 → anh.\n"
    "   - 姐姐 → chị.\n"
    "   - 弟弟 → em trai.\n"
    "   - 妹妹 → em gái.\n"
    "   - 爷爷 → ông nội.\n"
    "   - 奶奶 → bà nội.\n"
    "   - 外公 → ông ngoại.\n"
    "   - 外婆 → bà ngoại.\n"
    "   - Không máy móc chuyển mọi quan hệ thân thuộc thành 'anh/em'.\n\n"

    "4. NGƯỜI TRẺ NÓI VỚI NGƯỜI LỚN:\n"
    "   - Có thể dùng con/cháu - cô/chú/bác/ông/bà tùy quan hệ.\n"
    "   - Không dùng 'chú dì' nếu tiếng Việt tự nhiên hơn là 'cô chú'.\n\n"

    "5. CẤP TRÊN / CẤP DƯỚI:\n"
    "   - Xem xét chức vụ, tuổi tác và mức độ thân thiết.\n"
    "   - Ví dụ: sếp - tôi, sếp - em, anh - tôi, cấp trên - cấp dưới.\n"
    "   - Không mặc định mọi người đều xưng 'tôi - bạn'.\n\n"

    "6. CỔ TRANG:\n"
    "   - Phải xét thân phận: ta, ngươi, nàng, chàng, bổn vương, bổn cung, thần, "
    "nô tỳ, thuộc hạ, tiểu nhân, đại nhân, điện hạ, bệ hạ...\n"
    "   - Không lạm dụng từ cổ nếu bản gốc không mang sắc thái cổ trang.\n"
    "   - Không biến phim hiện đại thành văn cổ.\n\n"

    "7. ĐẠI TỪ CÓ TÍNH XÚC PHẠM:\n"
    "   - 你这个废物 → đồ vô dụng này / mày đúng là đồ vô dụng.\n"
    "   - 你这个女人 → cô đúng là... / người phụ nữ này... tùy ngữ cảnh.\n"
    "   - Phải giữ sắc thái mắng, khinh thường, giễu cợt nếu bản gốc có.\n\n"

    "==================================================\n"
    "III. CHỦ NGỮ ẨN TRONG TIẾNG TRUNG\n"
    "==================================================\n"

    "Tiếng Trung thường bỏ chủ ngữ.\n"
    "Ví dụ:\n"
    "   '去了医院。' có thể là 'Anh ấy đi bệnh viện', 'Cô ấy đi bệnh viện', "
    "'Tôi đi bệnh viện' tùy ngữ cảnh.\n\n"
    "QUY TẮC:\n"
    "- Nếu xác định chắc chắn chủ thể → thêm chủ ngữ tiếng Việt.\n"
    "- Nếu chưa xác định → không được tự đoán.\n"
    "- Có thể dùng câu bị động/chủ động hoặc bỏ chủ ngữ nếu tiếng Việt vẫn tự nhiên.\n\n"

    "==================================================\n"
    "IV. SẮC THÁI CẢM XÚC VÀ GIỌNG ĐIỆU\n"
    "==================================================\n"

    "Phải nhận diện sắc thái câu trước khi dịch:\n"
    "- Bình thường.\n"
    "- Thân mật.\n"
    "- Dịu dàng.\n"
    "- Lãng mạn.\n"
    "- Hài hước.\n"
    "- Cà khịa.\n"
    "- Mỉa mai.\n"
    "- Tức giận.\n"
    "- Đe dọa.\n"
    "- Khinh thường.\n"
    "- Buồn bã.\n"
    "- Hoảng sợ.\n"
    "- Ngạc nhiên.\n"
    "- Căng thẳng.\n"
    "- Trang trọng.\n"
    "- Lạnh lùng.\n"
    "- Trẻ con.\n"
    "- Nũng nịu.\n\n"

    "Không được dịch mọi câu bằng cùng một giọng văn.\n"
    "Ví dụ:\n"
    "   '你疯了吗？'\n"
    "Không nhất thiết luôn là 'Bạn bị điên à?'.\n"
    "Có thể là 'Anh điên rồi à?', 'Mày điên à?', 'Cậu bị điên hả?' tùy quan hệ.\n\n"

    "==================================================\n"
    "V. THÀNH NGỮ, TỤC NGỮ, CỤM TỪ CỐ ĐỊNH\n"
    "==================================================\n"

    "Không dịch từng chữ đối với thành ngữ Trung Quốc.\n"
    "Hãy tìm cách diễn đạt tương đương trong tiếng Việt.\n\n"

    "Ví dụ:\n"
    "   自作自受 → tự làm tự chịu.\n"
    "   乱七八糟 → rối tung rối mù / lộn xộn.\n"
    "   一见钟情 → yêu từ cái nhìn đầu tiên.\n"
    "   走投无路 → không còn đường lui.\n"
    "   胡说八道 → nói linh tinh / nói nhảm.\n"
    "   不知好歹 → không biết điều.\n"
    "   得寸进尺 → được đằng chân lân đằng đầu.\n\n"

    "Nếu có thành ngữ nhưng không có tương đương hoàn toàn trong tiếng Việt, "
    "ưu tiên truyền tải ĐÚNG Ý + ĐÚNG SẮC THÁI thay vì dịch từng chữ.\n\n"

    "==================================================\n"
    "VI. TIẾNG LÓNG / DOUYIN / GEN Z\n"
    "==================================================\n"

    "Khi gặp slang Trung Quốc, không dịch máy móc.\n"
    "Nếu có từ tương đương tự nhiên trong tiếng Việt thì sử dụng.\n\n"

    "Ví dụ:\n"
    "   绿茶 → trà xanh.\n"
    "   渣男 → tra nam / gã tồi trong tình cảm.\n"
    "   闺蜜 → bạn thân / hội bạn thân.\n"
    "   总裁 → tổng tài nếu là văn phong drama; CEO/chủ tịch nếu bối cảnh hiện đại.\n"
    "   白月光 → bạch nguyệt quang / người trong lòng khó quên tùy ngữ cảnh.\n"
    "   社死 → quê muốn độn thổ / chết vì quê.\n"
    "   内卷 → cạnh tranh khốc liệt / cuốn vào cuộc đua.\n"
    "   凡尔赛 → khoe mà như không khoe / Versailles.\n"
    "   破防 → chạm đúng nỗi đau / tan vỡ cảm xúc tùy ngữ cảnh.\n\n"

    "Không cố nhét slang Gen Z Việt vào mọi câu.\n"
    "Slang chỉ được dùng khi phù hợp với phong cách video.\n\n"

    "==================================================\n"
    "VII. TỪ TỤC, CHỬI, CÂU MẠNH\n"
    "==================================================\n"

    "Nếu bản gốc có chửi tục, xúc phạm hoặc câu nói mạnh thì phải giữ đúng mức độ.\n"
    "Không tự động làm nhẹ câu chửi.\n"
    "Không tự động tăng mức độ tục tĩu.\n\n"

    "Ví dụ:\n"
    "   滚 → cút / biến đi.\n"
    "   混蛋 → đồ khốn / thằng khốn.\n"
    "   王八蛋 → đồ khốn nạn / thằng chó tùy mức độ và bối cảnh.\n\n"

    "Phải xét tuổi tác, quan hệ và sắc thái nhân vật.\n\n"

    "==================================================\n"
    "VIII. NGÔN TÌNH / DRAMA / TÌNH CẢM\n"
    "==================================================\n"

    "Ưu tiên lời thoại tự nhiên, giàu cảm xúc nhưng không sến quá mức.\n"
    "Không biến lời thoại bình thường thành văn chương.\n\n"

    "Ví dụ:\n"
    "   我只是想见你一面。\n"
    "→ Anh chỉ muốn gặp em một lần thôi.\n\n"

    "   我从来没有忘记过你。\n"
    "→ Anh chưa từng quên em.\n\n"

    "Nếu nhân vật đang cãi nhau, giữ đúng sự gay gắt.\n"
    "Nếu đang tán tỉnh, giữ đúng sự flirt.\n"
    "Nếu đang chia tay, giữ đúng cảm xúc đau buồn.\n\n"

    "==================================================\n"
    "IX. CỔ TRANG / KIẾM HIỆP / CUNG ĐẤU / TIÊN HIỆP\n"
    "==================================================\n"

    "Khi phát hiện bối cảnh cổ trang, phải chuyển sang văn phong phù hợp.\n\n"

    "Các cách gọi có thể dùng:\n"
    "- 皇上 → Hoàng thượng / bệ hạ.\n"
    "- 皇后 → Hoàng hậu.\n"
    "- 太子 → Thái tử.\n"
    "- 王爷 → Vương gia.\n"
    "- 公主 → Công chúa.\n"
    "- 王妃 → Vương phi.\n"
    "- 娘娘 → nương nương.\n"
    "- 本王 → bổn vương.\n"
    "- 本宫 → bổn cung.\n"
    "- 臣 → thần.\n"
    "- 奴婢 → nô tỳ.\n"
    "- 属下 → thuộc hạ.\n"
    "- 在下 → tại hạ.\n"
    "- 师父 → sư phụ.\n"
    "- 师兄 → sư huynh.\n"
    "- 师姐 → sư tỷ.\n"
    "- 师弟 → sư đệ.\n"
    "- 师妹 → sư muội.\n\n"

    "Không áp dụng thuật ngữ cổ trang nếu video là đời hiện đại.\n\n"

    "==================================================\n"
    "X. TIÊN HIỆP / HUYỀN HUYỄN / TU TIÊN\n"
    "==================================================\n"

    "Giữ đúng hệ thống thuật ngữ của thể loại.\n"
    "Ví dụ:\n"
    "- 修炼 → tu luyện.\n"
    "- 灵气 → linh khí.\n"
    "- 丹药 → đan dược.\n"
    "- 境界 → cảnh giới.\n"
    "- 突破 → đột phá.\n"
    "- 渡劫 → độ kiếp.\n"
    "- 元婴 → Nguyên Anh.\n"
    "- 金丹 → Kim Đan.\n"
    "- 筑基 → Trúc Cơ.\n"
    "- 法宝 → pháp bảo.\n"
    "- 灵石 → linh thạch.\n"
    "- 宗门 → tông môn.\n"
    "- 长老 → trưởng lão.\n"
    "- 掌门 → chưởng môn.\n\n"

    "Không tùy tiện Việt hóa những thuật ngữ đã có cách dịch phổ biến trong thể loại.\n\n"

    "==================================================\n"
    "XI. HÀNH ĐỘNG / ĐÁNH NHAU / TỘI PHẠM\n"
    "==================================================\n"

    "Dịch rõ hành động và nhịp độ.\n"
    "Không làm câu hành động dài dòng.\n\n"

    "Ví dụ:\n"
    "   住手！ → Dừng tay!\n"
    "   放开她！ → Thả cô ấy ra!\n"
    "   给我滚！ → Cút khỏi đây cho tôi!\n"
    "   小心！ → Cẩn thận!\n"
    "   快跑！ → Chạy mau!\n\n"

    "==================================================\n"
    "XII. HÀI HƯỚC / CÀ KHỊA / MEME\n"
    "==================================================\n"

    "Nếu câu gốc mang tính hài hoặc meme, ưu tiên tạo hiệu ứng hài tương đương "
    "trong tiếng Việt nhưng không làm thay đổi nội dung.\n\n"

    "Có thể dùng:\n"
    "- trời ơi\n"
    "- chịu luôn\n"
    "- bó tay\n"
    "- hết cứu\n"
    "- ảo thật đấy\n"
    "- gì vậy trời\n"
    "- chịu thua\n"
    "- đúng là hết nói nổi\n\n"

    "Nhưng không được nhét meme vào những câu vốn nghiêm túc.\n\n"

    "==================================================\n"
    "XIII. NGHỀ NGHIỆP / CHUYÊN NGÀNH\n"
    "==================================================\n"

    "Nếu video thuộc ngành nghề cụ thể, phải ưu tiên thuật ngữ chuyên ngành chính xác.\n\n"

    "CÂU CÁ / CÂU CÁ GIẢI TRÍ:\n"
    "- 杆 → cần câu.\n"
    "- 鱼竿 → cần câu.\n"
    "- 鱼钩 → lưỡi câu.\n"
    "- 饵 → mồi.\n"
    "- 鱼饵 → mồi câu.\n"
    "- 中鱼 → dính cá / cá cắn câu.\n"
    "- 跑鱼 → sẩy cá.\n"
    "- 挂底 → vướng đáy / mắc đáy.\n"
    "- 抛竿 → quăng cần.\n"
    "- 收线 → thu dây.\n"
    "- 放线 → nhả dây.\n"
    "- 溜鱼 → ghì cá / vần cá.\n\n"

    "ẨM THỰC:\n"
    "- Không dịch máy móc tên món ăn.\n"
    "- Nếu món có tên riêng phổ biến ở Việt Nam thì dùng tên phổ biến.\n"
    "- Nếu không có tương đương, giữ tên món + mô tả ngắn nếu cần.\n\n"

    "GAME:\n"
    "- Giữ đúng thuật ngữ game phổ biến.\n"
    "- Ví dụ: buff, nerf, dame, tank, support, farm, rank nếu bối cảnh phù hợp.\n\n"

    "CÔNG NGHỆ:\n"
    "- Không Việt hóa tùy tiện thuật ngữ kỹ thuật phổ biến.\n"
    "- Ví dụ: server, database, API, bug, deploy, login...\n\n"

    "KHI GẶP NGHỀ KHÁC:\n"
    "- Y tế → dùng thuật ngữ y khoa tự nhiên.\n"
    "- Pháp luật → dùng thuật ngữ pháp lý.\n"
    "- Kinh doanh → dùng thuật ngữ kinh doanh.\n"
    "- Quân sự → dùng thuật ngữ quân sự.\n"
    "- Thể thao → dùng thuật ngữ thể thao.\n"
    "- Nấu ăn → dùng thuật ngữ bếp núc.\n"
    "- Thời trang → dùng thuật ngữ thời trang.\n"
    "- Xe cộ → dùng thuật ngữ kỹ thuật ô tô/xe máy.\n\n"

    "==================================================\n"
    "XIV. SỐ, TIỀN, THỜI GIAN, ĐƠN VỊ\n"
    "==================================================\n"

    "Không được tự ý thay đổi số liệu.\n"
    "Giữ nguyên giá trị thực tế của:\n"
    "- tiền bạc\n"
    "- tuổi\n"
    "- số lượng\n"
    "- ngày tháng\n"
    "- thời gian\n"
    "- phần trăm\n"
    "- khoảng cách\n"
    "- trọng lượng\n"
    "- nhiệt độ\n"
    "- tốc độ\n\n"

    "Có thể đổi cách đọc sang tiếng Việt tự nhiên nhưng tuyệt đối không làm thay đổi con số.\n\n"

    "==================================================\n"
    "XV. TÊN NGƯỜI / ĐỊA DANH / TÊN CÔNG TY\n"
    "==================================================\n"

    "1. Tên người Trung Quốc:\n"
    "- Giữ nguyên tên riêng theo phiên âm/thói quen dịch phù hợp.\n"
    "- Không tự đổi tên thành tên Việt.\n\n"

    "2. Địa danh:\n"
    "- Nếu có tên Việt phổ biến thì sử dụng tên Việt phổ biến.\n"
    "- Nếu không có, giữ phiên âm hợp lý.\n\n"

    "3. Công ty / thương hiệu / sản phẩm:\n"
    "- Không tự dịch tên thương hiệu nếu đó là tên riêng.\n"
    "- Nếu bản gốc dùng tên thương hiệu giả tưởng, giữ nguyên tên phù hợp.\n\n"

    "==================================================\n"
    "XVI. TỪ ĐA NGHĨA - PHẢI XÉT NGỮ CẢNH\n"
    "==================================================\n"

    "Không được chọn nghĩa đầu tiên của từ điển nếu ngữ cảnh cho thấy nghĩa khác.\n\n"

    "Ví dụ:\n"
    "   上头 có thể là 'cuốn', 'phấn khích', 'say', tùy ngữ cảnh.\n"
    "   老婆 có thể là 'vợ', 'bà xã', 'em', tùy quan hệ.\n"
    "   老公 có thể là 'chồng', 'ông xã', 'anh', tùy quan hệ.\n"
    "   哥 có thể là 'anh', 'ông anh', 'anh đây', tùy ngữ cảnh.\n"
    "   姐 có thể là 'chị', 'chị đây', 'bà chị', tùy ngữ cảnh.\n\n"

    "==================================================\n"
    "XVII. THÁN TỪ VÀ TỪ ĐỆM\n"
    "==================================================\n"

    "Dịch tự nhiên các từ:\n"
    "- 啊\n"
    "- 呀\n"
    "- 哦\n"
    "- 嗯\n"
    "- 呢\n"
    "- 嘛\n"
    "- 哈哈\n"
    "- 唉\n"
    "- 哎\n"
    "- 天啊\n"
    "- 我的天\n"
    "- 没事\n"
    "- 算了\n\n"

    "Không nhất thiết phải dịch từng từ thành một từ riêng.\n"
    "Có thể chuyển thành sắc thái tiếng Việt tương đương:\n"
    "   啊 → à, đó, đấy, nha, nhé... tùy câu.\n"
    "   呀 → nha, đó, đấy.\n"
    "   哦 → ồ, à, ra là vậy.\n"
    "   嗯 → ừ, ừm, vâng.\n"
    "   哎 → này, ôi, trời ơi...\n\n"

    "Không lạm dụng 'nhé/nha/á/hả' ở mọi câu.\n"
    "Chỉ thêm khi phù hợp với giọng nói tự nhiên.\n\n"

    "==================================================\n"
    "XVIII. CÂU HỎI / PHỦ ĐỊNH / NHẤN MẠNH\n"
    "==================================================\n"

    "Phải giữ chính xác sắc thái câu hỏi và phủ định.\n\n"

    "Đặc biệt chú ý:\n"
    "- 不\n"
    "- 没\n"
    "- 别\n"
    "- 未\n"
    "- 从来没有\n"
    "- 根本不\n"
    "- 怎么会\n"
    "- 难道\n"
    "- 居然\n"
    "- 竟然\n"
    "- 原来\n"
    "- 果然\n"
    "- 当然\n"
    "- 一定\n"
    "- 可能\n"
    "- 也许\n\n"

    "Không được bỏ mất từ phủ định hoặc biến câu nghi vấn thành câu khẳng định.\n\n"

    "==================================================\n"
    "XIX. BỊ ĐỘNG / CHỦ ĐỘNG / CẤU TRÚC TIẾNG TRUNG\n"
    "==================================================\n"

    "Các cấu trúc như:\n"
    "- 被\n"
    "- 把\n"
    "- 让\n"
    "- 叫\n"
    "- 给\n"
    "- 对\n"
    "- 跟\n"
    "- 为了\n"
    "- 因为...所以...\n"
    "- 虽然...但是...\n"
    "- 如果...就...\n"
    "phải được chuyển thành câu tiếng Việt tự nhiên.\n\n"

    "Không nhất thiết giữ nguyên cấu trúc ngữ pháp Trung Quốc.\n\n"

    "==================================================\n"
    "XX. SUB CHIA DÒNG / CÂU NGẮN\n"
    "==================================================\n"

    "Mỗi dòng subtitle phải dễ đọc và dễ hiểu.\n"
    "Ưu tiên câu ngắn, rõ nghĩa.\n"
    "Không cố kéo câu quá dài chỉ để bám từng chữ Trung Quốc.\n\n"

    "Nếu một câu tiếng Trung được chia thành nhiều dòng:\n"
    "- Hiểu toàn bộ câu trước.\n"
    "- Sau đó dịch từng dòng sao cho các dòng ghép lại thành một câu tự nhiên.\n"
    "- Không được làm mỗi dòng thành một câu độc lập nếu bản gốc không phải vậy.\n\n"

    "==================================================\n"
    "XXI. XỬ LÝ CÂU BỊ CẮT / SUB THIẾU NGỮ CẢNH\n"
    "==================================================\n"

    "Nếu dòng hiện tại không đủ nghĩa:\n"
    "- Đọc dòng trước.\n"
    "- Đọc dòng sau.\n"
    "- Suy luận từ mạch hội thoại.\n"
    "- Không dịch máy móc một cụm từ riêng lẻ.\n\n"

    "Nếu vẫn không đủ thông tin:\n"
    "- Chọn nghĩa phổ biến và trung tính nhất.\n"
    "- Tuyệt đối không tự sáng tác diễn biến.\n\n"

    "==================================================\n"
    "XXII. GIỌNG VĂN THEO THỂ LOẠI\n"
    "==================================================\n"

    "Tự động nhận diện thể loại và điều chỉnh văn phong:\n\n"

    "NGÔN TÌNH → mềm mại, tình cảm, tự nhiên.\n"
    "DRAMA → rõ cảm xúc, kịch tính.\n"
    "HÀI → tự nhiên, có nhịp, có thể dùng slang vừa phải.\n"
    "ĐỜI THƯỜNG → nói như người Việt ngoài đời.\n"
    "VLOG → gần gũi, mình/mọi người.\n"
    "CỔ TRANG → trang trọng, đúng thân phận.\n"
    "KIẾM HIỆP → hào sảng, đúng thuật ngữ.\n"
    "TIÊN HIỆP → đúng hệ thống tu luyện.\n"
    "CUNG ĐẤU → phân biệt rõ cấp bậc và thân phận.\n"
    "HÀNH ĐỘNG → ngắn, mạnh, rõ.\n"
    "KINH DỊ → căng thẳng, tiết chế, không làm mất không khí.\n"
    "TRINH THÁM → chính xác, logic.\n"
    "TÂM LÝ → tự nhiên, giữ chiều sâu cảm xúc.\n"
    "ẨM THỰC → tự nhiên, dễ hiểu.\n"
    "CÂU CÁ → dùng đúng tiếng lóng cần thủ.\n"
    "GAME → dùng thuật ngữ game phổ biến.\n"
    "CÔNG NGHỆ → dùng thuật ngữ kỹ thuật chuẩn.\n\n"

    "==================================================\n"
    "XXIII. QUY TẮC KHÔNG ĐƯỢC VI PHẠM\n"
    "==================================================\n"

    "1. Không thêm lời giải thích.\n"
    "2. Không thêm chú thích trong ngoặc.\n"
    "3. Không thêm phiên âm tiếng Trung.\n"
    "4. Không thêm bản dịch tiếng Anh.\n"
    "5. Không thêm nhận xét về bản dịch.\n"
    "6. Không tự ý đổi tên nhân vật.\n"
    "7. Không tự ý đổi số liệu.\n"
    "8. Không tự ý thêm/bớt tình tiết.\n"
    "9. Không dịch word-by-word.\n"
    "10. Không dùng 'tôi/bạn' mặc định.\n"
    "11. Không lạm dụng Hán Việt.\n"
    "12. Không lạm dụng slang Gen Z.\n"
    "13. Không thêm 'nhé/nha/á/hả' vào mọi câu.\n"
    "14. Không biến văn nói thành văn viết cứng nhắc.\n"
    "15. Không biến phim hiện đại thành văn cổ.\n"
    "16. Không biến cổ trang thành tiếng Việt hiện đại nếu làm mất sắc thái.\n"
    "17. Không tự đoán chủ ngữ khi chưa đủ căn cứ.\n"
    "18. Không làm mất sắc thái chửi, mỉa mai, đe dọa hoặc yêu đương.\n\n"

    "==================================================\n"
    "XXIV. QUY TRÌNH SUY LUẬN TRƯỚC KHI DỊCH\n"
    "==================================================\n"

    "Trước khi xuất kết quả, hãy tự thực hiện các bước sau trong đầu:\n\n"

    "BƯỚC 1: Xác định thể loại video.\n"
    "BƯỚC 2: Xác định ai đang nói với ai.\n"
    "BƯỚC 3: Xác định tuổi tác, giới tính và quan hệ xã hội nếu có thể xác định.\n"
    "BƯỚC 4: Xác định cảm xúc của câu.\n"
    "BƯỚC 5: Đọc ngữ cảnh trước/sau.\n"
    "BƯỚC 6: Xác định nghĩa chính xác của từ đa nghĩa/slang/thành ngữ.\n"
    "BƯỚC 7: Kiểm tra thuật ngữ chuyên ngành nếu có.\n"
    "BƯỚC 8: Viết lại thành tiếng Việt tự nhiên.\n"
    "BƯỚC 9: Kiểm tra xem có làm sai nghĩa gốc không.\n"
    "BƯỚC 10: Kiểm tra đại từ nhân xưng.\n"
    "BƯỚC 11: Kiểm tra số liệu/tên riêng.\n"
    "BƯỚC 12: Kiểm tra câu có phù hợp để đọc bằng giọng AI/người thật hay không.\n"
    "BƯỚC 13: Chỉ sau khi hoàn thành tất cả bước trên mới xuất kết quả.\n\n"

    "==================================================\n"
    "XXV. CHỈ THỊ RIÊNG\n"
    "==================================================\n"

    f"{instruction}\n\n"

    "==================================================\n"
    "XXVI. QUY TẮC OUTPUT CỨNG\n"
    "==================================================\n"

    "Input có cấu trúc:\n"
    "ID|NỘI DUNG TIẾNG TRUNG\n\n"

    "Output BẮT BUỘC giữ nguyên chính xác cấu trúc:\n"
    "ID|NỘI DUNG TIẾNG VIỆT\n\n"

    "QUY ĐỊNH:\n"
    "- Giữ nguyên toàn bộ ID.\n"
    "- Không thay đổi thứ tự ID.\n"
    "- Không thêm ID.\n"
    "- Không xóa ID.\n"
    "- Không gộp hai dòng thành một dòng.\n"
    "- Không tách một dòng thành nhiều dòng.\n"
    "- Mỗi input line tương ứng đúng một output line.\n"
    "- Không thêm markdown.\n"
    "- Không thêm dấu ```.\n"
    "- Không thêm tiêu đề.\n"
    "- Không thêm giải thích.\n"
    "- Không thêm nhận xét.\n"
    "- Không thêm bản tiếng Trung.\n"
    "- Chỉ trả về các dòng đã dịch.\n\n"

    "ĐẶC BIỆT:\n"
    "Nếu nội dung gốc đã là tiếng Việt hoặc là tên riêng/thuật ngữ không cần dịch, "
    "hãy giữ nguyên hoặc xử lý tối thiểu thay vì cố dịch sai.\n\n"

    f"NỘI DUNG CẦN DỊCH:\n{corrected_chinese}"
)
        
        logger.info(f"[Pass 2/2] 🌐 Llama đang dịch sang tiếng Việt...")
        text = auth_client.generate_ai(translation_prompt, api_key=api_key, model=PASS2_MODEL)
        if text:
            logger.info(f"  ✅ Dịch xong! (Qwen sửa lỗi + Llama dịch)")
            return text.strip()
        else:
            logger.warning(f"{ai_name} trả về rỗng ở Pass 2, fallback về bản gốc.")
            return payload_text
    except Exception as e:
        logger.error(f"Lỗi khi dịch bằng AI: {e}")
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
        custom_key = api_keys[0] if (api_keys and len(api_keys) > 0) else None
        text = auth_client.generate_ai(prompt, api_key=custom_key)
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

def summarize_review_with_gemini(full_transcript: str, api_keys: list = None) -> str:
    """
    Tóm tắt toàn bộ transcript thành một kịch bản Review Phim lôi cuốn.
    Sử dụng Gemini thông qua Backend Proxy.
    """
    from auth_client import auth_client
    from loguru import logger
    
    prompt = (
        "Bạn là một Reviewer phim kiêm Tiktoker hàng đầu Việt Nam. "
        "Dựa vào đoạn hội thoại/transcript gốc của video tiếng Trung sau đây, hãy viết một kịch bản Review Phim cực kỳ lôi cuốn, giật gân, "
        "hấp dẫn người xem ngay từ giây đầu tiên. Kịch bản này sẽ được AI đọc lên để làm thuyết minh.\n\n"
        "YÊU CẦU BẮT BUỘC:\n"
        "1. Kịch bản dài khoảng 200-400 chữ, tóm tắt toàn bộ cốt truyện một cách kịch tính nhất.\n"
        "2. Sử dụng ngôn ngữ mạng, GenZ, văn phong review phim đặc trưng (ví dụ: 'Cô gái này...', 'Càng về sau...', 'Không thể ngờ...').\n"
        "3. TRẢ VỀ ĐÚNG KỊCH BẢN, không có lời chào, không có giải thích, không có tiêu đề, không có markdown.\n\n"
        f"Transcript gốc:\n{full_transcript}"
    )
    
    try:
        custom_key = api_keys[0] if (api_keys and len(api_keys) > 0) else None
        ai_name = "Groq" if custom_key and custom_key.startswith("gsk_") else "Gemini"
        logger.info(f"Đang gửi toàn bộ Transcript cho {ai_name} để viết kịch bản Review Phim...")
        text = auth_client.generate_ai(prompt, api_key=custom_key)
        if text:
            logger.info(f"{ai_name} đã viết xong kịch bản Review Phim!")
            return text.strip()
        else:
            logger.warning(f"{ai_name} trả về rỗng.")
            return ""
    except Exception as e:
        logger.error(f"Lỗi khi viết kịch bản bằng AI: {e}")
        return ""

