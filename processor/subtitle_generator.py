import os
from pathlib import Path
from typing import Optional
from loguru import logger

from utils.translator import translate_text


class SubtitleGenerator:
    """Tạo phụ đề tự động bằng AI cục bộ (faster-whisper) + Dịch ngôn ngữ."""

    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
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

    def generate_srt(self, video_path: str, output_srt_path: str, src_lang: str = "zh", target_lang: str = "vi") -> Optional[str]:
        """
        Nhận diện giọng nói từ video, dịch và tạo file .srt.
        """
        try:
            self._load_model()
            video_path_obj = Path(video_path)
            if not video_path_obj.exists():
                logger.error(f"Video không tồn tại: {video_path}")
                return None
            
            logger.info(f"Transcribing audio from: {video_path_obj.name}")
            
            # Whisper tự trích xuất audio nếu đưa file video vào
            # Senior tip: Dùng VAD (Voice Activity Detection) để bỏ qua khoảng lặng, giảm beam_size xuống 2 để x2 tốc độ
            segments, info = self.model.transcribe(
                str(video_path), 
                beam_size=2, 
                language=src_lang,
                condition_on_previous_text=False,
                compression_ratio_threshold=2.0,
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
                return None
                
            gemini_keys = PROCESSOR_CONFIG.get("gemini_api_keys", [])
            # Fallback tương thích ngược với file config cũ
            if not gemini_keys and PROCESSOR_CONFIG.get("gemini_api_key"):
                gemini_keys = [PROCESSOR_CONFIG.get("gemini_api_key")]
                
            use_google_fallback = True
            
            if gemini_keys:
                # ─── Cách 1: Dịch ngữ cảnh bằng Gemini LLM (Senior Tip: Xoay tua API Keys chống Quota) ───
                logger.info(f"Đã tìm thấy {len(gemini_keys)} Gemini API Keys. Đang gửi dữ liệu text cho AI dịch ngữ cảnh...")
                
                # Senior tip: Chia nhỏ kịch bản (Chunking) để tránh AI Gemini bị ảo giác hoặc cắt xén (Truncate) khi video quá dài
                CHUNK_SIZE = 100
                payload_lines = []
                for idx, data in enumerate(segment_data):
                    # Định dạng: ID|text
                    payload_lines.append(f"{idx}|{data['original_text']}")
                
                translated_text = ""
                total_chunks = (len(payload_lines) - 1) // CHUNK_SIZE + 1
                gemini_success = True
                current_key_idx = 0
                
                for i in range(0, len(payload_lines), CHUNK_SIZE):
                    chunk = payload_lines[i:i + CHUNK_SIZE]
                    chunk_text = "\n".join(chunk)
                    
                    import time
                    chunk_success = False
                    
                    # Thử lần lượt các keys nếu bị lỗi Quota (429)
                    for attempt in range(len(gemini_keys)):
                        gemini_key = gemini_keys[current_key_idx]
                        logger.info(f"Đang gửi lô {i//CHUNK_SIZE + 1}/{total_chunks} cho Gemini (Bằng Key {current_key_idx + 1}/{len(gemini_keys)})...")
                        
                        chunk_result = translate_srt_with_gemini(chunk_text, gemini_key)
                        
                        if chunk_result:
                            translated_text += chunk_result + "\n"
                            chunk_success = True
                            break
                        else:
                            logger.warning(f"Key {current_key_idx + 1} bị lỗi hoặc hết lượt (Quota Limit)! Đang đổi sang Key khác...")
                            current_key_idx = (current_key_idx + 1) % len(gemini_keys)
                            time.sleep(2)  # Nghỉ một chút trước khi thử key mới
                            
                    if not chunk_success:
                        logger.warning(f"Tất cả {len(gemini_keys)} Gemini Keys đều đã hết lượt hoặc lỗi! Hủy Gemini, chuyển sang Google Translate!")
                        gemini_success = False
                        break
                        
                    # Nghỉ 2s giữa các request thành công để tránh spam Rate Limit
                    time.sleep(2)
                
                if gemini_success and translated_text.strip():
                    # Phân tích cú pháp (Parse) kết quả từ AI và ghép vào Timestamp GỐC
                    trans_dict = {}
                    for line in translated_text.split('\n'):
                        if "|" in line:
                            parts = line.split("|", 1)
                            idx_str = parts[0].strip()
                            if idx_str.isdigit():
                                trans_dict[int(idx_str)] = parts[1].strip()
                    
                    srt_content = []
                    segment_idx = 1
                    for idx, data in enumerate(segment_data):
                        t_text = trans_dict.get(idx, data['original_text'])
                        
                        # Bộ lọc AI ảo giác lặp từ (Senior tip)
                        if len(t_text) > 40:
                            words = t_text.split()
                            if len(words) > 8 and len(set(words)) < len(words) * 0.3:
                                logger.warning(f"Đã bỏ qua câu AI ảo giác: {t_text[:30]}...")
                                continue
                                
                        srt_content.append(str(segment_idx))
                        srt_content.append(f"{data['start_time']} --> {data['end_time']}")
                        srt_content.append(t_text)
                        srt_content.append("")
                        segment_idx += 1
                    
                    if srt_content:
                        with open(output_srt_path, "w", encoding="utf-8") as f:
                            f.write("\n".join(srt_content))
                        use_google_fallback = False
                    else:
                        logger.warning("Không có nội dung SRT nào được tạo ra từ Gemini sau khi lọc. Fallback Google Translate.")
                        
            if use_google_fallback:
                # ─── Cách 2: Dịch từng câu bằng Google Dịch (Fallback) ───
                def _translate_task(data):
                    translated_text = translate_text(data["original_text"], src=src_lang, dest=target_lang)
                    return data, translated_text

                srt_content = []
                segment_idx = 1
                
                logger.info(f"Translating {len(segment_data)} segments concurrently with Google Translate...")
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                    results = executor.map(_translate_task, segment_data)
                    
                    for data, translated_text in results:
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

                if not srt_content:
                    logger.warning("Không có nội dung SRT nào được tạo ra sau khi lọc.")
                    return None
                    
                with open(output_srt_path, "w", encoding="utf-8") as f:
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
