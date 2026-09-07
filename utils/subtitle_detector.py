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
DEFAULT_PORTRAIT_SUB_Y = (0.72, 0.075)  # Video dọc: cách đáy ~20% (ngang ngực nhân vật, dày 7.5%)
DEFAULT_LANDSCAPE_SUB_Y = (0.86, 0.085)  # Video ngang: sát mép đáy (chuẩn phim/drama 16:9, dày 8.5%)


def detect_subtitle_y_range(
    video_path: str,
    search_y_min: float = None,
    search_y_max: float = None,
    num_samples: int = 15,
    blur_padding: float = 0.025
) -> Tuple[float, float]:
    """
    Tự động dò tìm tọa độ Y của dòng phụ đề hardsub tiếng Trung trong video.
    Hỗ trợ cả phụ đề màu vàng (Douyin/Kuaishou) và chữ trắng có viền đen.
    Tự động mở rộng dải mờ chạm mép đáy nếu phụ đề nằm sát đáy để không bị lòi chữ bên dưới.
    
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
            # Quét toàn bộ nửa dưới màn hình để không bỏ sót phụ đề 2 dòng hoặc phụ đề cao
            search_y_min = 0.50 if is_landscape else 0.45
            
        if search_y_max is None:
            search_y_max = 0.99

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

            # Resize siêu tốc và chuyển màu
            resized = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_NEAREST)
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)

            # 1. Mặt nạ chữ sáng (chữ trắng, chữ vàng nhạt)
            _, white_mask = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

            # 2. Mặt nạ màu vàng (đặc trưng phụ đề Douyin/TikTok vàng chanh/vàng kim)
            yellow_mask = cv2.inRange(hsv, np.array([15, 60, 100]), np.array([45, 255, 255]))

            # Kết hợp cả 2 mặt nạ để bắt trọn 100% các loại phụ đề
            text_mask = cv2.bitwise_or(white_mask, yellow_mask)

            # Canny edge detector: Bắt cạnh chữ sắc nét
            edges = cv2.Canny(gray, 60, 150)

            # Chỉ giữ lại cạnh thuộc về vùng chữ sáng hoặc vàng
            text_edges = cv2.bitwise_and(edges, edges, mask=text_mask)

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

        # Ngưỡng phát hiện hàng chứa chữ: bắt đúng peak xung của chữ (40% prominence)
        thresh = baseline + (peak_val - baseline) * 0.40

        # Giới hạn vươn tới tối đa 8% chiều cao video (đủ trọn 1-2 dòng sub, không lan ra bối cảnh)
        max_gap_allowed_px = int(target_h * 0.02)
        max_reach_px = int(target_h * 0.08)

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

        # Đệm an toàn thanh thoát: vừa khít viền/bóng đổ của font chữ mà không ăn vào nhân vật
        pad_top_px = int(target_h * 0.010)
        pad_bottom_px = int(target_h * 0.015)

        y_start_px = max(0, sub_top_px - pad_top_px)
        y_end_px = min(target_h, sub_bottom_px + pad_bottom_px)

        # Nếu mép dưới dải mờ ăn sát chạm đáy (>= 96%) thì mới kéo chạm mép đáy
        if (y_end_px / float(target_h)) >= 0.96:
            y_end_px = target_h

        y_start_ratio = y_start_px / float(target_h)
        height_ratio = (y_end_px - y_start_px) / float(target_h)

        # Giới hạn an toàn vừa khít: video dọc từ 5.5% đến 8.5%, video ngang từ 6.0% đến 9.5%
        min_h = 0.060 if is_landscape else 0.055
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
