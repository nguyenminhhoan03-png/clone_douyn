"""
TTS Engine - Tạo giọng thuyết minh tiếng Việt từ file SRT
Sử dụng edge-tts (Microsoft TTS miễn phí, giọng cực tự nhiên).
Giọng hỗ trợ tiếng Việt:
  - vi-VN-HoaiMyNeural  (nữ, tự nhiên)
  - vi-VN-NamMinhNeural  (nam, tự nhiên)

[Senior+ Optimized]
  - Adaptive retry với exponential backoff thực sự
  - Text chunking: tách câu dài (>150 ký tự) thành nhiều chunk, tránh timeout do payload lớn
  - Tăng concurrency lên 4 với per-request timeout 20s (đủ dài cho câu ngắn, không chờ mãi)
  - Dùng asyncio.Semaphore kết hợp jitter mở rộng để tránh thundering herd với Microsoft server
  - FFmpeg atempo chạy song song qua ThreadPoolExecutor (không block event loop)
  - Cleanup temp files ngay sau khi dùng xong (tiết kiệm disk I/O và RAM)
"""
import asyncio
import os
import re
import sys
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from loguru import logger

# --- Sửa lỗi sập App (WinError 10054) trên Windows do ProactorEventLoop ---
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# ─────────────────────────────────────────────────────────────────────────────
# Constants / Tuning knobs – chỉnh ở đây, không cần sửa sâu trong code
# ─────────────────────────────────────────────────────────────────────────────
_MAX_CONCURRENCY = 2          # Giảm xuống 2 để tránh bị Microsoft Rate Limit / Ban IP
_PER_REQUEST_TIMEOUT = 25.0   # Tăng nhẹ timeout
_MAX_RETRIES = 5              # Số lần retry tối đa mỗi segment
_CHUNK_MAX_CHARS = 150        # Câu dài hơn sẽ bị split thành nhiều chunk
_THROTTLE_AFTER_SUCCESS = 1.0 # Ngủ 1s sau mỗi success để tránh spam request liên tục
_FFMPEG_WORKERS = 4           # ThreadPoolExecutor workers cho FFmpeg atempo


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


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

_VIET_CHARS = (
    r"àáãạảăắằẳẵặâấầẩẫậèéẹẻẽêềếểễệđìíĩỉị"
    r"òóõọỏôốồổỗộơớờởỡợùúũụủưứừửữựỳỵỷỹý"
    r"ÀÁÃẠẢĂẮẰẲẴẶÂẤẦẨẪẬÈÉẸẺẼÊỀẾỂỄỆĐÌÍĨỈỊ"
    r"ÒÓÕỌỎÔỐỒỔỖỘƠỚỜỞỠỢÙÚŨỤỦƯỨỪỬỮỰỲỴỶỸÝ"
)
_CLEAN_RE = re.compile(rf"[^\w\s\.,!?\-{_VIET_CHARS}]")


def _clean_text(raw: str) -> str:
    """Loại bỏ emoji và ký tự không đọc được, chuẩn hoá dấu câu."""
    text = _CLEAN_RE.sub("", raw)
    text = text.replace("...", ",").replace("..", ",").strip()
    # Loại bỏ dấu câu ở cuối (edge-tts bug: kết thúc bằng "," gây No audio)
    text = text.rstrip(",.!?;:- ")
    return text


def _split_into_chunks(text: str, max_chars: int = _CHUNK_MAX_CHARS) -> list[str]:
    """
    Chia câu dài thành các chunk <= max_chars để tránh timeout do payload lớn.
    Ưu tiên cắt tại dấu câu, rồi tại khoảng trắng.
    """
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    # Cắt tại dấu câu trước
    parts = re.split(r"(?<=[,;\.!?])\s+", text)
    current = ""
    for part in parts:
        if len(current) + len(part) + 1 <= max_chars:
            current = f"{current} {part}".strip() if current else part
        else:
            if current:
                chunks.append(current)
            # Nếu part vẫn quá dài, cắt bằng word boundary
            while len(part) > max_chars:
                space_idx = part.rfind(" ", 0, max_chars)
                cut = space_idx if space_idx > 0 else max_chars
                chunks.append(part[:cut].strip())
                part = part[cut:].strip()
            current = part
    if current:
        chunks.append(current)
    return [c for c in chunks if c]


async def _fetch_single_chunk(
    sem: asyncio.Semaphore,
    edge_tts,
    text: str,
    voice: str,
    rate: str,
    out_file: str,
    label: str,
) -> bool:
    """
    Tải 1 chunk text về file .mp3 với retry + exponential backoff.
    Trả về True nếu thành công.
    """
    import random

    async with sem:
        # Jitter khởi động để tránh thundering herd
        await asyncio.sleep(random.uniform(0.05, 0.5))

        for attempt in range(_MAX_RETRIES):
            # Mỗi attempt dùng một biến thể text nhỏ để vượt cache bị hỏng
            suffix = ("", "\r", "\r\n", " ")[attempt % 4]
            try:
                communicate = edge_tts.Communicate(text + suffix, voice, rate=rate)
                await asyncio.wait_for(
                    communicate.save(out_file),
                    timeout=_PER_REQUEST_TIMEOUT,
                )
                if os.path.exists(out_file) and os.path.getsize(out_file) > 0:
                    await asyncio.sleep(_THROTTLE_AFTER_SUCCESS)
                    return True
                # File rỗng – thử lại ngay
                logger.debug(f"TTS {label} attempt {attempt+1}: empty file, retrying…")

            except asyncio.TimeoutError:
                wait = min(2 ** attempt + random.uniform(0, 1), 10.0)
                if attempt == _MAX_RETRIES - 1:
                    logger.warning(
                        f"TTS {label} timeout sau {_MAX_RETRIES} lần thử ({text[:40]}). Bỏ qua!"
                    )
                else:
                    logger.debug(f"TTS {label} attempt {attempt+1} timeout, retry sau {wait:.1f}s…")
                await asyncio.sleep(wait)

            except Exception as exc:
                err = str(exc)
                wait = min(2 ** attempt + random.uniform(0, 1), 10.0)
                if "No audio was received" in err:
                    # Rate-limit hoặc text có vấn đề – nghỉ lâu hơn
                    wait = max(wait, random.uniform(3.0, 6.0))
                if attempt == _MAX_RETRIES - 1:
                    logger.warning(f"TTS {label} failed ({text[:40]}): {err}")
                else:
                    logger.debug(f"TTS {label} attempt {attempt+1} error '{err}', retry sau {wait:.1f}s…")
                await asyncio.sleep(wait)

        return False


def _run_ffmpeg_atempo(temp_file: str, speed_factor: float) -> Optional[str]:
    """
    Chạy FFmpeg atempo ĐỒNG BỘ (dùng trong ThreadPoolExecutor).
    atempo chỉ nhận [0.5, 2.0] mỗi filter; với speed_factor > 2 phải chain 2 filter.
    Trả về path file đã speed-up, hoặc None nếu lỗi.
    """
    fast_file = temp_file.replace(".mp3", "_fast.mp3")

    # Build atempo chain (hỗ trợ speed_factor tuỳ ý)
    if speed_factor <= 2.0:
        atempo_chain = f"atempo={speed_factor:.4f}"
    else:
        # Chia đôi: sqrt(speed_factor) ^ 2
        import math
        half = math.sqrt(speed_factor)
        atempo_chain = f"atempo={half:.4f},atempo={half:.4f}"

    cmd = [
        "ffmpeg", "-y", "-i", temp_file,
        "-filter:a", atempo_chain,
        "-q:a", "2",  # VBR quality thay vì default → nhanh hơn và nhỏ hơn
        fast_file,
    ]
    try:
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return fast_file if os.path.exists(fast_file) and os.path.getsize(fast_file) > 0 else None
    except Exception as exc:
        logger.warning(f"FFmpeg atempo failed for {temp_file}: {exc}")
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
    except ImportError as exc:
        logger.error(f"Thiếu thư viện: {exc}. Chạy: pip install edge-tts pysrt pydub")
        return None

    subs = pysrt.open(srt_path)
    if not subs:
        logger.warning("File SRT trống, không tạo được voiceover.")
        return None

    total_ms = int(video_duration * 1000)
    temp_dir = tempfile.mkdtemp(prefix="tts_")
    sem = asyncio.Semaphore(_MAX_CONCURRENCY)

    # ─── Bước 1: Chuẩn bị danh sách segment ────────────────────────────────
    # Mỗi entry: {"start_ms", "end_ms", "segment_duration_ms", "chunks": [...]}
    # chunk: {"text", "temp_file", "task_coro"}
    sub_data: list[dict] = []
    fetch_tasks: list = []

    for i, sub in enumerate(subs):
        raw_text = sub.text.strip()
        if not raw_text or len(raw_text) < 2:
            continue

        # Phân tích Tag để chuyển đổi giọng nói (Multi-speaker Dubbing)
        current_voice = voice if voice != "Multi" else "vi-VN-HoaiMyNeural"
        import re
        match = re.search(r'\[([MFNmf])\]', raw_text)
        if match:
            tag = match.group(1).upper()
            if tag == 'M':
                current_voice = "vi-VN-NamMinhNeural"
            elif tag == 'F' or tag == 'N':
                current_voice = "vi-VN-HoaiMyNeural"
            
            # Xóa tag khỏi text
            raw_text = re.sub(r'\[[MFNmf]\]', '', raw_text).strip()

        start_ms = sub.start.ordinal
        end_ms = sub.end.ordinal
        segment_duration_ms = end_ms - start_ms
        if segment_duration_ms <= 0:
            continue

        clean = _clean_text(raw_text)
        if not clean:
            continue

        # Tách câu dài → nhiều chunk để tránh timeout
        chunks_text = _split_into_chunks(clean)
        chunks: list[dict] = []
        for c_idx, chunk_text in enumerate(chunks_text):
            temp_file = os.path.join(temp_dir, f"seg_{i:04d}_c{c_idx}.mp3")
            label = f"seg{i}_c{c_idx}"
            # TRUYỀN current_voice THAY VÌ voice MẶC ĐỊNH CHUNG
            coro = _fetch_single_chunk(sem, edge_tts, chunk_text, current_voice, rate, temp_file, label)
            fetch_tasks.append(coro)
            chunks.append({"text": chunk_text, "temp_file": temp_file})

        sub_data.append({
            "index": i,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "segment_duration_ms": segment_duration_ms,
            "chunks": chunks,
        })

    if not sub_data:
        logger.warning("Không có segment nào hợp lệ để TTS.")
        return None

    logger.info(
        f"  TTS: {len(sub_data)} segments → {len(fetch_tasks)} chunks, "
        f"concurrency={_MAX_CONCURRENCY}, timeout/req={_PER_REQUEST_TIMEOUT}s"
    )

    # ─── Bước 2: Tải TẤT CẢ chunks song song ───────────────────────────────
    results_flat = await asyncio.gather(*fetch_tasks)

    # Map kết quả flat → từng chunk của từng segment
    result_iter = iter(results_flat)
    for entry in sub_data:
        for chunk in entry["chunks"]:
            chunk["success"] = next(result_iter)

    # ─── Bước 3: Ghép các chunk trong cùng một segment → file segment ───────
    # Dùng pydub để nối chunk (nếu segment bị split), lưu lại vào 1 file duy nhất
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=_FFMPEG_WORKERS)

    async def merge_chunks_and_speedup(entry: dict, available_time_ms: int) -> Optional["AudioSegment"]:
        """Ghép chunks của 1 segment, speed-up nếu cần, trả về AudioSegment."""
        from pydub import AudioSegment as AS

        # Ghép các chunk thành công
        merged = AS.silent(duration=0)
        any_success = False
        for chunk in entry["chunks"]:
            if not chunk["success"]:
                continue
            try:
                merged += AS.from_mp3(chunk["temp_file"])
                any_success = True
            except Exception as exc:
                logger.debug(f"Chunk {chunk['temp_file']} load error: {exc}")
            finally:
                try:
                    os.remove(chunk["temp_file"])
                except OSError:
                    pass

        if not any_success or len(merged) == 0:
            return None

        # Speed-up nếu audio dài hơn khoảng trống
        if len(merged) > available_time_ms:
            speed_factor = len(merged) / available_time_ms
            # Giới hạn max speed để tránh giọng méo không nghe được
            speed_factor = min(speed_factor, 2.5)

            # Ghi merged ra file tạm → atempo → đọc lại
            merged_tmp = os.path.join(temp_dir, f"seg_{entry['index']:04d}_merged.mp3")
            merged.export(merged_tmp, format="mp3", bitrate="192k")

            fast_path = await loop.run_in_executor(
                executor, _run_ffmpeg_atempo, merged_tmp, speed_factor
            )
            try:
                os.remove(merged_tmp)
            except OSError:
                pass

            if fast_path:
                try:
                    merged = AS.from_mp3(fast_path)
                    os.remove(fast_path)
                except Exception:
                    pass

            # Trim cứng phòng lệch vài ms
            if len(merged) > available_time_ms:
                merged = merged[:available_time_ms]

        return merged

    # ─── Bước 4: Ghép toàn bộ segments → final audio ────────────────────────
    from pydub import AudioSegment

    final_audio = AudioSegment.silent(duration=0)
    current_ms = 0
    segments_created = 0

    for idx, entry in enumerate(sub_data):
        start_ms = entry["start_ms"]

        # Tính available_time: từ start_ms đến start của segment thành công tiếp theo
        next_start_ms = total_ms
        for nxt in sub_data[idx + 1 :]:
            if any(c["success"] for c in nxt["chunks"]):
                next_start_ms = nxt["start_ms"]
                break
        available_time_ms = max(next_start_ms - start_ms, 100)

        seg_audio = await merge_chunks_and_speedup(entry, available_time_ms)
        if seg_audio is None:
            continue

        # Đặt khoảng lặng hoặc trim để khớp timeline
        if start_ms > current_ms:
            final_audio += AudioSegment.silent(duration=start_ms - current_ms)
            current_ms = start_ms
        elif start_ms < current_ms:
            final_audio = final_audio[:start_ms]
            current_ms = start_ms

        final_audio += seg_audio
        current_ms += len(seg_audio)
        segments_created += 1

    executor.shutdown(wait=False)

    # Cleanup thư mục tạm
    try:
        os.rmdir(temp_dir)
    except OSError:
        pass

    if segments_created == 0:
        logger.warning("Không tạo được segment TTS nào.")
        return None

    # Pad / trim cho khớp video_duration
    if len(final_audio) < total_ms:
        final_audio += AudioSegment.silent(duration=total_ms - len(final_audio))
    elif len(final_audio) > total_ms:
        final_audio = final_audio[:total_ms]

    final_audio.export(output_audio_path, format="mp3", bitrate="192k")
    logger.info(
        f"✅ TTS voiceover created: {segments_created}/{len(sub_data)} segments → {output_audio_path}"
    )
    return output_audio_path


# ─────────────────────────────────────────────────────────────────────────────
# Audio mixing
# ─────────────────────────────────────────────────────────────────────────────

def mix_audio_tracks(
    original_audio_path: str,
    voiceover_audio_path: str,
    output_path: str,
    original_volume: float = 0.35,
) -> Optional[str]:
    """
    Mix audio gốc + audio thuyết minh → 1 file audio.
    Sử dụng kỹ thuật Audio Ducking: Giữ nguyên 100% âm thanh gốc, 
    chỉ hạ xuống `original_volume` (vd 35%) khi giọng AI đang nói.
    """
    try:
        import math
        from pydub import AudioSegment

        original = AudioSegment.from_file(original_audio_path)
        voiceover = AudioSegment.from_mp3(voiceover_audio_path)

        if len(original) < len(voiceover):
            loops_needed = (len(voiceover) // len(original)) + 1
            original = original * loops_needed

        original = original[: len(voiceover)]

        # --- Audio Ducking Logic ---
        # Tính toán mức giảm dB
        if original_volume > 0:
            db_reduction = 20 * math.log10(original_volume)
        else:
            db_reduction = -100.0 # Mute

        chunk_size_ms = 50
        ducked_original_chunks = []
        
        # Ngưỡng RMS để coi là có giọng nói (im lặng thường có RMS rất thấp < 50)
        # Tùy thuộc vào voiceover, có thể tinh chỉnh. TTS im lặng có RMS = 0
        silence_threshold = 10 

        for i in range(0, len(original), chunk_size_ms):
            orig_chunk = original[i:i+chunk_size_ms]
            vo_chunk = voiceover[i:i+chunk_size_ms]
            
            # Nếu voiceover có tiếng (RMS > threshold) thì hạ volume original_chunk
            if vo_chunk.rms > silence_threshold:
                ducked_original_chunks.append(orig_chunk + db_reduction)
            else:
                # Không có giọng nói -> Giữ nguyên 100% âm thanh gốc
                ducked_original_chunks.append(orig_chunk)

        # Nối lại
        ducked_original = ducked_original_chunks[0]
        for c in ducked_original_chunks[1:]:
            ducked_original += c

        # Tăng volume voiceover nhẹ để giọng TTS nổi bật rõ
        voiceover = voiceover + 2.0  # +2 dB

        mixed = ducked_original.overlay(voiceover)
        mixed.export(output_path, format="mp3", bitrate="192k")

        logger.info(f"✅ Audio mixed with Ducking (duck_vol={original_volume*100:.0f}%)")
        return output_path

    except Exception as exc:
        logger.error(f"Mix audio failed: {exc}")
        return None
