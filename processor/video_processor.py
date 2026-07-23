"""
Video Processor - Xử lý video trước khi upload TikTok
Chức năng chính:
  - Mirror (lật ngang) video
  - Thay đổi speed nhẹ
  - Thêm text overlay tiếng Việt
  - Ghép nhạc Việt trending thay nhạc gốc
  - Apply filter nhẹ (brightness, contrast)
Mục đích: Biến đổi video đủ để TikTok không detect trùng lặp.
"""
import os
import random
import subprocess
from pathlib import Path
from typing import Optional

from loguru import logger

from config.settings import PROCESSOR_CONFIG, PROCESSED_DIR, MUSIC_DIR
from database.db_manager import DatabaseManager
from processor.subtitle_generator import SubtitleGenerator


class VideoProcessor:
    """Xử lý video dance Douyin bằng Native FFmpeg (Siêu tốc)."""

    def __init__(self, db: DatabaseManager = None):
        self.db = db or DatabaseManager()
        self.config = PROCESSOR_CONFIG
        
        # Thêm default config cho auto_subtitle
        if "auto_subtitle" not in self.config:
            self.config["auto_subtitle"] = True
            
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        MUSIC_DIR.mkdir(parents=True, exist_ok=True)
        
        self.subtitle_generator = SubtitleGenerator() if self.config.get("auto_subtitle") else None

    @staticmethod
    def _get_font_path(font_name: str = "arial") -> str:
        """Lấy đường dẫn font đầy đủ trên Windows cho FFmpeg."""
        import sys
        if sys.platform == "win32":
            fonts_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
            candidates = [f"{font_name}.ttf", f"{font_name}b.ttf", f"{font_name}bd.ttf"]
            for candidate in candidates:
                font_path = fonts_dir / candidate
                if font_path.exists():
                    # FFmpeg filter cần forward slash và CẦN ESCAPE dấu hai chấm (:) ở tên ổ đĩa (vd C\:/Windows)
                    font_str = str(font_path).replace("\\", "/")
                    return font_str.replace(":", "\\:")
        return font_name

    def _get_random_music(self) -> Optional[str]:
        specific_music = self.config.get("specific_music_path")
        if specific_music and Path(specific_music).exists():
            logger.info(f"Using specific music: {Path(specific_music).name}")
            return str(specific_music)

        music_files = list(MUSIC_DIR.glob("*.mp3")) + list(MUSIC_DIR.glob("*.m4a"))
        if not music_files:
            return None
        selected = random.choice(music_files)
        logger.info(f"Selected music: {selected.name}")
        return str(selected)

    def _get_video_duration(self, input_path: str) -> float:
        """Lấy thời lượng video bằng ffprobe."""
        cmd = [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of",
            "default=noprint_wrappers=1:nokey=1", input_path
        ]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    def process_video(self, input_path: str, title: str = None,
                      output_path: str = None) -> Optional[str]:
        input_path = Path(input_path)
        if not input_path.exists():
            logger.error(f"Video file not found: {input_path}")
            return None

        if not output_path:
            output_path = PROCESSED_DIR / f"processed_{input_path.name}"
        output_path = Path(output_path)

        logger.info(f"Processing video: {input_path.name} (Native FFmpeg)")
        
        video_duration = self._get_video_duration(str(input_path))
        if video_duration <= 0:
            logger.error("Could not read video duration.")
            return None

        filters = []
        audio_filters = []
        inputs = ["-y", "-i", str(input_path)] # Input 0 là video gốc
        
        # 1. Mirror
        if self.config.get("mirror", True):
            filters.append("hflip")
            logger.debug("  ✓ Mirrored")

        # 2. Brightness
        brightness = self.config.get("brightness_adjust", 1.0)
        if brightness != 1.0:
            # eq=contrast=1.05 hoặc eq=brightness=0.05
            filters.append(f"eq=brightness={brightness - 1.0:.2f}")
            logger.debug(f"  ✓ Brightness: {brightness}x")
            
        # 3. Speed
        speed_range = self.config.get("speed_range", (0.97, 1.03))
        speed_factor = random.uniform(*speed_range)
        if speed_factor != 1.0:
            filters.append(f"setpts={1.0/speed_factor:.4f}*PTS")
            audio_filters.append(f"atempo={speed_factor:.4f}")
            logger.debug(f"  ✓ Speed: {speed_factor:.3f}x")

        # 5. Phụ đề (Auto Subtitle + Black bar)
        has_subtitles = False
        srt_path = None
        if self.config.get("auto_subtitle") and self.subtitle_generator:
            srt_path = PROCESSED_DIR / f"{input_path.stem}.srt"
            logger.info(f"  Running AI to transcribe & translate subtitles...")
            generated_srt = self.subtitle_generator.generate_srt(
                str(input_path), str(srt_path), src_lang="zh", target_lang="vi"
            )
            if generated_srt:
                # Subtitles chèn lên phần đã làm mờ, nâng MarginV=40 để tránh bị che bởi UI TikTok
                srt_path_unix = str(srt_path).replace("\\", "/").replace(":", "\\:")
                filters.append(f"subtitles='{srt_path_unix}':force_style='FontSize=16,Alignment=2,MarginV=40,BorderStyle=1,Outline=1.5,Shadow=1'")
                has_subtitles = True
                logger.debug("  ✓ Subtitles applied")

        # 6. Audio / Dubbing / Music
        final_audio_input_idx = 0
        has_dubbing = False
        mixed_audio_path = None
        
        if self.config.get("ai_dubbing") and has_subtitles and srt_path and srt_path.exists():
            from utils.tts_engine import generate_voiceover_from_srt, mix_audio_tracks
            logger.info("  🎙️ Generating AI Vietnamese voiceover...")
            voiceover_path = PROCESSED_DIR / f"{input_path.stem}_voiceover.mp3"
            
            tts_voice = self.config.get("tts_voice", "vi-VN-HoaiMyNeural")
            tts_rate = self.config.get("tts_rate", "+0%")
            
            vo_result = generate_voiceover_from_srt(
                str(srt_path), str(voiceover_path),
                video_duration=video_duration,
                voice=tts_voice, rate=tts_rate,
            )
            
            if vo_result:
                # Kiểm tra xem người dùng có chọn Ghép nhạc không
                bg_music_path = self._get_random_music() if self.config.get("replace_audio") else None
                mixed_audio_path = PROCESSED_DIR / f"{input_path.stem}_mixed.mp3"
                orig_vol = self.config.get("original_audio_volume", 0.15) # Mặc định nhạc nền 15%
                
                if bg_music_path:
                    logger.info("  🎵 Mixing AI voiceover with background music (Original voice muted)...")
                    from utils.tts_engine import mix_audio_tracks
                    mixed = mix_audio_tracks(
                        str(bg_music_path), str(voiceover_path),
                        str(mixed_audio_path), original_volume=orig_vol,
                    )
                else:
                    # Nếu KHÔNG ghép nhạc, chỉ dùng giọng đọc AI (tắt toàn bộ âm thanh và nhạc gốc)
                    logger.info("  🎙️ Using AI voiceover only (Background muted)...")
                    import shutil
                    shutil.copy(str(voiceover_path), str(mixed_audio_path))
                    mixed = True
                    
                if mixed:
                    inputs.extend(["-i", str(mixed_audio_path)])
                    final_audio_input_idx = len(inputs) // 2 - 1
                    has_dubbing = True
                    logger.debug(f"  ✓ AI Dubbing applied")
                    
                # Cleanup temp audios
                try:
                    if voiceover_path.exists(): voiceover_path.unlink()
                except: pass

        if self.config.get("replace_audio", True) and not has_dubbing:
            music_path = self._get_random_music()
            if music_path:
                inputs.extend(["-stream_loop", "-1", "-i", music_path])
                final_audio_input_idx = len(inputs) // 2 - 1
                logger.debug("  ✓ Audio replaced with Vietnamese music")
                
        # Xây dựng lệnh FFmpeg cuối cùng
        cmd = ["ffmpeg"] + inputs
        
        # Build filter complex
        filter_complex = ""
        last_vid_pad = "0:v"
        
        if has_subtitles:
            # Tách luồng, cắt 15% dưới cùng, làm mờ, rồi chèn đè lại lên luồng chính
            filter_complex += f"[{last_vid_pad}]split=2[vmain][vtmp];"
            filter_complex += f"[vtmp]crop=iw:ih*0.15:0:ih*0.85,boxblur=20:5[vblur];"
            filter_complex += f"[vmain][vblur]overlay=0:H-h[vwithblur];"
            last_vid_pad = "vwithblur"

        if filters:
            filter_complex += f"[{last_vid_pad}]{','.join(filters)}[vout];"
        else:
            filter_complex += f"[{last_vid_pad}]copy[vout];"
            
        if audio_filters:
            filter_complex += f"[{final_audio_input_idx}:a]{','.join(audio_filters)}[aout]"
        else:
            filter_complex += f"[{final_audio_input_idx}:a]anull[aout]"

        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", "[vout]", "-map", "[aout]"])
        
        # Cắt thời lượng
        cmd.extend(["-t", str(video_duration / speed_factor)])
        
        # Encode settings
        cmd.extend([
            "-c:v", self.config.get("output_codec", "libx264"),
            "-preset", "fast",
            "-b:v", self.config.get("output_bitrate", "5000k"),
            "-c:a", self.config.get("output_audio_codec", "aac"),
            "-b:a", "192k",
            str(output_path)
        ])

        logger.info(f"  Exporting with FFmpeg: {output_path.name}...")
        try:
            # Chạy FFmpeg ẩn đi output, nếu lỗi thì bắt output
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            file_size = output_path.stat().st_size / 1024 / 1024
            logger.info(f"  ✅ Done: {output_path.name} ({file_size:.1f} MB)")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg failed: {e.stderr.decode('utf-8', errors='ignore')}")
            return None
        finally:
            if srt_path and srt_path.exists():
                try: srt_path.unlink()
                except: pass
            if has_dubbing and mixed_audio_path:
                try: Path(mixed_audio_path).unlink()
                except: pass

        return str(output_path)

    def process_downloaded_videos(self, titles: dict = None, limit: int = 10, video_ids: list = None) -> list:
        videos = self.db.get_downloaded_videos(limit=limit)
        if video_ids is not None:
            videos = [v for v in videos if v["video_id"] in video_ids]
        if not videos:
            logger.info("No downloaded videos to process")
            return []

        results = []
        titles = titles or {}
        for video in videos:
            video_id = video["video_id"]
            title = titles.get(video_id) or self._generate_title(video)
            processed_path = self.process_video(input_path=video["download_path"], title=title)
            if processed_path:
                self.db.update_translated_title(video_id, title)
                self.db.update_video_status(video_id=video_id, status="processed", processed_path=processed_path)
                results.append(processed_path)
            else:
                self.db.update_video_status(video_id=video_id, status="failed", error_message="Processing failed")

        logger.info(f"Processed {len(results)}/{len(videos)} videos")
        return results

    def _generate_title(self, video: dict) -> str:
        from utils.translator import translate_description
        original_title = video.get("title", "")
        if original_title and len(original_title) > 3:
            translated = translate_description(original_title)
            if translated and len(translated) > 2:
                logger.info(f"  🇻🇳 Dịch title: {translated[:60]}")
                return translated

        templates = [
            "Nhảy đẹp quá 😍🔥", "Dance cover cực đỉnh 💃✨", "Ai nhảy đẹp hơn? 🤔🔥",
            "Trend mới cực hot 🔥💃", "Xinh quá nhảy quá đẹp 😍", "Bước nhảy gây sốt 💥✨",
            "Nhảy siêu cuốn 🎵💃", "Có ai nhảy được như này? 🤩", "Hot girl nhảy siêu đỉnh 🔥",
            "Chill cùng điệu nhảy 🎶💃", "Nhảy cùng xu hướng mới 🌟", "Cover dance viral 💫🔥"
        ]
        return random.choice(templates)
