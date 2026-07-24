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
    # Senior tip: Giảm Concurrency xuống 2 để an toàn tuyệt đối với Microsoft Edge TTS
    sem = asyncio.Semaphore(2) 
    
    async def fetch_tts(i, clean_text, temp_file):
        import random
        
        async with sem:
            # Jitter: Khởi động lệch nhịp TRONG LÚC ĐÃ GIỮ SEMAPHORE để tránh Burst Connection
            await asyncio.sleep(random.uniform(0.1, 0.7))
            
            # Khắc phục bug chí mạng của edge-tts: Text kết thúc bằng dấu câu (,) sẽ bị lỗi No audio was received
            clean_text = clean_text.rstrip(",.!?;:- ")
            if not clean_text:
                return False
                
            # Senior tip: Tăng retry lên 3, dùng Timeout để chống treo, và "thay đổi nhẹ text" nếu bị lỗi ảo
            for attempt in range(3): 
                try:
                    # Đổi text bằng ký tự ngắt dòng vô hình để ép Edge TTS không lấy cache cũ bị hỏng
                    text_to_send = clean_text if attempt == 0 else clean_text + ("\r" if attempt == 1 else "\r\n")
                    
                    communicate = edge_tts.Communicate(text_to_send, voice, rate=rate)
                    
                    # CỰC KỲ QUAN TRỌNG: Chống treo vô thời hạn bằng Circuit Breaker (Timeout = 30s để hỗ trợ các câu cực dài)
                    await asyncio.wait_for(communicate.save(temp_file), timeout=30.0)
                    
                    if os.path.exists(temp_file) and os.path.getsize(temp_file) > 0:
                        # Throttling: Ngủ 0.5s trước khi nhả Semaphore để hãm tốc độ tải toàn hệ thống
                        await asyncio.sleep(0.5)
                        return True
                        
                except asyncio.TimeoutError:
                    # Nếu bị treo quá 12s, ép ngắt và thử lại ngay lập tức
                    if attempt == 2:
                        logger.warning(f"TTS segment {i} timeout ({clean_text[:30]}). Bỏ qua!")
                    await asyncio.sleep(1.0)
                    
                except Exception as e:
                    err_msg = str(e)
                    if attempt == 2:
                        logger.warning(f"TTS segment {i} failed ({clean_text[:30]}): {err_msg}")
                    
                    if "No audio was received" in err_msg:
                        # Lỗi do rate limit hoặc text có vấn đề. Nghỉ vài giây rồi retry
                        await asyncio.sleep(random.uniform(2.0, 4.0))
                    else:
                        await asyncio.sleep(random.uniform(1.0, 2.0))
            
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
    
    # 3. Ghép audio tuần tự (chống đè giọng / multiple voices) và Ép khớp thời gian (Anti-Drifting)
    final_audio = AudioSegment.silent(duration=0)
    current_ms = 0
    segments_created = 0

    for idx, (data, success) in enumerate(zip(sub_data, results)):
        if not success:
            continue
            
        start_ms = data["start_ms"]
        temp_file = data["temp_file"]
        
        # Tính toán thời gian tối đa cho phép trước khi câu tiếp theo bắt đầu
        next_start_ms = total_ms
        for next_idx in range(idx + 1, len(sub_data)):
            if results[next_idx]: # Nếu câu tiếp theo có audio
                next_start_ms = sub_data[next_idx]["start_ms"]
                break
                
        # Khoảng trống tối đa để đọc câu này (tính bằng ms)
        available_time_ms = next_start_ms - start_ms
        if available_time_ms <= 0:
            available_time_ms = 100 # Safe fallback
            
        try:
            seg_audio = AudioSegment.from_mp3(temp_file)

            # Nếu Audio dài hơn Khoảng trống cho phép -> Bắt buộc phải ép tốc độ (để không bị trễ nhịp / đè giọng)
            if len(seg_audio) > available_time_ms:
                speed_factor = len(seg_audio) / available_time_ms
                
                # Gọi FFmpeg atempo để nén tốc độ mà không bị méo giọng (Chipmunk)
                import subprocess
                fast_file = temp_file.replace(".mp3", "_fast.mp3")
                
                # FFmpeg atempo hỗ trợ từ 0.5 đến 100.0, có thể dùng nhiều filter nếu cần nhưng bản mới đã hỗ trợ > 2.0
                cmd = [
                    "ffmpeg", "-y", "-i", temp_file,
                    "-filter:a", f"atempo={speed_factor:.3f}",
                    fast_file
                ]
                try:
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                    seg_audio = AudioSegment.from_mp3(fast_file)
                    try: os.remove(fast_file)
                    except: pass
                except Exception as e:
                    logger.warning(f"FFmpeg atempo failed for {temp_file}: {e}")
                    
                # Cắt gọt chuẩn xác 100% lỡ FFmpeg bị lệch vài mili-giây
                if len(seg_audio) > available_time_ms:
                    seg_audio = seg_audio[:available_time_ms]

            # Nếu đoạn sub này bắt đầu sau khi câu trước đã kết thúc (có khoảng lặng) -> Chèn khoảng lặng
            if start_ms > current_ms:
                silence_gap = start_ms - current_ms
                final_audio += AudioSegment.silent(duration=silence_gap)
                current_ms = start_ms
            elif start_ms < current_ms:
                # Nếu bị trễ vài ms do sai số float, cắt bỏ phần thừa để ép đúng start_ms
                final_audio = final_audio[:start_ms]
                current_ms = start_ms

            # Nối tiếp đoạn audio vào
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
