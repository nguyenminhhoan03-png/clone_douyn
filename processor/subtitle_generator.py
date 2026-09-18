import os
import time
import re
import threading
from pathlib import Path
from typing import Optional, Callable, List
from loguru import logger

from utils.translator import translate_text


class _KeyManager:
    """
    Senior-level Round-Robin API Key Manager.
    
    Features:
    - Round-Robin: phân tải đều giữa các keys (nhớ vị trí giữa các lần gọi)
    - Cooldown Tracking: key bị rate limit → tự động bỏ qua đến khi hết cooldown
    - Auto-Wait: nếu TẤT CẢ keys đều đang cooldown → tự chờ đến key sớm nhất
    - Parse wait time: đọc thời gian chờ từ error message của Groq
    """
    
    def __init__(self):
        self._index = 0
        self._cooldowns = {}  # key_hash -> timestamp khi hết cooldown
        self._lock = threading.Lock()
    
    def _hash(self, key):
        """Hash key để log không lộ API key."""
        return key[-6:] if key else "none"
    
    def get_next_key(self, keys: List[str]) -> Optional[str]:
        """
        Lấy key tiếp theo chưa bị cooldown.
        Nếu tất cả đang cooldown → chờ key sớm nhất rồi trả về.
        """
        if not keys:
            return None
        
        with self._lock:
            now = time.time()
            
            # Thử tìm key chưa bị cooldown
            for _ in range(len(keys)):
                key = keys[self._index % len(keys)]
                self._index = (self._index + 1) % len(keys)
                
                cooldown_until = self._cooldowns.get(self._hash(key), 0)
                if now >= cooldown_until:
                    return key
            
            # Tất cả keys đang cooldown → chờ key hết cooldown sớm nhất
            if self._cooldowns:
                min_wait = min(self._cooldowns.values()) - now
                if min_wait > 0:
                    logger.info(f"⏳ Tất cả keys đang cooldown. Tự động chờ {min_wait:.1f}s...")
                    time.sleep(min_wait + 0.5)  # +0.5s buffer
                # Xóa cooldown đã hết hạn
                self._cooldowns = {k: v for k, v in self._cooldowns.items() if v > time.time()}
                return self.get_next_key(keys)
            
            return keys[0]  # fallback
    
    def mark_rate_limited(self, key: str, error_msg: str = ""):
        """
        Đánh dấu key bị rate limit.
        Parse thời gian chờ từ error message nếu có.
        """
        # Groq trả về: "Please try again in 30.595s"
        wait_seconds = 35  # default 35s
        match = re.search(r'try again in (\d+\.?\d*)s', error_msg)
        if match:
            wait_seconds = float(match.group(1)) + 2  # +2s buffer
        
        h = self._hash(key)
        with self._lock:
            self._cooldowns[h] = time.time() + wait_seconds
        logger.debug(f"  🔒 Key ...{h} cooldown {wait_seconds:.0f}s")
    
    def mark_success(self, key: str):
        """Xóa cooldown cho key thành công."""
        with self._lock:
            self._cooldowns.pop(self._hash(key), None)


# Singleton: 1 instance duy nhất dùng chung cho toàn bộ app
_key_manager = _KeyManager()


class SubtitleGenerator:
    """Tạo phụ đề tự động bằng AI cục bộ (faster-whisper) + Dịch ngôn ngữ."""
    _transcribe_lock = threading.Lock()

    def __init__(self, model_size: str = None):
        default_model = "base"
        self.model_size = model_size or os.getenv("WHISPER_MODEL", default_model)
        self.model = None

    def _load_model(self):
        if self.model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                raise ImportError("Vui lòng cài đặt: pip install faster-whisper")
            
            logger.info(f"Loading Whisper model '{self.model_size}'...")
            # Senior tip: Tự động detect và ưu tiên dùng GPU (CUDA) nếu có, fallback về CPU
            try:
                self.model = WhisperModel(self.model_size, device="cuda", compute_type="float16")
                logger.info("Whisper model loaded on CUDA (GPU) - Xử lý siêu tốc!")
            except Exception as e:
                import os
                threads = os.cpu_count() or 4
                logger.info(f"Đang dùng CPU ({threads} threads) cho Whisper '{self.model_size}'...")
                self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8", cpu_threads=threads)
                logger.info("Whisper model loaded on CPU!")

    def generate_srt(self, video_path: str, output_srt_path: str, src_lang: str = "zh", target_lang: str = "vi", progress_cb: Optional[Callable] = None) -> Optional[str]:
        """
        Nhận diện giọng nói từ video, dịch và tạo file .srt.
        """
        try:
            try:
                self._load_model()
            except Exception as e:
                if progress_cb: progress_cb(10, f"Lỗi load model AI (Cần cài đặt đúng thư viện hoặc thiết lập GPU): {str(e)[:100]}")
                logger.error(f"Lỗi load model AI: {e}")
                return None
                
            video_path_obj = Path(video_path)
            if not video_path_obj.exists():
                logger.error(f"Video không tồn tại: {video_path}")
                if progress_cb: progress_cb(10, "Lỗi: Video gốc không tồn tại để dịch AI.")
                return None
            
            logger.info(f"Transcribing audio from: {video_path_obj.name}")
            
            # 1. Trích xuất âm thanh giọng nói trong trẻo (Vocal Enhancement) phục vụ Whisper
            # Cắt tần số thấp (<100Hz) loại bỏ bass/nhạc nền ù, cắt tần số cao (>7500Hz) loại bỏ rít
            # Chuẩn hóa âm lượng động (Dynamic Normalizer) đẩy âm thanh thì thầm/nhỏ lên rõ ràng
            clean_audio_path = None
            try:
                import tempfile
                import subprocess
                from processor.video_processor import FFMPEG_BIN
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                    clean_audio_path = tf.name
                
                cmd = [
                    FFMPEG_BIN, "-y", "-i", str(video_path),
                    "-vn", "-ac", "1", "-ar", "16000",
                    "-af", "highpass=f=80,dynaudnorm=f=125:g=15:p=0.95:m=10.0",
                    clean_audio_path
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                audio_input = clean_audio_path
                logger.debug("  ✓ Đã trích xuất & khuếch đại giọng nói thì thầm/tự nói (DynAudNorm) cho Whisper")
            except Exception as e:
                logger.debug(f"Audio extraction fallback: {e}")
                audio_input = str(video_path)

            # 2. Khóa Lock để chỉ 1 video gọi Whisper bóc băng tại một thời điểm, giải phóng ngay CPU/GPU
            try:
                with SubtitleGenerator._transcribe_lock:
                    segments_gen, info = self.model.transcribe(
                        audio_input, 
                        beam_size=1,
                        best_of=1,
                        language=src_lang,
                        temperature=0.0,
                        condition_on_previous_text=False,
                        compression_ratio_threshold=2.4,
                        no_speech_threshold=0.8,
                        initial_prompt=None,
                        vad_filter=False,
                        word_timestamps=True
                    )
                    segments = list(segments_gen)
            finally:
                if clean_audio_path and os.path.exists(clean_audio_path):
                    try:
                        os.unlink(clean_audio_path)
                    except Exception:
                        pass

            logger.info(f"Detected language '{info.language}' with probability {info.language_probability:.2f}")

            import concurrent.futures
            import re
            from config.settings import PROCESSOR_CONFIG
            from utils.translator import translate_srt_with_gemini

            segment_data = []
            split_chars = r'[。！？；;\n]+'

            for segment in segments:
                original_text = segment.text.strip()
                if not original_text:
                    continue

                # TỰ ĐỘNG BẺ NHỎ CÂU (Chống dồn hàng chục câu vào một đoạn ngắn):
                # Nếu Whisper gộp nhiều câu ngăn cách bởi dấu ngắt câu, tách từng câu ra thành segment riêng
                raw_sentences = [s.strip() for s in re.split(split_chars, original_text) if s.strip()]
                if not raw_sentences:
                    continue

                if len(raw_sentences) == 1:
                    s = raw_sentences[0]
                    # Tránh kéo dài subtitle quá mức khi có đoạn nhạc nền / im lặng ở đuôi câu
                    dur = segment.end - segment.start
                    max_dur = max(2.5, len(s) * 0.4 + 1.0)
                    eff_end = min(segment.end, segment.start + max_dur) if dur > max_dur + 2.0 else segment.end

                    # Chống hallucination lặp lại liên tiếp cùng 1 câu
                    if segment_data and segment_data[-1]["original_text"] == s and (segment.start - segment_data[-1]["end"]) < 2.0:
                        continue

                    segment_data.append({
                        "start": segment.start,
                        "end": eff_end,
                        "start_time": self._format_time(segment.start),
                        "end_time": self._format_time(eff_end),
                        "original_text": s,
                    })
                else:
                    # Nhiều câu: Phân bổ thời gian tỉ lệ theo độ dài ký tự chuẩn xác
                    total_len = sum(len(s) for s in raw_sentences)
                    total_dur = max(0.6 * len(raw_sentences), segment.end - segment.start)
                    curr_start = segment.start
                    for i, s in enumerate(raw_sentences):
                        ratio = len(s) / max(1, total_len)
                        dur = max(0.6, ratio * total_dur)
                        curr_end = curr_start + dur

                        # Chống hallucination lặp lại liên tiếp
                        if segment_data and segment_data[-1]["original_text"] == s and abs(curr_start - segment_data[-1]["end"]) < 1.0:
                            curr_start = curr_end
                            continue

                        segment_data.append({
                            "start": curr_start,
                            "end": curr_end,
                            "start_time": self._format_time(curr_start),
                            "end_time": self._format_time(curr_end),
                            "original_text": s,
                        })
                        curr_start = curr_end

            if not segment_data:
                logger.warning("Không nhận diện được giọng nói trong video.")
                if progress_cb: progress_cb(10, "Cảnh báo: Video không có giọng nói hoặc AI không nghe rõ.")
                return None

            # Lưu file _zh.srt chứa phụ đề tiếng Trung gốc và timestamps chính xác (cho OCR đối chiếu định vị hardsub)
            try:
                zh_path = str(output_srt_path).replace('.srt', '_zh.srt')
                srt_content_zh = []
                for s_idx, s_data in enumerate(segment_data, 1):
                    srt_content_zh.append(str(s_idx))
                    srt_content_zh.append(f"{s_data['start_time']} --> {s_data['end_time']}")
                    srt_content_zh.append(s_data['original_text'])
                    srt_content_zh.append("")
                with open(zh_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(srt_content_zh))
                logger.info(f"Đã lưu phụ đề gốc tiếng Trung phục vụ OCR đối chiếu: {zh_path}")
            except Exception as e:
                logger.warning(f"Không thể lưu _zh.srt: {e}")
                
            ai_provider = PROCESSOR_CONFIG.get("ai_provider") or os.getenv("AI_PROVIDER", "cloud_first")
            ollama_url = PROCESSOR_CONFIG.get("ollama_url") or os.getenv("OLLAMA_URL", "http://localhost:11434")
            ollama_model = PROCESSOR_CONFIG.get("ollama_model") or os.getenv("OLLAMA_MODEL", "qwen2.5")

            gemini_keys = PROCESSOR_CONFIG.get("gemini_api_keys", [])
            if not gemini_keys:
                raw_k = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", "")).strip()
                if raw_k:
                    gemini_keys = [k.strip() for k in raw_k.split(",") if k.strip()]

            # Fallback nếu vẫn rỗng: tìm trong settings.json của current user
            if not gemini_keys:
                try:
                    from auth_client import auth_client
                    from config.settings import COOKIES_DIR
                    import json
                    username = auth_client.user_info.get("username", "default") if auth_client.user_info else "default"
                    user_clean = username.replace("@", "_").replace(".", "_")
                    user_settings_path = COOKIES_DIR / user_clean / "settings.json"
                    if user_settings_path.exists():
                        with open(user_settings_path, "r", encoding="utf-8") as f:
                            u_data = json.load(f)
                            k_val = u_data.get("gemini_api_key", "").strip()
                            if k_val:
                                gemini_keys = [k.strip() for k in k_val.split(",") if k.strip()]
                                PROCESSOR_CONFIG["gemini_api_keys"] = gemini_keys
                            if u_data.get("custom_ai_model"):
                                PROCESSOR_CONFIG["custom_ai_model"] = u_data.get("custom_ai_model")
                except Exception:
                    pass

            if not gemini_keys and PROCESSOR_CONFIG.get("gemini_api_key"):
                gemini_keys = [PROCESSOR_CONFIG.get("gemini_api_key")]
                
            # Nếu dùng Ollama hoặc không có key riêng thì vẫn chạy được
            if ai_provider in ("ollama", "ollama_only"):
                if not gemini_keys:
                    gemini_keys = ["ollama"]
            elif not gemini_keys or len(gemini_keys) == 0:
                gemini_keys = [None]
                
            use_google_fallback = True
            
            if gemini_keys:
                ai_mode = PROCESSOR_CONFIG.get("ai_mode", "Thuyết minh nguyên bản")
                
                if ai_mode == "Tóm tắt Review Phim":
                    logger.info("Chế độ Tóm tắt Review Phim: Gom toàn bộ text...")
                    from utils.translator import summarize_review_with_gemini
                    full_text = " ".join([d["original_text"] for d in segment_data])
                    review_script = summarize_review_with_gemini(
                        full_text, 
                        api_keys=gemini_keys,
                        provider=ai_provider,
                        model=ollama_model,
                        ollama_url=ollama_url
                    )
                    
                    if review_script:
                        end_time = segment_data[-1]["end_time"]
                        srt_content = [
                            "1",
                            f"00:00:00,000 --> {end_time}",
                            review_script,
                            ""
                        ]
                        with open(output_srt_path, "w", encoding="utf-8") as f:
                            f.write("\n".join(srt_content))
                        
                        clean_path = str(output_srt_path).replace('.srt', '_clean.srt')
                        with open(clean_path, "w", encoding="utf-8") as f:
                            f.write("\n".join(srt_content))
                            
                        logger.info(f"Đã tạo kịch bản Tóm tắt Review tại: {output_srt_path}")
                        return output_srt_path
                    else:
                        logger.warning("Lỗi khi viết kịch bản Review, chuyển về dịch nguyên bản...")
                        
                # ─── Cách 1: Dịch ngữ cảnh bằng AI LLM (Hỗ trợ Thứ tự ưu tiên & Dự phòng 2 chiều) ───
                cloud_keys = [k for k in gemini_keys if k and k != "ollama"]
                custom_model = PROCESSOR_CONFIG.get("custom_ai_model") or os.getenv("CUSTOM_AI_MODEL", "gemini-3.6-flash-high")
                
                # Xác định nhãn Cloud
                cloud_label = "Cloud API"
                if cloud_keys:
                    first_k = cloud_keys[0]
                    if str(first_k).startswith("sk-"):
                        cloud_label = f"Vilao.ai ({custom_model})"
                    elif str(first_k).startswith("gsk_"):
                        cloud_label = "Groq Cloud"
                    else:
                        cloud_label = "Gemini Cloud"

                # Log chế độ hoạt động
                if ai_provider in ("ollama_first", "ollama"):
                    logger.info(f"🦙 Chế độ: Ưu tiên Ollama Local ({ollama_model}) ➔ Dự phòng Cloud API ({cloud_label})...")
                elif ai_provider in ("cloud_first", "gemini", "groq", "vilao"):
                    logger.info(f"⚡ Chế độ: Ưu tiên Cloud API ({cloud_label}) ➔ Dự phòng Ollama Local ({ollama_model})...")
                elif ai_provider == "cloud_only":
                    logger.info(f"☁️ Chế độ: Chỉ sử dụng Cloud API ({cloud_label})...")
                else: # ollama_only
                    logger.info(f"🦙 Chế độ: Chỉ sử dụng Ollama Local Offline ({ollama_model})...")

                CHUNK_SIZE = 15 if ai_provider in ("ollama", "ollama_first", "ollama_only") else 25
                payload_lines = []
                for idx, data in enumerate(segment_data):
                    payload_lines.append(f"{idx}|{data['original_text']}")
                
                translated_text = ""
                total_chunks = (len(payload_lines) - 1) // CHUNK_SIZE + 1
                gemini_success = True
                multi_speaker_mode = PROCESSOR_CONFIG.get("tts_voice") in ("Multi", "vbee-multi")

                def _try_translate_with_ollama(chunk_str, ctx_str):
                    try:
                        return translate_srt_with_gemini(
                            chunk_str,
                            api_key="ollama",
                            multi_speaker=multi_speaker_mode,
                            provider="ollama",
                            model=ollama_model,
                            ollama_url=ollama_url,
                            context=ctx_str
                        )
                    except Exception as err:
                        logger.warning(f"Ollama Local gặp lỗi: {err}")
                        return None

                def _try_translate_with_cloud(chunk_str, ctx_str):
                    if not cloud_keys:
                        return None
                    for c_key in cloud_keys:
                        c_prov = "vilao" if str(c_key).startswith("sk-") else ("groq" if str(c_key).startswith("gsk_") else "gemini")
                        try:
                            res = translate_srt_with_gemini(
                                chunk_str,
                                api_key=c_key,
                                multi_speaker=multi_speaker_mode,
                                provider=c_prov,
                                model=custom_model,
                                context=ctx_str
                            )
                            if res and res.strip():
                                return res.strip()
                        except Exception as c_err:
                            logger.warning(f"Key Cloud (...{str(c_key)[-6:]}) lỗi: {c_err}")
                    return None

                for i in range(0, len(payload_lines), CHUNK_SIZE):
                    chunk = payload_lines[i:i + CHUNK_SIZE]
                    chunk_text = "\n".join(chunk)
                    chunk_success = False
                    
                    pre_ctx_lines = []
                    if i > 0:
                        prev_slice = payload_lines[max(0, i - 2):i]
                        pre_ctx_lines = [p.split("|", 1)[1] for p in prev_slice if "|" in p]
                    pre_ctx_str = " | ".join(pre_ctx_lines)

                    chunk_idx_str = f"Lô {i//CHUNK_SIZE + 1}/{total_chunks}"
                    chunk_result = None

                    if ai_provider in ("ollama_first", "ollama"):
                        logger.info(f"Đang gửi {chunk_idx_str} cho Ollama Local ({ollama_model})...")
                        chunk_result = _try_translate_with_ollama(chunk_text, pre_ctx_str)
                        if not chunk_result and cloud_keys:
                            logger.warning(f"⚠️ Ollama không phản hồi. Tự động chuyển sang Cloud API ({cloud_label}) cứu hộ...")
                            chunk_result = _try_translate_with_cloud(chunk_text, pre_ctx_str)

                    elif ai_provider in ("cloud_first", "gemini", "groq", "vilao"):
                        logger.info(f"Đang gửi {chunk_idx_str} cho Cloud API ({cloud_label})...")
                        chunk_result = _try_translate_with_cloud(chunk_text, pre_ctx_str)
                        if not chunk_result:
                            logger.warning(f"⚠️ Cloud API không phản hồi/hết lượt. Tự động chuyển về Ollama Local ({ollama_model}) cứu hộ...")
                            chunk_result = _try_translate_with_ollama(chunk_text, pre_ctx_str)

                    elif ai_provider == "cloud_only":
                        logger.info(f"Đang gửi {chunk_idx_str} cho Cloud API ({cloud_label})...")
                        chunk_result = _try_translate_with_cloud(chunk_text, pre_ctx_str)

                    elif ai_provider == "ollama_only":
                        logger.info(f"Đang gửi {chunk_idx_str} cho Ollama Local ({ollama_model})...")
                        chunk_result = _try_translate_with_ollama(chunk_text, pre_ctx_str)

                    if chunk_result and chunk_result.strip():
                        translated_text += chunk_result.strip() + "\n"
                        chunk_success = True
                    else:
                        logger.warning(f"{chunk_idx_str} chuyển sang Google Translate cứu hộ...")
                        from utils.translator import translate_text
                        chunk_rescue_lines = []
                        for line in chunk:
                            if "|" in line:
                                idx_part, raw_zh = line.split("|", 1)
                                vi_text = translate_text(raw_zh.strip(), src="zh-CN", dest="vi")
                                chunk_rescue_lines.append(f"{idx_part.strip()}|{vi_text}")
                            else:
                                chunk_rescue_lines.append(line)
                        translated_text += "\n".join(chunk_rescue_lines) + "\n"
                        chunk_success = True
                        
                    # Nghỉ 1s giữa các chunk thành công
                    time.sleep(1)
                
                if gemini_success and translated_text.strip():
                    # Phân tích cú pháp (Parse) kết quả từ AI và ghép vào Timestamp GỐC
                    trans_dict = {}
                    for line in translated_text.split('\n'):
                        if "|" in line:
                            parts = line.split("|", 1)
                            idx_str = parts[0].strip()
                            if idx_str.isdigit():
                                trans_dict[int(idx_str)] = parts[1].strip()
                    
                    srt_content_tagged = []
                    srt_content_clean = []
                    segment_idx = 1
                    import re
                    from utils.translator import translate_text

                    # CỨU HỘ SIÊU TỐC BẰNG BATCH GOOGLE TRANSLATE
                    # Tìm tất cả câu AI bị sót hoặc còn chứa chữ Hán:
                    missing_indices = []
                    missing_texts = []
                    for idx, data in enumerate(segment_data):
                        t_text = trans_dict.get(idx)
                        is_chinese = bool(t_text and re.search(r'[\u4e00-\u9fff]', t_text))
                        if not t_text or is_chinese:
                            missing_indices.append(idx)
                            missing_texts.append(data['original_text'])

                    if missing_texts:
                        from utils.translator import translate_lines_batch
                        logger.info(f"⚡ Đang tự động cứu hộ {len(missing_texts)} câu phụ đề bằng Google Translate (Batch siêu tốc)...")
                        rescued_batch = translate_lines_batch(missing_texts, src="zh-CN", dest="vi")
                        for idx, rescued_vi in zip(missing_indices, rescued_batch):
                            trans_dict[idx] = rescued_vi

                    for idx, data in enumerate(segment_data):
                        t_text = trans_dict.get(idx, data['original_text'])
                        t_text = t_text.strip().strip('|').strip()
                        
                        # Bộ lọc làm sạch lặp từ bất thường (rút gọn lặp từ thay vì drop bỏ cả câu):
                        if len(t_text) > 40:
                            words = t_text.split()
                            if len(words) > 8 and len(set(words)) < len(words) * 0.3:
                                t_text = re.sub(r'(\b\w+\b)(?:\s+\1){3,}', r'\1 \1', t_text)
                                
                        # 1. Nhận diện tag [M], [F], [N] ở BẤT KỲ ĐÂU trong câu (đầu câu hoặc cuối câu):
                        tag_found = None
                        tag_m = re.search(r'\[\s*(M|F|N|Nam|Nữ|Nu)\s*\]|\(\s*(M|F|N|Nam|Nữ|Nu)\s*\)|(?:^|\s)(M|F|N|Nam|Nữ|Nu)[:\s]+', t_text, re.IGNORECASE)
                        if tag_m:
                            raw_tag = (tag_m.group(1) or tag_m.group(2) or tag_m.group(3)).upper()
                            tag_found = 'M' if ('M' in raw_tag or 'NAM' in raw_tag) else ('F' if ('F' in raw_tag or 'NỮ' in raw_tag or 'NU' in raw_tag) else 'N')
                        
                        # 2. Xóa sạch mọi tag và ký tự | khỏi clean_text (dùng in trực tiếp lên Video):
                        clean_text = re.sub(r'\[\s*(?:M|F|N|Nam|Nữ|Nu|Male|Female|Man|Woman)\s*\][:\s\-]*', '', t_text, flags=re.IGNORECASE)
                        clean_text = re.sub(r'\(\s*(?:M|F|N|Nam|Nữ|Nu|Male|Female|Man|Woman)\s*\)[:\s\-]*', '', clean_text, flags=re.IGNORECASE)
                        clean_text = re.sub(r'^(?:M|F|N|Nam|Nữ|Nu|Male|Female|Man|Woman)[:\s\-]+', '', clean_text, flags=re.IGNORECASE)
                        clean_text = clean_text.replace('|', ' ').strip()
                        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                        
                        # 2b. BỘ LỌC CHUẨN HÓA XƯNG HÔ & PHIÊN ÂM (Staff Engineer Quality Gate):
                        clean_text = re.sub(r'\b(?:Chào\s+)?anh\s+lãnh\s+đạo\b', 'Chào sếp ạ', clean_text, flags=re.IGNORECASE)
                        clean_text = re.sub(r'\bngười\s+lãnh\s+đạo\b', 'sếp', clean_text, flags=re.IGNORECASE)
                        clean_text = re.sub(r'\bHu\s+Hu\s+ngoan\b', 'Hoa Hoa ngoan', clean_text, flags=re.IGNORECASE)
                        clean_text = re.sub(r'\bĐưa\s+(?:bạn|mày|con|cháu)\s+lớn\s+lên\b', 'Nuôi con khôn lớn', clean_text, flags=re.IGNORECASE)
                        clean_text = re.sub(r'\b(Chú|Bác|Ông|Cô|Dì)\s+([^.\n,]+?)\s+đón\s+em\b', r'\1 \2 đón cháu', clean_text, flags=re.IGNORECASE)
                        clean_text = re.sub(r'\b(Chú|Bác|Ông|Cô|Dì)\s+đón\s+em\b', r'\1 đón cháu', clean_text, flags=re.IGNORECASE)
                        clean_text = re.sub(r'\bChú\s+Hoa\s+Hoa\b', 'Chú Chu', clean_text)
                        
                        # 3. Chuẩn hóa t_text cho file SRT cấp cho TTS Engine (luôn chuẩn [M] ở đầu câu):
                        if tag_found and multi_speaker_mode:
                            t_text = f"[{tag_found}] {clean_text}"
                        else:
                            t_text = clean_text

                        tag_str = f"Tag: {tag_found} (Đa giọng TTS)" if tag_found else "Tag: Đơn giọng"
                        sub_log_msg = f"📝 [Sub #{segment_idx:02d}] [{data['start_time']} ➔ {data['end_time']}] 🇨🇳 Gốc: \"{data['original_text']}\" ➔ 🇻🇳 Sub: \"{clean_text}\" ({tag_str})"
                        logger.info(sub_log_msg)
                        if progress_cb:
                            try: progress_cb(15, f"[DEBUG] {sub_log_msg}")
                            except Exception: pass
                        
                        # Chống ngâm/treo phụ đề cũ trên màn hình khi nhân vật đã dứt lời:
                        start_sec = data.get("start", 0.0)
                        end_sec = data.get("end", start_sec + 3.0)
                        actual_dur = end_sec - start_sec
                        # Thời gian đọc lý tưởng: ~14 ký tự/giây + 1.2s đệm nhìn (min 2.0s, max 6.0s)
                        ideal_dur = max(2.0, min(6.0, len(clean_text) * 0.14 + 1.2))
                        if actual_dur > ideal_dur + 1.5:
                            clamped_end = start_sec + ideal_dur
                            clamped_end_str = self._format_time(clamped_end)
                        else:
                            clamped_end_str = data['end_time']
                        
                        time_line = f"{data['start_time']} --> {clamped_end_str}"
                        
                        srt_content_tagged.append(str(segment_idx))
                        srt_content_tagged.append(time_line)
                        srt_content_tagged.append(t_text)
                        srt_content_tagged.append("")
                        
                        srt_content_clean.append(str(segment_idx))
                        srt_content_clean.append(time_line)
                        srt_content_clean.append(clean_text)
                        srt_content_clean.append("")
                        
                        segment_idx += 1
                    
                    if srt_content_tagged:
                        # Ghi bản có tags (cho TTS)
                        with open(output_srt_path, "w", encoding="utf-8") as f:
                            f.write("\n".join(srt_content_tagged))
                            
                        # Ghi bản không tags (cho Video)
                        clean_path = str(output_srt_path).replace('.srt', '_clean.srt')
                        with open(clean_path, "w", encoding="utf-8") as f:
                            f.write("\n".join(srt_content_clean))
                            
                        use_google_fallback = False
                    else:
                        logger.warning("Không có nội dung SRT nào được tạo ra từ AI sau khi lọc. Fallback Google Translate.")
                        
            if use_google_fallback:
                # ─── Cách 2: Dịch hàng loạt bằng Google Dịch (Batch Translation - Chống 429) ───
                from utils.translator import translate_lines_batch
                
                srt_content = []
                segment_idx = 1
                BATCH_SIZE = 25
                
                logger.info(f"Translating {len(segment_data)} segments in batches with Google Translate...")
                
                for b_i in range(0, len(segment_data), BATCH_SIZE):
                    batch = segment_data[b_i:b_i + BATCH_SIZE]
                    raw_lines = [item["original_text"] for item in batch]
                    translated_batch = translate_lines_batch(raw_lines, src=src_lang, dest=target_lang)
                    
                    for data, translated_text in zip(batch, translated_batch):
                        if len(translated_text) > 40:
                            words = translated_text.split()
                            if len(words) > 8 and len(set(words)) < len(words) * 0.3:
                                translated_text = re.sub(r'(\b\w+\b)(?:\s+\1){3,}', r'\1 \1', translated_text)
                        
                        logger.debug(f"[{data['start_time']} -> {data['end_time']}] {data['original_text']} => {translated_text}")
                        
                        # Chống ngâm/treo phụ đề khi nhân vật đã dứt lời:
                        start_sec = data.get("start", 0.0)
                        end_sec = data.get("end", start_sec + 3.0)
                        actual_dur = end_sec - start_sec
                        ideal_dur = max(2.0, min(6.0, len(translated_text) * 0.14 + 1.2))
                        if actual_dur > ideal_dur + 1.5:
                            clamped_end = start_sec + ideal_dur
                            clamped_end_str = self._format_time(clamped_end)
                        else:
                            clamped_end_str = data['end_time']

                        srt_content.append(str(segment_idx))
                        srt_content.append(f"{data['start_time']} --> {clamped_end_str}")
                        srt_content.append(translated_text)
                        srt_content.append("")
                        segment_idx += 1
                        
                    # Nghỉ nhẹ giữa các lô để đảm bảo an toàn tuyệt đối cho IP
                    time.sleep(0.3)

                if not srt_content:
                    logger.warning("Không có nội dung SRT nào được tạo ra sau khi lọc.")
                    return None
                    
                with open(output_srt_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(srt_content))
                    
                # Google Translate không có tags, nên clean SRT giống hệt bản gốc
                clean_path = str(output_srt_path).replace('.srt', '_clean.srt')
                with open(clean_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(srt_content))
                
            logger.info(f"Đã tạo file SRT: {output_srt_path}")
            return output_srt_path
            
        except Exception as e:
            logger.error(f"Lỗi khi tạo phụ đề: {e}")
            return None

    def _format_time(self, seconds: float) -> str:
        """Format số giây sang dạng hh:mm:ss,ms cho file SRT."""
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        msecs = int((seconds - int(seconds)) * 1000)
        return f"{hrs:02d}:{mins:02d}:{secs:02d},{msecs:03d}"
