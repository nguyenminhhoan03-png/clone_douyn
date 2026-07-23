"""
TTS Engine - Tạo giọng thuyết minh tiếng Việt từ file SRT
Sử dụng edge-tts (Microsoft TTS miễn phí, giọng cực tự nhiên).
Giọng hỗ trợ tiếng Việt:
  - vi-VN-HoaiMyNeural  (nữ, tự nhiên)
  - vi-VN-NamMinhNeural  (nam, tự nhiên)
"""
import asyncio
import os
import tempfile
from pathlib import Path
from typing import Optional

from loguru import logger


def generate_voiceover_from_srt(
    srt_path: str,
    output_audio_path: str,
    video_duration: float,
    voice: str = "vi-VN-HoaiMyNeural",
    rate: str = "+0%",
) -> Optional[str]:
    """
    Đọc file SRT tiếng Việt → tạo file audio thuyết minh khớp timeline video.

    Args:
        srt_path: Đường dẫn file .srt tiếng Việt
        output_audio_path: Đường dẫn file audio output (.mp3)
        video_duration: Tổng thời lượng video (giây)
        voice: Giọng TTS (mặc định: vi-VN-HoaiMyNeural - giọng nữ)
        rate: Tốc độ đọc (vd: "+0%", "+10%", "-10%")

    Returns:
        Đường dẫn file audio đã tạo, hoặc None nếu lỗi
    """
    try:
        return asyncio.run(
            _async_generate_voiceover(
                srt_path, output_audio_path, video_duration, voice, rate
            )
        )
    except Exception as e:
        logger.error(f"TTS Engine error: {e}")
        return None


async def _async_generate_voiceover(
    srt_path: str,
    output_audio_path: str,
    video_duration: float,
    voice: str,
    rate: str,
) -> Optional[str]:
    """Async implementation: đọc SRT → tạo audio segments → ghép thành 1 file."""
    try:
        import edge_tts
        import pysrt
        from pydub import AudioSegment
    except ImportError as e:
        logger.error(f"Thiếu thư viện: {e}. Chạy: pip install edge-tts pysrt pydub")
        return None

    subs = pysrt.open(srt_path)
    if not subs:
        logger.warning("File SRT trống, không tạo được voiceover.")
        return None

    total_ms = int(video_duration * 1000)
    temp_dir = tempfile.mkdtemp(prefix="tts_")
    
    # 1. Chuẩn bị danh sách các task cần tải
    tasks = []
    sem = asyncio.Semaphore(3) # Giảm xuống 3 để tránh bị Microsoft Rate Limit chặn "No audio was received"
    
    async def fetch_tts(i, clean_text, temp_file):
        import random
        
        async with sem:
            for attempt in range(5): # Thử lại tối đa 5 lần thay vì 3
                try:
                    communicate = edge_tts.Communicate(clean_text, voice, rate=rate)
                    await communicate.save(temp_file)
                    if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
                        return True
                except Exception as e:
                    if attempt == 4:
                        logger.warning(f"TTS segment {i} failed after 5 attempts ({clean_text[:30]}): {e}")
                
                # Exponential backoff + Jitter: Đợi lâu hơn ở các lần thất bại tiếp theo để tránh spam server
                delay = (1.5 ** attempt) + random.uniform(0.5, 1.5)
                await asyncio.sleep(delay)
            return False

    sub_data = []
    for i, sub in enumerate(subs):
        text = sub.text.strip()
        if not text or len(text) < 2:
            continue

        start_ms = sub.start.ordinal
        end_ms = sub.end.ordinal
        segment_duration_ms = end_ms - start_ms

        if segment_duration_ms <= 0:
            continue

        import re
        # Loại bỏ emoji và các ký tự đặc biệt không đọc được để tránh AI đổi giọng tiếng Anh
        clean_text = re.sub(r'[^\w\s\.,!\?àáãạảăắằẳẵặâấầẩẫậèéẹẻẽêềếểễệđìíĩỉịòóõọỏôốồổỗộơớờởỡợùúũụủưứừửữựỳỵỷỹýÀÁÃẠẢĂẮẰẲẴẶÂẤẦẨẪẬÈÉẸẺẼÊỀẾỂỄỆĐÌÍĨỈỊÒÓÕỌỎÔỐỒỔỖỘƠỚỜỞỠỢÙÚŨỤỦƯỨỪỬỮỰỲỴỶỸÝ]', '', text)
        clean_text = clean_text.replace("...", ",").replace("..", ",").strip()
        
        if not clean_text:
            continue

        temp_file = os.path.join(temp_dir, f"seg_{i:04d}.mp3")
        tasks.append(fetch_tts(i, clean_text, temp_file))
        sub_data.append({
            "index": i,
            "start_ms": start_ms,
            "segment_duration_ms": segment_duration_ms,
            "temp_file": temp_file
        })

    # 2. Tải tất cả audio segments đồng thời
    results = await asyncio.gather(*tasks)
    
    # 3. Ghép audio tuần tự (chống đè giọng / multiple voices)
    final_audio = AudioSegment.silent(duration=0)
    current_ms = 0
    segments_created = 0

    for data, success in zip(sub_data, results):
        if not success:
            continue
            
        start_ms = data["start_ms"]
        segment_duration_ms = data["segment_duration_ms"]
        temp_file = data["temp_file"]
        
        try:
            seg_audio = AudioSegment.from_mp3(temp_file)

            # Ép tốc độ nếu đoạn đọc quá dài so với sub (tối đa 1.35x để không bị quéo giọng)
            if len(seg_audio) > segment_duration_ms and segment_duration_ms > 200:
                speed_factor = len(seg_audio) / segment_duration_ms
                if speed_factor > 1.35:
                    speed_factor = 1.35
                seg_audio = _speed_up_audio(seg_audio, speed_factor)

            # Nếu đoạn sub này bắt đầu sau khi câu trước đã đọc xong -> Chèn khoảng lặng
            if start_ms > current_ms:
                silence_gap = start_ms - current_ms
                final_audio += AudioSegment.silent(duration=silence_gap)
                current_ms = start_ms

            # Nối tiếp đoạn audio vào (TUYỆT ĐỐI KHÔNG DÙNG OVERLAY)
            final_audio += seg_audio
            current_ms += len(seg_audio)
            
            segments_created += 1

        except Exception as e:
            logger.warning(f"TTS segment {data['index']} processing failed: {e}")
        finally:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass

    try:
        os.rmdir(temp_dir)
    except OSError:
        pass

    if segments_created == 0:
        logger.warning("Không tạo được segment TTS nào.")
        return None

    # Đảm bảo audio dài bằng video_duration
    if len(final_audio) < total_ms:
        final_audio += AudioSegment.silent(duration=total_ms - len(final_audio))
    elif len(final_audio) > total_ms:
        final_audio = final_audio[:total_ms]

    final_audio.export(output_audio_path, format="mp3", bitrate="192k")
    logger.info(
        f"✅ TTS voiceover created: {segments_created} segments → {output_audio_path}"
    )
    return output_audio_path


def _speed_up_audio(audio_segment, factor: float):
    """Tăng tốc audio bằng cách thay đổi frame_rate rồi convert lại.
    Cách này giữ pitch tương đối ổn cho factor nhỏ (1.0-1.5x)."""
    from pydub import AudioSegment

    # Tăng frame_rate → audio nhanh hơn + pitch cao hơn
    sound_with_altered_frame_rate = audio_segment._spawn(
        audio_segment.raw_data,
        overrides={"frame_rate": int(audio_segment.frame_rate * factor)},
    )
    # Convert lại về frame_rate chuẩn
    return sound_with_altered_frame_rate.set_frame_rate(audio_segment.frame_rate)


def mix_audio_tracks(
    original_audio_path: str,
    voiceover_audio_path: str,
    output_path: str,
    original_volume: float = 0.2,
) -> Optional[str]:
    """
    Mix audio gốc (giảm volume) + audio thuyết minh → 1 file audio.

    Args:
        original_audio_path: Audio gốc từ video
        voiceover_audio_path: Audio thuyết minh TTS
        output_path: Đường dẫn output
        original_volume: Tỉ lệ volume audio gốc (0.0 - 1.0), default 0.2 = 20%

    Returns:
        Đường dẫn file audio đã mix
    """
    try:
        from pydub import AudioSegment

        original = AudioSegment.from_file(original_audio_path)
        voiceover = AudioSegment.from_mp3(voiceover_audio_path)

        # Lặp nhạc nền (original) nếu nó ngắn hơn voiceover
        if len(original) < len(voiceover):
            loops_needed = (len(voiceover) // len(original)) + 1
            original = original * loops_needed

        # Sau đó cắt original cho bằng chính xác độ dài voiceover
        original = original[: len(voiceover)]

        # Giảm volume audio gốc
        # Công thức: dB = 20 * log10(volume_ratio)
        import math

        if original_volume > 0:
            db_reduction = 20 * math.log10(original_volume)
            original = original + db_reduction  # pydub dùng + dB
        else:
            original = AudioSegment.silent(duration=len(original))

        # Tăng volume voiceover nhẹ để rõ hơn
        voiceover = voiceover + 3  # +3dB

        # Mix (overlay)
        mixed = original.overlay(voiceover)
        mixed.export(output_path, format="mp3", bitrate="192k")

        logger.info(f"✅ Audio mixed: original@{original_volume*100:.0f}% + voiceover")
        return output_path

    except Exception as e:
        logger.error(f"Mix audio failed: {e}")
        return None
