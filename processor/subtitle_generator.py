import os
import time
import re
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
        self._cooldowns[h] = time.time() + wait_seconds
        logger.debug(f"  🔒 Key ...{h} cooldown {wait_seconds:.0f}s")
    
    def mark_success(self, key: str):
        """Xóa cooldown cho key thành công."""
        self._cooldowns.pop(self._hash(key), None)


# Singleton: 1 instance duy nhất dùng chung cho toàn bộ app
_key_manager = _KeyManager()


class SubtitleGenerator:
    """Tạo phụ đề tự động bằng AI cục bộ (faster-whisper) + Dịch ngôn ngữ."""

    def __init__(self, model_size: str = None):
        default_model = "base" if os.name != "nt" else "medium"
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
                logger.warning("Không tìm thấy GPU CUDA, đang dùng CPU (Sẽ chậm hơn) ...")
                self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
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
            
            # Whisper tự trích xuất audio nếu đưa file video vào
            # Senior+ tip: beam_size=5 cho độ chính xác cao nhất với tiếng Trung
            # condition_on_previous_text=True để Whisper dùng ngữ cảnh câu trước suy luận câu sau (giảm lỗi đồng âm)
            segments, info = self.model.transcribe(
                str(video_path), 
                beam_size=5, 
                language=src_lang,
                condition_on_previous_text=True,
                compression_ratio_threshold=2.4,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500)
            )
            logger.info(f"Detected language '{info.language}' with probability {info.language_probability:.2f}")

            import concurrent.futures
            from config.settings import PROCESSOR_CONFIG
            from utils.translator import translate_srt_with_gemini

            segment_data = []
            for segment in segments:
                original_text = segment.text.strip()
                if original_text:
                    segment_data.append({
                        "start_time": self._format_time(segment.start),
                        "end_time": self._format_time(segment.end),
                        "original_text": original_text,
                    })
                    
            if not segment_data:
                logger.warning("Không nhận diện được giọng nói trong video.")
                if progress_cb: progress_cb(10, "Cảnh báo: Video không có giọng nói hoặc AI không nghe rõ.")
                return None
                
            ai_provider = PROCESSOR_CONFIG.get("ai_provider", "ollama")
            ollama_url = PROCESSOR_CONFIG.get("ollama_url", "http://localhost:11434")
            ollama_model = PROCESSOR_CONFIG.get("ollama_model", "qwen2.5")

            gemini_keys = PROCESSOR_CONFIG.get("gemini_api_keys", [])
            # Fallback tương thích ngược với file config cũ
            if not gemini_keys and PROCESSOR_CONFIG.get("gemini_api_key"):
                gemini_keys = [PROCESSOR_CONFIG.get("gemini_api_key")]
                
            # Nếu dùng Ollama hoặc không có key riêng thì vẫn chạy được
            if ai_provider == "ollama":
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
                        
                # ─── Cách 1: Dịch ngữ cảnh bằng AI LLM (Ollama Local / Groq / Gemini) ───
                if ai_provider == "ollama":
                    ai_name = f"Ollama ({ollama_model})"
                    logger.info(f"🦙 Đang sử dụng {ai_name} (Local Offline) để xử lý phụ đề...")
                else:
                    ai_name = "Groq" if gemini_keys and gemini_keys[0] and str(gemini_keys[0]).startswith("gsk_") else "Gemini"
                    logger.info(f"Đã tìm thấy {len(gemini_keys)} {ai_name} API Keys. Đang gửi dữ liệu text cho AI dịch ngữ cảnh...")
                
                # Chunk size cho Ollama trên CPU tối ưu ở mức 25 câu để tránh nghẽn context và timeout
                CHUNK_SIZE = 25 if ai_provider == "ollama" else 100
                payload_lines = []
                for idx, data in enumerate(segment_data):
                    payload_lines.append(f"{idx}|{data['original_text']}")
                
                translated_text = ""
                total_chunks = (len(payload_lines) - 1) // CHUNK_SIZE + 1
                gemini_success = True
                
                # Kiểm tra cấu hình xem có đang ở chế độ nhiều giọng không
                multi_speaker_mode = PROCESSOR_CONFIG.get("tts_voice") in ("Multi", "vbee-multi")
                
                for i in range(0, len(payload_lines), CHUNK_SIZE):
                    chunk = payload_lines[i:i + CHUNK_SIZE]
                    chunk_text = "\n".join(chunk)
                    chunk_success = False
                    
                    # Smart Round-Robin: thử tối đa len(keys) + 1 lần (bao gồm auto-wait)
                    max_attempts = len(gemini_keys) + 1
                    for attempt in range(max_attempts):
                        gemini_key = _key_manager.get_next_key(gemini_keys)
                        if not gemini_key:
                            break
                        
                        key_label = "Ollama Local" if gemini_key == "ollama" else (f"...{gemini_key[-6:]}" if gemini_key else "Server")
                        logger.info(f"Đang gửi lô {i//CHUNK_SIZE + 1}/{total_chunks} cho {ai_name} ({key_label})...")
                        
                        chunk_result = translate_srt_with_gemini(
                            chunk_text, 
                            gemini_key,
                            multi_speaker=multi_speaker_mode,
                            provider=ai_provider,
                            model=ollama_model,
                            ollama_url=ollama_url
                        )
                        
                        if chunk_result:
                            _key_manager.mark_success(gemini_key)
                            translated_text += chunk_result + "\n"
                            chunk_success = True
                            break
                        else:
                            if gemini_key == "ollama":
                                if attempt < max_attempts - 1:
                                    logger.warning(f"⚠️ Ollama Local không phản hồi ở lần thử {attempt+1}/{max_attempts}. Đang thử lại sau 2s...")
                                    time.sleep(2)
                                else:
                                    logger.warning(f"❌ Ollama Local đã thử {max_attempts} lần không thành công. Sẽ chuyển sang Google Translate cứu hộ.")
                            else:
                                # Đánh dấu key Cloud bị lỗi với cooldown
                                _key_manager.mark_rate_limited(gemini_key)
                                logger.warning(f"Key {key_label} bị lỗi! KeyManager tự động chọn key khác...")
                            
                    if not chunk_success:
                        logger.warning(f"Lô {i//CHUNK_SIZE + 1}/{total_chunks} gọi AI không phản hồi. Tự động dịch bổ cứu lô này bằng Google Translate...")
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
                        
                        # LOG: Hiển thị text gốc và text dịch để User kiểm tra chất lượng
                        logger.info(f"[Dịch Sub {idx+1}] {data['original_text']} ➔ {t_text}")
                        
                        # Bộ lọc AI ảo giác lặp từ (Senior tip)
                        if len(t_text) > 40:
                            words = t_text.split()
                            if len(words) > 8 and len(set(words)) < len(words) * 0.3:
                                logger.warning(f"Đã bỏ qua câu AI ảo giác: {t_text[:30]}...")
                                continue
                                
                        # Xóa tags [M], [F], [N] và ký tự phân cách | để tạo bản clean cho Subtitle hiển thị trên Video
                        clean_text = re.sub(r'\[[MFNmf]\]', '', t_text).strip().strip('|').strip()
                        
                        time_line = f"{data['start_time']} --> {data['end_time']}"
                        
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
                                logger.warning(f"Đã bỏ qua câu bị AI ảo giác: {translated_text[:30]}...")
                                continue
                        
                        logger.debug(f"[{data['start_time']} -> {data['end_time']}] {data['original_text']} => {translated_text}")
                        
                        srt_content.append(str(segment_idx))
                        srt_content.append(f"{data['start_time']} --> {data['end_time']}")
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
