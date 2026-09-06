"""
Subtitle Detector - Tự động phát hiện vị trí phụ đề gốc (Hardsub) trong video bằng Computer Vision (OpenCV).
Hỗ trợ thông minh cả Video Dọc (Portrait 9:16) và Video Ngang (Landscape 16:9).
Lọc độ sáng chữ (Bright Text Mask) kết hợp Canny Edge để chống nhận nhầm cổ áo / quần áo / bối cảnh.
Tốc độ xử lý siêu tốc < 0.25s.
"""

import os
from typing import Tuple
from loguru import logger

# Preset mặc định theo tỉ lệ khung hình
DEFAULT_PORTRAIT_SUB_Y = (0.72, 0.085)   # Video dọc: cách đáy ~20% (ngang ngực nhân vật)
DEFAULT_LANDSCAPE_SUB_Y = (0.90, 0.080)  # Video ngang: sát mép dưới cùng (chuẩn phim/drama)


def detect_subtitle_y_range(
    video_path: str,
    search_y_min: float = None,
    search_y_max: float = None,
    num_samples: int = 15,
    blur_padding: float = 0.015
) -> Tuple[float, float]:
    """
    Tự động dò tìm tọa độ Y của dòng phụ đề hardsub tiếng Trung trong video.
    
    Args:
        video_path: Đường dẫn tới file video (.mp4)
        search_y_min: Giới hạn trên của vùng quét (None = tự động theo tỉ lệ video)
        search_y_max: Giới hạn dưới của vùng quét (None = tự động theo tỉ lệ video)
        num_samples: Số lượng khung hình mẫu cần trích xuất phân tích
        blur_padding: Khoảng đệm an toàn mở rộng dải làm mờ
        
    Returns:
        tuple (y_start_ratio, height_ratio):
            y_start_ratio: Tọa độ Y bắt đầu dải mờ (0.0 -> 1.0)
            height_ratio: Chiều cao của dải mờ (0.0 -> 1.0)
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

        if total_frames <= 0 or orig_h <= 0 or orig_w <= 0:
            return DEFAULT_PORTRAIT_SUB_Y

        is_landscape = (orig_w > orig_h)
        default_preset = DEFAULT_LANDSCAPE_SUB_Y if is_landscape else DEFAULT_PORTRAIT_SUB_Y

        # Xác định vùng quét thích ứng theo tỉ lệ khung hình
        if search_y_min is None:
            # Video ngang: Phụ đề luôn ở sát đáy (80% -> 98.5%)
            # Video dọc: Phụ đề từ ngang ngực xuống (48% -> 92% bao gồm cả sub 2 dòng)
            search_y_min = 0.80 if is_landscape else 0.48
            
        if search_y_max is None:
            search_y_max = 0.985 if is_landscape else 0.92

        # Downscale frame về chiều rộng 360px để tăng tốc độ xử lý gấp 5-10 lần
        target_w = 360
        scale = target_w / float(orig_w)
        target_h = int(orig_h * scale)

        # Rải đều các frame mẫu từ 10% đến 90% thời lượng video
        frame_indices = np.linspace(
            int(total_frames * 0.1),
            int(total_frames * 0.9),
            num_samples
        ).astype(int)

        edge_accum = np.zeros(target_h, dtype=np.float32)
        valid_frames = 0

        # Chỉ quét phần giữa theo chiều ngang (15% -> 85%) để loại bỏ watermark/icon ở mép
        w_crop_start = int(target_w * 0.15)
        w_crop_end = int(target_w * 0.85)

        for f_idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            # Resize siêu tốc và chuyển xám
            resized = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_NEAREST)
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

            # Lọc các điểm ảnh sáng đặc trưng của chữ phụ đề (độ sáng >= 180)
            _, bright_mask = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)

            # Canny edge detector: Bắt cạnh chữ sắc nét
            edges = cv2.Canny(gray, 80, 180)

            # Chỉ giữ lại cạnh thuộc về vùng chữ sáng
            text_edges = cv2.bitwise_and(edges, edges, mask=bright_mask)

            # Cộng dồn mật độ cạnh theo từng hàng Y ở dải ngang giữa
            horiz_profile = np.sum(text_edges[:, w_crop_start:w_crop_end] > 0, axis=1)
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

        # Ngưỡng phát hiện hàng chứa chữ: cao hơn baseline 5%
        thresh = baseline + (peak_val - baseline) * 0.05

        # Cho phép bắc cầu qua khoảng cách giữa 2 dòng (tối đa 3.5% chiều cao video ~ 25px)
        max_gap_allowed_px = int(target_h * 0.035)
        max_reach_px = int(target_h * 0.16)

        # Quét lên trên từ peak_idx để tìm điểm bắt đầu của khối chữ (bao trọn dòng trên)
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

        # Quét xuống dưới từ peak_idx để tìm điểm kết thúc của khối chữ (bao trọn dòng dưới)
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

        # Thêm padding an toàn ở cả mép trên và dưới
        pad_px = int(target_h * blur_padding)
        y_start_px = max(0, sub_top_px - pad_px)
        y_end_px = min(target_h, sub_bottom_px + pad_px)

        y_start_ratio = y_start_px / float(target_h)
        height_ratio = (y_end_px - y_start_px) / float(target_h)

        # Giới hạn an toàn: video dọc từ 8.5% đến 18%, video ngang từ 7.5% đến 12%
        min_h = 0.075 if is_landscape else 0.085
        max_h = 0.12 if is_landscape else 0.18
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
