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
from pathlib import Path
from typing import Optional

from loguru import logger

from config.settings import PROCESSOR_CONFIG, PROCESSED_DIR, MUSIC_DIR
from database.db_manager import DatabaseManager
from processor.subtitle_generator import SubtitleGenerator


class VideoProcessor:
    """Xử lý video dance Douyin: mirror + speed + text overlay + nhạc Việt."""

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
        """Lấy đường dẫn font đầy đủ trên Windows (Pillow cần full path)."""
        import sys
        if sys.platform == "win32":
            fonts_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
            # Thử các tên file font phổ biến
            candidates = [
                f"{font_name}.ttf",
                f"{font_name}b.ttf",   # bold
                f"{font_name}bd.ttf",  # bold
            ]
            for candidate in candidates:
                font_path = fonts_dir / candidate
                if font_path.exists():
                    return str(font_path)
        return font_name  # Fallback: trả tên font (Linux/Mac tự resolve)

    def _get_random_music(self) -> Optional[str]:
        """Lấy file nhạc cụ thể (nếu có) hoặc random một file nhạc Việt từ thư mục music."""
        specific_music = self.config.get("specific_music_path")
        if specific_music and Path(specific_music).exists():
            logger.info(f"Using specific music: {Path(specific_music).name}")
            return str(specific_music)

        music_files = list(MUSIC_DIR.glob("*.mp3")) + list(MUSIC_DIR.glob("*.m4a"))
        if not music_files:
            logger.warning(
                f"Không có file nhạc nào trong: {MUSIC_DIR}\n"
                f"Hãy bỏ file nhạc (.mp3/.m4a) vào thư mục này để ghép nhạc Việt!"
            )
            return None
        selected = random.choice(music_files)
        logger.info(f"Selected music: {selected.name}")
        return str(selected)

    def process_video(self, input_path: str, title: str = None,
                      output_path: str = None) -> Optional[str]:
        """
        Pipeline xử lý video tổng hợp:
        1. Load video
        2. Mirror (lật ngang)
        3. Speed change nhẹ
        4. Thêm text overlay tiếng Việt
        5. Ghép nhạc Việt (nếu có)
        6. Adjust brightness
        7. Export video đã xử lý

        Args:
            input_path: Đường dẫn video gốc
            title: Text tiếng Việt để overlay lên video
            output_path: Đường dẫn output (tự tạo nếu không cung cấp)

        Returns:
            Đường dẫn file video đã xử lý, hoặc None nếu lỗi
        """
        try:
            # Lazy import moviepy (nặng, chỉ import khi cần)
            from moviepy import VideoFileClip, TextClip, CompositeVideoClip, AudioFileClip
        except ImportError:
            logger.error(
                "moviepy chưa được cài! Chạy: pip install moviepy"
            )
            return None

        input_path = Path(input_path)
        if not input_path.exists():
            logger.error(f"Video file not found: {input_path}")
            return None

        # Tạo output path
        if not output_path:
            output_path = PROCESSED_DIR / f"processed_{input_path.name}"
        output_path = Path(output_path)

        logger.info(f"Processing video: {input_path.name}")
        video = None

        try:
            # 1. Load video
            video = VideoFileClip(str(input_path))
            processed = video
            logger.debug(f"  Original: {video.duration:.1f}s, {video.size}")

            # 2. Mirror (lật ngang)
            if self.config.get("mirror", True):
                processed = processed.with_effects([
                    self._mirror_effect()
                ])
                logger.debug("  ✓ Mirrored")

            # 3. Speed change nhẹ
            speed_range = self.config.get("speed_range", (0.97, 1.03))
            speed_factor = random.uniform(*speed_range)
            if speed_factor != 1.0:
                processed = processed.with_speed_scaled(speed_factor)
                logger.debug(f"  ✓ Speed: {speed_factor:.3f}x")

            # 4. Thêm text overlay tiếng Việt (Tiêu đề trên cùng)
            if title and self.config.get("add_text", True):
                processed = self._add_text_overlay(processed, title)
                logger.debug(f"  ✓ Text overlay: {title[:30]}...")

            # 4.5. Phụ đề tiếng Việt tự động (Auto-Subtitle) dưới đáy video
            has_subtitles = False
            srt_path = None
            if self.config.get("auto_subtitle") and self.subtitle_generator:
                import pysrt
                srt_path = PROCESSED_DIR / f"{input_path.stem}.srt"
                
                logger.info(f"  Running AI to transcribe & translate subtitles...")
                generated_srt = self.subtitle_generator.generate_srt(
                    str(input_path), str(srt_path), src_lang="zh", target_lang="vi"
                )
                
                if generated_srt:
                    processed = self._add_subtitles(processed, generated_srt)
                    has_subtitles = True
                    logger.debug("  ✓ Subtitles applied (Chinese text covered)")

            # 4.6. Thuyết minh AI tiếng Việt (AI Dubbing)
            has_dubbing = False
            if self.config.get("ai_dubbing") and has_subtitles and srt_path and srt_path.exists():
                from utils.tts_engine import generate_voiceover_from_srt, mix_audio_tracks
                
                logger.info("  🎙️ Generating AI Vietnamese voiceover...")
                voiceover_path = PROCESSED_DIR / f"{input_path.stem}_voiceover.mp3"
                
                tts_voice = self.config.get("tts_voice", "vi-VN-HoaiMyNeural")
                tts_rate = self.config.get("tts_rate", "+0%")
                
                vo_result = generate_voiceover_from_srt(
                    str(srt_path), str(voiceover_path),
                    video_duration=processed.duration,
                    voice=tts_voice, rate=tts_rate,
                )
                
                if vo_result:
                    # Trích xuất audio gốc → mix với voiceover
                    original_audio_path = PROCESSED_DIR / f"{input_path.stem}_orig_audio.mp3"
                    mixed_audio_path = PROCESSED_DIR / f"{input_path.stem}_mixed.mp3"
                    
                    try:
                        # Export audio gốc ra file tạm
                        if processed.audio:
                            processed.audio.write_audiofile(
                                str(original_audio_path), logger=None
                            )
                            
                            orig_vol = self.config.get("original_audio_volume", 0.2)
                            mixed = mix_audio_tracks(
                                str(original_audio_path), str(voiceover_path),
                                str(mixed_audio_path), original_volume=orig_vol,
                            )
                            
                            if mixed:
                                from moviepy import AudioFileClip
                                mixed_clip = AudioFileClip(str(mixed_audio_path))
                                processed = processed.with_audio(mixed_clip)
                                has_dubbing = True
                                logger.debug(f"  ✓ AI Dubbing applied (voice={tts_voice}, orig@{orig_vol*100:.0f}%)")
                        else:
                            # Video không có audio gốc → dùng voiceover trực tiếp
                            from moviepy import AudioFileClip
                            vo_clip = AudioFileClip(str(voiceover_path))
                            processed = processed.with_audio(vo_clip)
                            has_dubbing = True
                            logger.debug("  ✓ AI Dubbing applied (no original audio)")
                    except Exception as e:
                        logger.warning(f"  ⚠ Mix audio failed: {e}")
                    finally:
                        # Cleanup temp audio files
                        for tmp in [original_audio_path, mixed_audio_path, voiceover_path]:
                            try:
                                if Path(tmp).exists():
                                    Path(tmp).unlink()
                            except Exception:
                                pass

            # Cleanup SRT file
            if srt_path and srt_path.exists():
                try:
                    srt_path.unlink()
                except Exception:
                    pass

            # 5. Ghép nhạc Việt (Chỉ ghép nếu không có subtitle/dubbing)
            if self.config.get("replace_audio", True) and not has_subtitles and not has_dubbing:
                music_path = self._get_random_music()
                if music_path:
                    processed = self._replace_audio(processed, music_path)
                    logger.debug("  ✓ Audio replaced with Vietnamese music")
            elif has_dubbing:
                logger.debug("  ✓ Using AI dubbed audio")
            elif has_subtitles:
                logger.debug("  ✓ Kept original audio because subtitles are present")

            # 6. Brightness adjustment
            brightness = self.config.get("brightness_adjust", 1.0)
            if brightness != 1.0:
                processed = processed.image_transform(
                    lambda frame: self._adjust_brightness(frame, brightness)
                )
                logger.debug(f"  ✓ Brightness: {brightness}x")

            # 7. Export
            logger.info(f"  Exporting: {output_path.name}...")
            processed.write_videofile(
                str(output_path),
                codec=self.config.get("output_codec", "libx264"),
                audio_codec=self.config.get("output_audio_codec", "aac"),
                bitrate=self.config.get("output_bitrate", "5000k"),
                fps=self.config.get("output_fps", 30),
                logger=None,  # Tắt moviepy progress bar (dùng loguru thay)
                threads=4,
            )

            file_size = output_path.stat().st_size / 1024 / 1024
            logger.info(
                f"  ✅ Done: {output_path.name} ({file_size:.1f} MB)"
            )
            return str(output_path)

        except Exception as e:
            logger.error(f"Error processing video {input_path.name}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
        finally:
            if video:
                try:
                    video.close()
                except Exception:
                    pass

    def _mirror_effect(self):
        """Tạo mirror effect cho moviepy v2."""
        from moviepy import vfx
        return vfx.MirrorX()

    def _add_text_overlay(self, video, text: str):
        """Thêm text overlay tiếng Việt lên video."""
        try:
            from moviepy import TextClip, CompositeVideoClip

            text_config = self.config.get("text_overlay", {})
            font_size = text_config.get("font_size", 45)
            font_color = text_config.get("font_color", "white")
            position = text_config.get("position", "top")
            margin = text_config.get("margin", 30)

            # Xác định vị trí
            if position == "top":
                pos = ("center", margin)
            elif position == "bottom":
                pos = ("center", video.h - margin - font_size - 20)
            else:
                pos = ("center", "center")

            # Tạo text clip
            txt_clip = (
                TextClip(
                    text=text,
                    font_size=font_size,
                    color=font_color,
                    font=self._get_font_path("arial"),
                    stroke_color="black",
                    stroke_width=2,
                    text_align="center",
                    size=(video.w - 60, None),
                    method="caption",
                )
                .with_position(pos)
                .with_duration(video.duration)
            )

            # Tạo background cho text (nền đen trong suốt)
            bg_color = text_config.get("bg_color", (0, 0, 0, 160))
            # Composite
            result = CompositeVideoClip([video, txt_clip])
            return result

        except Exception as e:
            logger.warning(f"Could not add text overlay: {e}")
            return video

    def _add_subtitles(self, video, srt_path: str):
        """Đọc file SRT, che kín chữ gốc tiếng Trung bằng thanh đen,
        rồi đè phụ đề tiếng Việt lên trên."""
        try:
            import pysrt
            from moviepy import TextClip, CompositeVideoClip, ColorClip
            
            subs = pysrt.open(srt_path)
            overlay_clips = []
            
            # ── BƯỚC 1: Tạo thanh đen đặc che kín vùng chữ gốc Trung Quốc ──
            # Thanh đen phủ kín 1/5 dưới đáy video, chạy suốt video
            cover_height = max(int(video.h * 0.18), 120)  # ~18% chiều cao, tối thiểu 120px
            black_bar = (
                ColorClip(
                    size=(video.w, cover_height),
                    color=(0, 0, 0),  # Đen đặc 100%
                )
                .with_position((0, video.h - cover_height))
                .with_duration(video.duration)
                .with_opacity(0.92)  # Gần đen hoàn toàn, nhẹ nhàng
            )
            overlay_clips.append(black_bar)
            
            # ── BƯỚC 2: Chèn phụ đề tiếng Việt lên thanh đen ──
            font_size = 42
            # Vị trí chữ: căn giữa thanh đen (cách đáy video ~40-60px)
            text_y = video.h - cover_height + (cover_height // 2) - (font_size // 2) - 5
            
            for sub in subs:
                start_time = sub.start.ordinal / 1000.0
                end_time = sub.end.ordinal / 1000.0
                
                txt_clip = (
                    TextClip(
                        text=sub.text,
                        font_size=font_size,
                        color="white",
                        font=self._get_font_path("arial"),
                        stroke_color="black",
                        stroke_width=2,
                        text_align="center",
                        size=(video.w - 40, None),
                        method="caption",
                    )
                    .with_position(("center", text_y))
                    .with_start(start_time)
                    .with_end(end_time)
                )
                overlay_clips.append(txt_clip)
                
            if overlay_clips:
                return CompositeVideoClip([video] + overlay_clips)
                
            return video
            
        except Exception as e:
            logger.error(f"Lỗi khi ghép subtitles: {e}")
            return video

    def _replace_audio(self, video, music_path: str):
        """Thay thế audio của video bằng nhạc Việt."""
        try:
            from moviepy import AudioFileClip

            music = AudioFileClip(music_path)

            # Cắt nhạc cho vừa với video duration
            if music.duration > video.duration:
                # Random start point trong nhạc
                max_start = music.duration - video.duration
                start = random.uniform(0, max_start) if max_start > 0 else 0
                music = music.subclipped(start, start + video.duration)
            else:
                # Nếu nhạc ngắn hơn video, loop nhạc
                from moviepy import concatenate_audioclips
                loops_needed = int(video.duration / music.duration) + 1
                music = concatenate_audioclips([music] * loops_needed)
                music = music.subclipped(0, video.duration)

            # Fade in/out
            music = music.with_effects([])

            return video.with_audio(music)

        except Exception as e:
            logger.warning(f"Could not replace audio: {e}")
            return video

    def _adjust_brightness(self, frame, factor: float):
        """Điều chỉnh brightness của frame."""
        import numpy as np
        adjusted = frame.astype(np.float64) * factor
        return np.clip(adjusted, 0, 255).astype(np.uint8)

    def process_downloaded_videos(self, titles: dict = None, limit: int = 10, video_ids: list = None) -> list:
        """
        Xử lý tất cả video đã download chưa processed.

        Args:
            titles: Dict mapping video_id → title tiếng Việt.
                    Nếu None, sẽ tạo title generic.
            limit: Số lượng video tối đa xử lý
            video_ids: Danh sách ID các video cụ thể muốn xử lý (nếu có)

        Returns:
            List các đường dẫn video đã xử lý
        """
        videos = self.db.get_downloaded_videos(limit=limit)
        
        # Lọc danh sách theo video_ids nếu người dùng chọn
        if video_ids is not None:
            videos = [v for v in videos if v["video_id"] in video_ids]
            
        if not videos:
            logger.info("No downloaded videos to process")
            return []

        results = []
        titles = titles or {}

        for video in videos:
            video_id = video["video_id"]

            # Lấy title từ mapping hoặc tạo title generic
            title = titles.get(video_id) or self._generate_title(video)

            # Process video
            processed_path = self.process_video(
                input_path=video["download_path"],
                title=title,
            )

            if processed_path:
                # Lưu title đã dịch vào DB để uploader dùng
                self.db.update_translated_title(video_id, title)
                self.db.update_video_status(
                    video_id=video_id,
                    status="processed",
                    processed_path=processed_path,
                )
                results.append(processed_path)
            else:
                self.db.update_video_status(
                    video_id=video_id,
                    status="failed",
                    error_message="Processing failed",
                )

        logger.info(f"Processed {len(results)}/{len(videos)} videos")
        return results

    def _generate_title(self, video: dict) -> str:
        """Dịch title gốc (tiếng Trung) sang tiếng Việt.
        Fallback: dùng template tiếng Việt ngẫu nhiên."""
        from utils.translator import translate_description

        original_title = video.get("title", "")

        # Thử dịch title gốc sang tiếng Việt
        if original_title and len(original_title) > 3:
            translated = translate_description(original_title)
            if translated and len(translated) > 2:
                logger.info(f"  🇻🇳 Dịch title: {translated[:60]}")
                return translated

        # Fallback: template tiếng Việt ngẫu nhiên
        templates = [
            "Nhảy đẹp quá 😍🔥",
            "Dance cover cực đỉnh 💃✨",
            "Ai nhảy đẹp hơn? 🤔🔥",
            "Trend mới cực hot 🔥💃",
            "Xinh quá nhảy quá đẹp 😍",
            "Bước nhảy gây sốt 💥✨",
            "Nhảy siêu cuốn 🎵💃",
            "Có ai nhảy được như này? 🤩",
            "Hot girl nhảy siêu đỉnh 🔥",
            "Chill cùng điệu nhảy 🎶💃",
            "Nhảy cùng xu hướng mới 🌟",
            "Cover dance viral 💫🔥",
        ]
        return random.choice(templates)
