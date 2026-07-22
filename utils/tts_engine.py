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

    # Tạo audio track im lặng dài bằng video
    total_ms = int(video_duration * 1000)
    final_audio = AudioSegment.silent(duration=total_ms)

    temp_dir = tempfile.mkdtemp(prefix="tts_")
    segments_created = 0

    for i, sub in enumerate(subs):
        text = sub.text.strip()
        if not text or len(text) < 2:
            continue

        start_ms = sub.start.ordinal  # Thời điểm bắt đầu (ms)
        end_ms = sub.end.ordinal      # Thời điểm kết thúc (ms)
        segment_duration_ms = end_ms - start_ms

        if segment_duration_ms <= 0:
            continue

        # Dọn dẹp text: xóa dấu chấm lửng, ký tự lạ để tránh lỗi TTS server
        clean_text = text.replace("...", ",").replace("..", ",").replace("~", "").strip()
        if not clean_text:
            continue

        temp_file = os.path.join(temp_dir, f"seg_{i:04d}.mp3")
        success = False
        
        # Thử lại tối đa 3 lần nếu server Microsoft trả lỗi (rate limit / no audio)
        for attempt in range(3):
            try:
                communicate = edge_tts.Communicate(clean_text, voice, rate=rate)
                await communicate.save(temp_file)
                if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
                    success = True
                    break
            except Exception as e:
                if attempt == 2:
                    logger.warning(f"TTS segment {i} failed after 3 attempts ({clean_text[:30]}): {e}")
            await asyncio.sleep(0.5) # Nghỉ nửa giây trước khi thử lại
            
        if not success:
            continue

        try:
            # Load audio segment
            seg_audio = AudioSegment.from_mp3(temp_file)

            # Nếu audio dài hơn khoảng thời gian sub → tăng tốc nhẹ (tối đa 1.25x) để nghe tự nhiên
            if len(seg_audio) > segment_duration_ms and segment_duration_ms > 200:
                speed_factor = len(seg_audio) / segment_duration_ms
                if speed_factor > 1.25:
                    speed_factor = 1.25 # Khóa tốc độ tối đa là 1.25x để không bị líu lưỡi
                
                seg_audio = _speed_up_audio(seg_audio, speed_factor)
                # Chú ý: Không cắt bớt (truncate) audio nữa, cứ để nó đọc tràn ra tự nhiên
                # Việc này sẽ giúp giọng đọc hoàn chỉnh câu thay vì bị ngắt giữa chừng hoặc quá nhanh.

            # Overlay vào đúng vị trí timeline
            if start_ms < total_ms:
                # Đảm bảo final_audio đủ dài để chứa đoạn audio bị tràn
                end_pos = start_ms + len(seg_audio)
                if end_pos > len(final_audio):
                    # Thêm khoảng lặng vào cuối để kéo dài final_audio
                    silence_needed = end_pos - len(final_audio)
                    final_audio += AudioSegment.silent(duration=silence_needed)
                    
                final_audio = final_audio.overlay(seg_audio, position=start_ms)
                segments_created += 1

        except Exception as e:
            logger.warning(f"TTS segment {i} processing failed: {e}")
            continue
        finally:
            # Cleanup temp file
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass

    # Cleanup temp dir
    try:
        os.rmdir(temp_dir)
    except OSError:
        pass

    if segments_created == 0:
        logger.warning("Không tạo được segment TTS nào.")
        return None

    # Export file audio cuối cùng
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

        # Đảm bảo cùng độ dài
        if len(voiceover) < len(original):
            voiceover = voiceover + AudioSegment.silent(
                duration=len(original) - len(voiceover)
            )
        elif len(voiceover) > len(original):
            voiceover = voiceover[: len(original)]

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
