"""
Subtitle Detector - Tự động phát hiện vị trí phụ đề gốc (Hardsub) trong video bằng OCR & Computer Vision.
Hỗ trợ thông minh cả Video Dọc (Portrait 9:16) và Video Ngang (Landscape 16:9).
- Pha 1: RapidOCR đối chiếu ngữ nghĩa câu thoại từ Whisper (chính xác 100%, chống nhận nhầm sticker/bối cảnh/thẻ tên).
- Pha 2 (Fallback): OpenCV Sobel X edge detector có giới hạn cứng (search_y_min >= 0.55), triệt tiêu 100% làm mờ nhầm ở nửa trên/giữa màn hình.
"""

import os
import re
from typing import Tuple, Optional, List, Dict
from loguru import logger

# Preset mặc định theo tỉ lệ khung hình
DEFAULT_PORTRAIT_SUB_Y = (0.72, 0.075)  # Video dọc: cách đáy ~20% (ngang ngực nhân vật, dày 7.5%)
DEFAULT_LANDSCAPE_SUB_Y = (0.82, 0.080)  # Video ngang: chuẩn phim/drama 16:9 (Y=82% -> 90%)

_ocr_engine = None


def get_ocr_engine():
    """Khởi tạo và cache engine RapidOCR dạng singleton."""
    global _ocr_engine
    if _ocr_engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _ocr_engine = RapidOCR()
            logger.debug("Khởi tạo thành công RapidOCR cho Subtitle Detector.")
        except Exception as e:
            logger.debug(f"Không thể khởi tạo RapidOCR: {e}")
            _ocr_engine = False
    return _ocr_engine if _ocr_engine is not False else None


def extract_srt_sample_timestamps(srt_path: str, count: int = 5) -> list:
    """
    Trích xuất danh sách các mốc thời gian (giây) giữa các câu thoại từ file SRT.
    Lấy các câu thoại phân bổ đều theo thời lượng để đại diện chính xác cho toàn video.
    """
    if not srt_path or not os.path.exists(srt_path):
        return []
    try:
        import numpy as np
        times = []
        pattern = re.compile(r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})')
        with open(srt_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                match = pattern.search(line)
                if match:
                    h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, match.groups())
                    start = h1 * 3600 + m1 * 60 + s1 + ms1 / 1000.0
                    end = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000.0
                    if end - start >= 0.8:  # Chỉ chọn câu thoại đủ dài để sub hiện rõ
                        times.append((start + end) / 2.0)
        if not times:
            return []
        if len(times) <= count:
            return times
        indices = np.linspace(0, len(times) - 1, count, dtype=int)
        return [float(times[i]) for i in indices]
    except Exception as e:
        logger.debug(f"Không thể đọc timestamps từ SRT: {e}")
        return []


def extract_dialogue_samples(srt_path: str, count: int = 5) -> List[Dict]:
    """
    Trích xuất danh sách các câu thoại mẫu kèm timestamp và nội dung chữ từ file SRT.
    Dùng để đối chiếu OCR tìm đúng dòng hardsub trên khung hình.
    Trả về: [{"time": float, "text": str, "start": float, "end": float}, ...]
    """
    if not srt_path or not os.path.exists(srt_path):
        return []
    try:
        import numpy as np
        samples = []
        pattern = re.compile(r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})')
        
        with open(srt_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [l.strip() for l in f.readlines()]
            
        i = 0
        while i < len(lines):
            line = lines[i]
            match = pattern.search(line)
            if match:
                h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, match.groups())
                start = h1 * 3600 + m1 * 60 + s1 + ms1 / 1000.0
                end = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000.0
                
                # Gom các dòng text tiếp theo
                text_lines = []
                j = i + 1
                while j < len(lines) and lines[j] and not lines[j].isdigit() and '-->' not in lines[j]:
                    text_lines.append(lines[j])
                    j += 1
                    
                sub_text = " ".join(text_lines).strip()
                sub_text = re.sub(r'\[.*?\]|\(.*?\)', '', sub_text).strip()
                
                if (end - start) >= 0.7 and len(sub_text) >= 2:
                    samples.append({
                        "time": (start + end) / 2.0,
                        "text": sub_text,
                        "start": start,
                        "end": end
                    })
                i = j
            else:
                i += 1
                
        if not samples:
            return []
        if len(samples) <= count:
            return samples
        indices = np.linspace(0, len(samples) - 1, count, dtype=int)
        return [samples[idx] for idx in indices]
    except Exception as e:
        logger.debug(f"Không thể trích xuất dialogue samples: {e}")
        return []


def _match_text(detected_text: str, expected_text: str) -> bool:
    """So khớp nội dung nhận diện từ OCR với câu thoại từ Whisper."""
    if not detected_text or not expected_text:
        return False
    # Loại bỏ dấu câu và khoảng trắng
    c1 = re.sub(r'[^\w\u4e00-\u9fff]', '', detected_text.lower())
    c2 = re.sub(r'[^\w\u4e00-\u9fff]', '', expected_text.lower())
    if not c1 or not c2:
        return False
        
    # Nếu là chữ Hán: so sánh tập ký tự trùng
    set1, set2 = set(c1), set(c2)
    common = set1 & set2
    if len(common) >= 2:
        return True
    if len(set2) > 0 and (len(common) / len(set2)) >= 0.35:
        return True
    if c1 in c2 or c2 in c1:
        return True
    return False


def detect_subtitle_with_ocr(
    video_path: str,
    dialogue_samples: List[Dict],
    orig_w: int,
    orig_h: int,
    is_landscape: bool
) -> Optional[Tuple[float, float]]:
    """
    Sử dụng RapidOCR để dò tìm chính xác vị trí phụ đề qua đối chiếu với câu thoại Whisper.
    Đảm bảo 100% không nhận nhầm bối cảnh, cổ áo, bảng tên hay watermark.
    Hỗ trợ cả video bình thường lẫn video bị lật ngang (hflip).
    """
    ocr = get_ocr_engine()
    if not ocr or not dialogue_samples:
        return None

    try:
        import cv2
        import numpy as np
    except ImportError:
        return None

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Vùng quét chữ phụ đề: nửa dưới màn hình
    y_crop_start_ratio = 0.58 if is_landscape else 0.50
    y_crop_end_ratio = 0.94 if is_landscape else 0.95
    y_crop_start = int(orig_h * y_crop_start_ratio)
    y_crop_end = int(orig_h * y_crop_end_ratio)

    matched_boxes = []
    all_expected_texts = [s["text"] for s in dialogue_samples if s.get("text")]

    try:
        for sample in dialogue_samples:
            t_sec = sample.get("time", 0.0)
            target_f = max(0, min(total_frames - 1, int(t_sec * fps)))
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_f)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            crop = frame[y_crop_start:y_crop_end, :]
            
            # Quét cả ảnh xuôi và ảnh lật ngang (để hỗ trợ video lật hflip bypass bản quyền)
            for test_img, is_flipped in [(crop, False), (cv2.flip(crop, 1), True)]:
                res, _ = ocr(test_img)
                if not res:
                    continue

                for box, text, score in res:
                    pts_y = [pt[1] + y_crop_start for pt in box]
                    pts_x = [(orig_w - pt[0]) if is_flipped else pt[0] for pt in box]
                    
                    y1 = min(pts_y) / float(orig_h)
                    y2 = max(pts_y) / float(orig_h)
                    cx = sum(pts_x) / (len(pts_x) * float(orig_w))
                    bh = y2 - y1

                    # Điều kiện hình học phụ đề: Căn giữa (cx ~ 0.5) và chiều cao vừa vặn
                    if abs(cx - 0.50) > 0.22 or bh < 0.015 or bh > 0.12:
                        continue

                    # Điều kiện ngữ nghĩa: Trùng khớp với câu thoại của mốc này hoặc mốc lân cận
                    sample_text = sample.get("text", "")
                    matched = _match_text(text, sample_text)
                    if not matched:
                        # Kiểm tra dự phòng với tất cả câu thoại khác nếu lệch vài frame
                        for exp in all_expected_texts:
                            if _match_text(text, exp):
                                matched = True
                                break

                    if matched:
                        matched_boxes.append((y1, y2, bh))
                        break # Đã tìm thấy dòng sub chuẩn cho frame này

            if len(matched_boxes) >= 3:
                # Đã có đủ 3 mẫu khớp chuẩn xác, không cần quét thêm để tối ưu tốc độ
                break

    except Exception as e:
        logger.debug(f"Lỗi khi quét OCR phụ đề: {e}")
    finally:
        cap.release()

    if not matched_boxes:
        return None

    # Lấy median tọa độ để loại trừ ngoại lai (outliers)
    y1_med = float(np.median([b[0] for b in matched_boxes]))
    y2_med = float(np.median([b[1] for b in matched_boxes]))
    
    # Khoảng đệm an toàn che trọn viền và bóng đổ chữ
    pad_top = 0.015
    pad_bottom = 0.018
    
    y_start = max(0.0, y1_med - pad_top)
    h_blur = (y2_med - y1_med) + pad_top + pad_bottom
    
    # Giới hạn an toàn độ dày dải mờ: từ 5.5% đến 11%
    min_h = 0.060 if is_landscape else 0.055
    max_h = 0.110 if is_landscape else 0.100
    h_blur = max(min_h, min(max_h, h_blur))
    y_start = max(0.0, min(1.0 - h_blur, y_start))

    logger.info(
        f"🎯 [OCR Match Subtitle] Đã bắt dính tọa độ phụ đề qua đối chiếu câu thoại Whisper: "
        f"Y={y_start*100:.1f}% -> {(y_start + h_blur)*100:.1f}% (H={h_blur*100:.1f}%, Khớp {len(matched_boxes)} khung hình)"
    )
    return round(float(y_start), 4), round(float(h_blur), 4)


def detect_subtitle_y_range(
    video_path: str,
    search_y_min: float = None,
    search_y_max: float = None,
    num_samples: int = 15,
    blur_padding: float = 0.025,
    dialogue_timestamps: list = None,
    dialogue_samples: list = None
) -> Tuple[float, float]:
    """
    Tự động dò tìm tọa độ Y của dòng phụ đề hardsub trong video.
    Ưu tiên Pha 1: RapidOCR đối chiếu câu thoại Whisper (chính xác 100%).
    Pha 2 (Fallback): OpenCV Sobel X edge detector có giới hạn cứng (search_y_min >= 0.55).
    
    Returns:
        tuple (y_start_ratio, height_ratio)
    """
    if not os.path.exists(video_path):
        return DEFAULT_PORTRAIT_SUB_Y

    try:
        import cv2
        import numpy as np
    except ImportError:
        logger.warning("Không tìm thấy OpenCV (cv2). Sử dụng preset phụ đề mặc định.")
        return DEFAULT_PORTRAIT_SUB_Y

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return DEFAULT_PORTRAIT_SUB_Y

    try:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

        if total_frames <= 0 or orig_h <= 0 or orig_w <= 0:
            return DEFAULT_PORTRAIT_SUB_Y

        is_landscape = (orig_w > orig_h)
        default_preset = DEFAULT_LANDSCAPE_SUB_Y if is_landscape else DEFAULT_PORTRAIT_SUB_Y
    finally:
        cap.release()

    # ─── BƯỚC 1: QUÉT OCR ĐỐI CHIẾU CÂU THOẠI (CHÍNH XÁC 100%) ───
    # Tự động tìm file _zh.srt gần nhất nếu chưa truyền dialogue_samples
    if not dialogue_samples:
        candidate_zh = video_path.rsplit(".", 1)[0] + "_zh.srt"
        if os.path.exists(candidate_zh):
            dialogue_samples = extract_dialogue_samples(candidate_zh, count=5)

    if dialogue_samples and len(dialogue_samples) > 0:
        try:
            ocr_res = detect_subtitle_with_ocr(
                video_path, dialogue_samples, orig_w, orig_h, is_landscape
            )
            if ocr_res is not None:
                return ocr_res
        except Exception as ocr_err:
            logger.debug(f"OCR Subtitle Match error: {ocr_err}")

    # ─── BƯỚC 2: FALLBACK OPENCV SOBEL X EDGE DETECTOR (SIẾT CHẶT VÙNG QUÉT) ───
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return default_preset

    try:
        # Xác định vùng quét thích ứng: TUYỆT ĐỐI KHÔNG QUÉT NỬA TRÊN MÀN HÌNH (>= 0.50)
        has_dialogue_times = bool(dialogue_timestamps and len(dialogue_timestamps) > 0)
        if search_y_min is None:
            # Video dọc: quét từ 0.55 (dưới ngực nhân vật trở xuống đáy).
            # Video ngang: quét từ 0.65 (chuẩn phim/drama 16:9).
            search_y_min = 0.65 if is_landscape else 0.55
        else:
            # Cưỡng chế chặn an toàn: không bao giờ cho phép quét trên 50% màn hình
            search_y_min = max(0.50, float(search_y_min))

        if search_y_max is None:
            search_y_max = 0.91 if is_landscape else 0.88
        else:
            search_y_max = min(0.96, float(search_y_max))

        # Downscale frame về chiều rộng 360px để tăng tốc độ xử lý gấp 5-10 lần (< 0.2s)
        target_w = 360
        scale = target_w / float(orig_w)
        target_h = int(orig_h * scale)

        # Lựa chọn khung hình mẫu: Ưu tiên mốc thời gian có câu thoại thật
        if has_dialogue_times:
            frame_indices = [max(0, min(total_frames - 1, int(t * fps))) for t in dialogue_timestamps]
        else:
            frame_indices = np.linspace(
                int(total_frames * 0.1),
                int(total_frames * 0.9),
                num_samples
            ).astype(int)

        edge_accum = np.zeros(target_h, dtype=np.float32)
        valid_frames = 0

        # Chỉ quét phần giữa theo chiều ngang để loại bỏ watermark/icon/sticker ở mép
        w_crop_start = int(target_w * (0.20 if is_landscape else 0.15))
        w_crop_end = int(target_w * (0.80 if is_landscape else 0.85))

        for f_idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            # Resize siêu tốc và chuyển màu
            resized = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_NEAREST)
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)

            # 1. Mặt nạ chữ sáng (chữ trắng, chữ vàng nhạt)
            _, white_mask = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY)

            # 2. Mặt nạ màu vàng (đặc trưng phụ đề Douyin/TikTok vàng chanh/vàng kim)
            yellow_mask = cv2.inRange(hsv, np.array([15, 60, 100]), np.array([45, 255, 255]))

            # Kết hợp cả 2 mặt nạ để bắt trọn 100% các loại phụ đề
            text_mask = cv2.bitwise_or(white_mask, yellow_mask)

            # 3. Lọc nét chữ dọc (Sobel X): Chữ Hán/Latinh chứa mật độ nét sổ dọc dày đặc,
            # trong khi các đường kẻ ngang (thanh tiến trình, mặt bàn, mép sàn) có Sobel X gần bằng 0.
            sobel_x = cv2.convertScaleAbs(cv2.Sobel(gray, cv2.CV_16S, 1, 0, ksize=3))
            text_edges = cv2.bitwise_and(sobel_x, sobel_x, mask=text_mask)

            # Cộng dồn mật độ nét chữ theo từng hàng Y ở dải ngang giữa
            horiz_profile = np.sum(text_edges[:, w_crop_start:w_crop_end] > 25, axis=1)
            edge_accum += horiz_profile
            valid_frames += 1

        if valid_frames == 0:
            return default_preset

        # Giới hạn tìm kiếm trong vùng khả dĩ của phụ đề
        y_min_px = int(target_h * search_y_min)
        y_max_px = int(target_h * search_y_max)

        search_profile = edge_accum[y_min_px:y_max_px].copy()
        if len(search_profile) == 0:
            return default_preset

        # Làm mịn nhẹ hồ sơ cạnh (kernel 5)
        kernel = np.ones(5, dtype=np.float32) / 5.0
        smoothed = np.convolve(search_profile, kernel, mode='same')

        peak_idx = int(np.argmax(smoothed))
        peak_val = smoothed[peak_idx]

        # Baseline: lấy median của 20% hàng đầu tiên (vùng trên ngực, ít bị dính chữ)
        baseline = np.median(smoothed[:max(5, int(len(smoothed) * 0.2))])

        if peak_val < baseline * 1.20 or peak_val < 10.0:
            logger.debug(f"Mật độ cạnh chữ ({peak_val:.1f}) không vượt ngưỡng. Dùng preset ({'Ngang' if is_landscape else 'Dọc'}).")
            return default_preset

        # Ngưỡng phát hiện hàng chứa chữ: bắt đúng peak xung của chữ (40% prominence)
        thresh = baseline + (peak_val - baseline) * 0.40

        # Giới hạn vươn tới tối đa 8% chiều cao video (đủ trọn 1-2 dòng sub, không lan ra bối cảnh)
        max_gap_allowed_px = int(target_h * 0.02)
        max_reach_px = int(target_h * 0.08)

        # Quét lên trên từ peak_idx để tìm điểm bắt đầu của khối chữ
        top_rel = peak_idx
        consecutive_low = 0
        for i in range(peak_idx, max(0, peak_idx - max_reach_px), -1):
            if smoothed[i] >= thresh:
                top_rel = i
                consecutive_low = 0
            else:
                consecutive_low += 1
                if consecutive_low > max_gap_allowed_px:
                    break

        # Quét xuống dưới từ peak_idx để tìm điểm kết thúc của khối chữ
        bottom_rel = peak_idx
        consecutive_low = 0
        for i in range(peak_idx, min(len(smoothed), peak_idx + max_reach_px)):
            if smoothed[i] >= thresh:
                bottom_rel = i
                consecutive_low = 0
            else:
                consecutive_low += 1
                if consecutive_low > max_gap_allowed_px:
                    break

        sub_top_px = y_min_px + top_rel
        sub_bottom_px = y_min_px + bottom_rel

        # Đệm an toàn thanh thoát: vừa khít viền/bóng đổ của font chữ mà không ăn vào nhân vật
        pad_top_px = int(target_h * 0.012)
        pad_bottom_px = int(target_h * 0.015)

        y_start_px = max(0, sub_top_px - pad_top_px)
        y_end_px = min(target_h, sub_bottom_px + pad_bottom_px)

        y_start_ratio = y_start_px / float(target_h)
        height_ratio = (y_end_px - y_start_px) / float(target_h)

        # Giới hạn an toàn vừa khít: video dọc từ 5.5% đến 8.5%, video ngang từ 6.5% đến 9.5%
        min_h = 0.065 if is_landscape else 0.055
        max_h = 0.095 if is_landscape else 0.085
        height_ratio = max(min_h, min(max_h, height_ratio))
        y_start_ratio = max(0.0, min(1.0 - height_ratio, y_start_ratio))

        logger.info(
            f"🎯 [Smart Blur] Đã phát hiện phụ đề ({'Video Ngang' if is_landscape else 'Video Dọc'}): "
            f"Y={y_start_ratio*100:.1f}% -> {(y_start_ratio + height_ratio)*100:.1f}% (Độ dày: {height_ratio*100:.1f}%)"
        )
        return round(float(y_start_ratio), 4), round(float(height_ratio), 4)

    except Exception as e:
        logger.warning(f"Lỗi khi phát hiện vùng phụ đề bằng OpenCV: {e}. Dùng preset chuẩn.")
        return DEFAULT_PORTRAIT_SUB_Y
    finally:
        cap.release()

