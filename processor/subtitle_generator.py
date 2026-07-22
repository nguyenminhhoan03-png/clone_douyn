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
            # Dùng cpu mặc định vì gpu cần setup CUDA (nếu máy có sẵn CUDA thì tự cấu hình 'cuda')
            # Thêm device="cuda" nếu máy bạn có card Nvidia và đã cài CUDA
            self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            logger.info("Whisper model loaded!")

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
            # condition_on_previous_text=False giúp giảm thiểu tình trạng AI bị ảo giác (lặp từ vô nghĩa)
            segments, info = self.model.transcribe(
                str(video_path), 
                beam_size=5, 
                language=src_lang,
                condition_on_previous_text=False,
                compression_ratio_threshold=2.0
            )
            logger.info(f"Detected language '{info.language}' with probability {info.language_probability:.2f}")

            srt_content = []
            segment_idx = 1
            
            for segment in segments:
                start_time = self._format_time(segment.start)
                end_time = self._format_time(segment.end)
                
                # Dịch câu này
                original_text = segment.text.strip()
                if not original_text:
                    continue
                    
                translated_text = translate_text(original_text, src=src_lang, dest=target_lang)
                
                # Chống ảo giác (anti-hallucination filter): 
                # Nếu chuỗi dịch ra dài bất thường và chứa mẫu lặp đi lặp lại nhiều lần
                if len(translated_text) > 40:
                    words = translated_text.split()
                    if len(words) > 8 and len(set(words)) < len(words) * 0.3:
                        logger.warning(f"Đã bỏ qua câu bị AI ảo giác: {translated_text[:30]}...")
                        continue
                
                logger.debug(f"[{start_time} -> {end_time}] {original_text} => {translated_text}")
                
                srt_content.append(str(segment_idx))
                srt_content.append(f"{start_time} --> {end_time}")
                srt_content.append(translated_text)
                srt_content.append("")
                
                segment_idx += 1

            if not srt_content:
                logger.warning("Không nhận diện được giọng nói trong video.")
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
