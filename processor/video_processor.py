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
from typing import Optional, Callable

from loguru import logger

from config.settings import PROCESSOR_CONFIG, get_user_processed_dir, get_user_downloads_dir, MUSIC_DIR, BASE_DIR
from database.db_manager import DatabaseManager
from processor.subtitle_generator import SubtitleGenerator

def get_bin_path(name: str) -> str:
    path = BASE_DIR / f"{name}.exe"
    if path.exists():
        return str(path)
    return name

FFPROBE_BIN = get_bin_path("ffprobe")
FFMPEG_BIN = get_bin_path("ffmpeg")


class VideoProcessor:
    """Xử lý video dance Douyin bằng Native FFmpeg (Siêu tốc)."""

    def __init__(self, db: DatabaseManager = None, username: str = None):
        self.db = db or DatabaseManager()
        self.config = PROCESSOR_CONFIG
        self.username = username or "default"
        self.current_username = self.username
        self.downloads_dir = get_user_downloads_dir(self.username)
        self.processed_dir = get_user_processed_dir(self.username)
        
        # Thêm default config cho auto_subtitle
        if "auto_subtitle" not in self.config:
            self.config["auto_subtitle"] = True
            
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        MUSIC_DIR.mkdir(parents=True, exist_ok=True)
        
        whisper_model = self.config.get("whisper_model", "base")
        self.subtitle_generator = SubtitleGenerator(model_size=whisper_model) if self.config.get("auto_subtitle") else None

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
        cmd = [FFPROBE_BIN, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", input_path]
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=creationflags)
            return float(result.stdout.strip())
        except:
            return -1.0

    def _get_video_height(self, input_path: str) -> int:
        cmd = [FFPROBE_BIN, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=height", "-of", "default=noprint_wrappers=1:nokey=1", input_path]
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=creationflags)
            return int(result.stdout.strip())
        except:
            return 1920 # Fallback 1080p portrait (1080x1920)

    def process_video(self, input_path: str, title: str = None,
                      output_path: str = None, progress_cb: Optional[Callable] = None) -> Optional[str]:
        input_path = Path(input_path)
        if not input_path.exists():
            msg = f"Lỗi: Không tìm thấy file gốc {input_path.name}"
            logger.error(msg)
            if progress_cb: progress_cb(0, msg)
            return None

        if not output_path:
            output_path = get_user_processed_dir(self.current_username) / f"processed_{input_path.name}"
        output_path = Path(output_path)

        if progress_cb:
            progress_cb(5, "Đang chuẩn bị...")
            
        logger.info(f"Processing video: {input_path.name} (Native FFmpeg)")
        
        video_duration = self._get_video_duration(str(input_path))
        if video_duration <= 0:
            msg = "Lỗi: Không thể đọc thời lượng video (Thiếu ffprobe hoặc file lỗi)"
            logger.error(msg)
            if progress_cb: progress_cb(0, msg)
            return None

        inputs = ["-i", str(input_path)]
        filters = []
        audio_filters = []
        # --- SENIOR+ ANTI-REUP PIPELINE (Phá mã MD5, pHash, AI Detection) ---
        platform_mode = self.config.get("platform", "tiktok")
        yt_cfg = self.config.get("youtube_bypass", {}) if platform_mode == "youtube" else {}

        # 1. Mirror (Lật video)
        if self.config.get("mirror", True):
            filters.append("hflip")
            logger.debug("  ✓ Mirrored (Basic)")

        # 2. YouTube Bypass: Crop & Zoom (Cắt sâu 15% viền để phá ma trận Content ID)
        if platform_mode == "youtube" and yt_cfg.get("crop_zoom", 1.0) > 1.0:
            cz = yt_cfg.get("crop_zoom", 1.15)
            filters.append(f"crop=iw/{cz:.2f}:ih/{cz:.2f},scale=iw:ih")
            logger.debug(f"  ✓ YouTube Bypass: Crop & Zoom {cz:.2f}x")

        # 3. Rotation siêu nhỏ & Vignette (Phá vỡ thuật toán Spatial pHash)
        rot_angle = random.uniform(-0.02, 0.02) # radians
        filters.append(f"rotate={rot_angle}:c=black:ow=iw:oh=ih")
        filters.append("vignette=PI/4")
        logger.debug(f"  ✓ Micro-Rotation ({rot_angle:.4f} rad) & Vignette")

        # 4. Color Grading chuyên sâu & Noise (YouTube Mode màu đậm hơn + Noise)
        brightness = self.config.get("brightness_adjust", 1.0)
        contrast = random.uniform(1.05, 1.12) if platform_mode == "youtube" else random.uniform(1.02, 1.07)
        saturation = random.uniform(1.05, 1.15) if platform_mode == "youtube" else random.uniform(1.02, 1.10)
        gamma = random.uniform(0.92, 1.08)
        
        filters.append(f"eq=brightness={brightness - 1.0:.2f}:contrast={contrast:.2f}:saturation={saturation:.2f}:gamma={gamma:.2f}")
        
        if platform_mode == "youtube" and yt_cfg.get("add_noise", True):
            filters.append("noise=alls=3:allf=t+u")
            logger.debug("  ✓ YouTube Bypass: Added Grain Noise")
            
        logger.debug("  ✓ Color Grading - Bypass Frame MD5/pHash")
        
        # -------------------------------------------------------------------------------
            
        # 5. Phụ đề (Auto Subtitle + Black bar)
        has_subtitles = False
        srt_path = None
        if self.config.get("auto_subtitle") and self.subtitle_generator:
            if progress_cb:
                progress_cb(10, "Đang dịch AI...")
            srt_path = get_user_processed_dir(self.current_username) / f"{input_path.stem}.srt"
            logger.info(f"  Running AI to transcribe & translate subtitles...")
            
            try:
                generated_srt = self.subtitle_generator.generate_srt(
                    str(input_path), str(srt_path), src_lang="zh", target_lang="vi", progress_cb=progress_cb
                )
            except Exception as e:
                generated_srt = None
                if progress_cb: progress_cb(10, f"Lỗi nghiêm trọng Subtitle AI: {str(e)[:100]}")
                
            if generated_srt:
                clean_srt_path = str(srt_path).replace('.srt', '_clean.srt')
                
                # Sử dụng đường dẫn tương đối để tránh lỗi dấu hai chấm (:) của ổ đĩa trên Windows trong FFmpeg filter
                rel_srt_path = os.path.relpath(clean_srt_path, os.getcwd())
                clean_srt_str = str(rel_srt_path).replace("\\", "/")
                
                # Escape các ký tự đặc biệt còn lại (nếu có trong tên file)
                for char in [" ", ",", "="]:
                    clean_srt_str = clean_srt_str.replace(char, f"\\{char}")
                    
                srt_path_unix = clean_srt_str
                
                # Lấy cấu hình vùng mờ để tính tọa độ
                blur_height = self.config.get("blur_height", 0.15)
                blur_pos = self.config.get("blur_position", "bottom")
                video_height = self._get_video_height(str(input_path))

                # Xử lý Vị trí Subtitle (Tuỳ chỉnh theo UI)
                sub_pos_opt = self.config.get("sub_pos", "Đè lên vùng mờ")
                if "Đè lên vùng mờ" in sub_pos_opt:
                    # Tính khoảng cách MarginV để chữ nằm vào giữa vùng làm mờ
                    margin_v = int((blur_height * video_height) / 2)
                    if blur_pos == "bottom":
                        alignment = 2 # Néo vào đáy
                    else:
                        alignment = 8 # Néo vào đỉnh
                elif "Cao" in sub_pos_opt:
                    margin_v = 280  # Đẩy lên cao tránh UI TikTok
                    alignment = 2
                else: # Giữa màn hình
                    margin_v = 0
                    alignment = 5 # Center screen

                # Style đoản kịch chuyên nghiệp (Trắng tinh tế, viền mỏng, đổ bóng nhẹ)
                style = f"FontName=Arial,FontSize=14,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Alignment={alignment},MarginV={margin_v},Bold=1,BorderStyle=1,Outline=1.2,Shadow=0.5"
                filters.append(f"subtitles={srt_path_unix}:force_style='{style}'")
                has_subtitles = True
                logger.debug("  ✓ Subtitles applied")
            else:
                if progress_cb: progress_cb(10, "Lỗi: Không thể tạo Phụ đề (Bỏ qua Sub & Voice)")
                logger.warning("Subtitle generation failed or returned None, skipping subtitles.")

        # 6. Speed (Phải áp dụng sau subtitles để sub được scale đúng tốc độ cùng với video)
        speed_range = self.config.get("speed_range", (0.97, 1.03))
        speed_factor = random.uniform(*speed_range)
        if speed_factor != 1.0:
            filters.append(f"setpts={1.0/speed_factor:.4f}*PTS")
            audio_filters.append(f"atempo={speed_factor:.4f}")
            logger.debug(f"  ✓ Speed: {speed_factor:.3f}x")

        # 7. Audio / Dubbing / Music
        final_audio_input_idx = 0
        has_dubbing = False
        mixed_audio_path = None
        
        if self.config.get("ai_dubbing") and has_subtitles and srt_path and srt_path.exists():
            from utils.tts_engine import generate_voiceover_from_srt, mix_audio_tracks
            if progress_cb: progress_cb(30, "Đang đọc thuyết minh (TTS)...")
            logger.info("  🎙️ Generating AI Vietnamese voiceover...")
            voiceover_path = get_user_processed_dir(self.current_username) / f"{input_path.stem}_voiceover.mp3"
            
            tts_voice = self.config.get("tts_voice", "vi-VN-HoaiMyNeural")
            tts_rate = self.config.get("tts_rate", "+0%")
            
            vo_result = generate_voiceover_from_srt(
                str(srt_path), str(voiceover_path),
                video_duration=video_duration,
                voice=tts_voice, rate=tts_rate,
            )
            
            if vo_result:
                if progress_cb: progress_cb(60, "Đang ghép nhạc...")
                mixed_audio_path = get_user_processed_dir(self.current_username) / f"{input_path.stem}_mixed.mp3"
                
                # config values
                bg_vol = self.config.get("bg_music_volume", 0.15)
                mute_original = self.config.get("mute_original_audio", False)
                replace_audio = self.config.get("replace_audio", True)
                
                bg_music_path = self._get_random_music() if replace_audio else None
                
                if bg_music_path:
                    # REVIEW PHIM STYLE: Dùng nhạc nền random + Voiceover.
                    # Nhạc nền random KHÔNG BỊ MUTE bởi tùy chọn Tắt tiếng video gốc.
                    logger.info("  🎵 Review Phim Style: Mixing AI voiceover with background music (Ducking)...")
                    mixed = mix_audio_tracks(
                        str(bg_music_path), str(voiceover_path),
                        str(mixed_audio_path), original_volume=bg_vol,
                    )
                else:
                    # ĐOẢN KỊCH STYLE: Dùng âm thanh gốc + Voiceover
                    # Nếu người dùng chọn Tắt âm thanh gốc thì mute hoàn toàn (0.0), nếu không thì dùng bg_vol
                    target_vol = 0.0 if mute_original else bg_vol
                    logger.info(f"  🎵 Đoản Kịch Style: Mixing AI voiceover with ORIGINAL VIDEO AUDIO (vol={target_vol})...")
                    mixed = mix_audio_tracks(
                        str(input_path), str(voiceover_path),
                        str(mixed_audio_path), original_volume=target_vol,
                    )
                    
                if mixed:
                    inputs.extend(["-i", str(mixed_audio_path)])
                    final_audio_input_idx = inputs.count("-i") - 1
                    has_dubbing = True
                    logger.debug(f"  ✓ AI Dubbing with Audio Ducking applied")
                    
                try:
                    if voiceover_path.exists(): voiceover_path.unlink()
                except: pass

        if self.config.get("replace_audio", True) and not has_dubbing:
            music_path = self._get_random_music()
            if music_path:
                inputs.extend(["-stream_loop", "-1", "-i", music_path])
                final_audio_input_idx = inputs.count("-i") - 1
                logger.debug("  ✓ Audio replaced with Vietnamese music")

        # 8. Logo Watermark Input (Nếu có cấu hình Logo)
        logo_input_idx = None
        logo_path = yt_cfg.get("logo_path")
        if logo_path and Path(logo_path).exists():
            inputs.extend(["-i", str(logo_path)])
            logo_input_idx = inputs.count("-i") - 1
            logger.info(f"  🏷️ YouTube Bypass: Adding Logo Watermark ({Path(logo_path).name})")
                
        # Xây dựng lệnh FFmpeg cuối cùng
        cmd = [FFMPEG_BIN, "-y"] + inputs
        
        # Build filter complex
        filter_complex = ""
        last_vid_pad = "0:v"
        
        blur_enabled = self.config.get("blur_enabled", True)
        if blur_enabled:
            blur_height = self.config.get("blur_height", 0.15)
            blur_pos = self.config.get("blur_position", "bottom")
            
            filter_complex += f"[{last_vid_pad}]split=2[vmain][vtmp];"
            if blur_pos == "bottom":
                # Crop phần dưới cùng
                crop_y = f"ih*{1.0 - blur_height}"
                filter_complex += f"[vtmp]crop=iw:ih*{blur_height}:0:{crop_y},gblur=sigma=15[vblur];"
                filter_complex += f"[vmain][vblur]overlay=0:H*{1.0 - blur_height}[vwithblur];"
            else:
                # Crop phần trên cùng
                filter_complex += f"[vtmp]crop=iw:ih*{blur_height}:0:0,gblur=sigma=15[vblur];"
                filter_complex += f"[vmain][vblur]overlay=0:0[vwithblur];"
                
            last_vid_pad = "vwithblur"

        if filters:
            filter_complex += f"[{last_vid_pad}]{','.join(filters)}[vout_main];"
            last_vid_pad = "vout_main"

        # Nếu có Logo Watermark -> ghép Logo vào video stream
        if logo_input_idx is not None:
            logo_pos = yt_cfg.get("logo_position", "top_right")
            logo_scale = yt_cfg.get("logo_scale", 0.15)
            
            # Scale logo
            filter_complex += f"[{logo_input_idx}:v]scale=iw*{logo_scale}:-1[scaled_logo];"
            
            # Tùy chỉnh vị trí overlay
            if logo_pos == "top_left":
                overlay_xy = "x=20:y=20"
            elif logo_pos == "bottom_left":
                overlay_xy = "x=20:y=main_h-overlay_h-50"
            elif logo_pos == "bottom_right":
                overlay_xy = "x=main_w-overlay_w-20:y=main_h-overlay_h-50"
            elif logo_pos == "floating":
                # Logo di chuyển chậm theo chu kỳ hình sin
                overlay_xy = "x='(main_w-overlay_w)/2+(main_w-overlay_w)/3*sin(t*0.5)':y='(main_h-overlay_h)/2+(main_h-overlay_h)/3*cos(t*0.3)'"
            else: # top_right
                overlay_xy = "x=main_w-overlay_w-20:y=20"
                
            filter_complex += f"[{last_vid_pad}][scaled_logo]overlay={overlay_xy}[vout];"
        else:
            if last_vid_pad != "0:v":
                filter_complex += f"[{last_vid_pad}]null[vout];"
            else:
                filter_complex += f"[0:v]null[vout];"
            
        if audio_filters:
            filter_complex += f"[{final_audio_input_idx}:a]{','.join(audio_filters)}[aout]"
        else:
            filter_complex += f"[{final_audio_input_idx}:a]anull[aout]"

        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", "[vout]", "-map", "[aout]"])
        
        # Cắt thời lượng
        cmd.extend(["-t", str(video_duration / speed_factor)])
        
        # Encode settings
        codec = self.config.get("output_codec", "libx264")
        preset = "ultrafast" if codec == "libx264" else "fast"
        
        cmd.extend([
            "-c:v", codec,
            "-preset", preset,         # Senior tip: ultrafast tăng tốc render x5 lần so với fast
            "-crf", "23",              # Senior tip: Chuẩn CRF 23 giúp giữ nguyên độ nét mà dung lượng giảm 4 lần
            "-pix_fmt", "yuv420p",     # Senior tip: Chuẩn màu 8-bit YUV420p tương thích 100% mọi trình duyệt Web & Mobile
            "-maxrate", "4000k",       # Ép trần bitrate tránh file bị phình to bất thường
            "-bufsize", "8000k",
            "-c:a", self.config.get("output_audio_codec", "aac"),
            "-b:a", "192k",
            "-threads", "0",           # Senior tip: Maximize CPU usage
            "-movflags", "+faststart", # Senior tip: Tối ưu chuẩn file mp4 cho upload (moov atom)
            str(output_path)
        ])

        if progress_cb:
            progress_cb(70, "Đang render Video...")

        logger.info(f"  Exporting with FFmpeg: {output_path.name}...")
        try:
            import re
            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW
                
            # Chạy FFmpeg ẩn đi output, bắt stderr để đọc thời gian thực
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=creationflags)
            
            time_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
            
            for line in process.stderr:
                match = time_pattern.search(line)
                if match and progress_cb:
                    h, m, s = match.groups()
                    current_time = int(h) * 3600 + int(m) * 60 + float(s)
                    
                    if video_duration > 0:
                        # Map ffmpeg time (0 -> duration) to progress (70 -> 99)
                        ffmpeg_progress = min(1.0, current_time / video_duration)
                        final_progress = 70 + (ffmpeg_progress * 29)
                        progress_cb(final_progress, "Đang render Video...")
                        
            process.wait()
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, cmd, stderr=process.stderr.read() if not process.stderr.closed else "")
                
            if not output_path.exists():
                raise Exception(f"FFmpeg chạy xong nhưng không tạo được file ở {output_path.name}")
                
            file_size = output_path.stat().st_size / 1024 / 1024
            if file_size <= 0:
                raise Exception("Lỗi: FFmpeg xuất ra file 0KB (Dữ liệu hỏng hoặc rỗng)")
                
            logger.info(f"  ✅ Done: {output_path.name} ({file_size:.1f} MB)")
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr if hasattr(e, 'stderr') else str(e)
            logger.error(f"FFmpeg failed: {err_msg}")
            if progress_cb: progress_cb(0, f"Lỗi FFmpeg: {err_msg[:200]}")
            return None
        except Exception as e:
            logger.error(f"FFmpeg process error: {str(e)}")
            if progress_cb: progress_cb(0, f"Lỗi hệ thống FFmpeg: {str(e)[:200]}")
            return None
        finally:
            if srt_path and srt_path.exists():
                try: srt_path.unlink()
                except: pass
                # Dọn cả file _clean.srt
                clean_srt = Path(str(srt_path).replace('.srt', '_clean.srt'))
                try:
                    if clean_srt.exists(): clean_srt.unlink()
                except: pass
            if has_dubbing and mixed_audio_path:
                try: Path(mixed_audio_path).unlink()
                except: pass

        return str(output_path)

    def process_downloaded_videos(self, titles: dict = None, limit: int = 10, video_ids: list = None, cancel_check: Optional[Callable[[], bool]] = None, progress_callback: Optional[Callable] = None) -> list:
        if video_ids:
            # Lấy không giới hạn nếu người dùng đã tick chọn cụ thể
            videos = self.db.get_downloaded_videos(limit=999999)
            if progress_callback: progress_callback("SYS", 0, f"[DEBUG] DB trả về {len(videos)} videos. Lọc theo {len(video_ids)} IDs...")
            videos = [v for v in videos if v["video_id"] in video_ids]
            if progress_callback: progress_callback("SYS", 0, f"[DEBUG] Sau lọc còn {len(videos)} videos hợp lệ.")
        else:
            videos = self.db.get_downloaded_videos(limit=limit)
            
        if not videos:
            logger.info("No downloaded videos to process")
            return []

        results = []
        titles = titles or {}
        for video in videos:
            if cancel_check and cancel_check():
                logger.warning("Quá trình xử lý video bị ngắt (Stop).")
                break
                
            video_id = video["video_id"]
            title = titles.get(video_id) or self._generate_title(video)
            
            # Wrap progress callback for this specific video
            # SENIOR FIX: vid=video_id để "đóng băng" giá trị tại thời điểm tạo closure
            def cb(pct, status, vid=video_id):
                if progress_callback:
                    progress_callback(vid, pct, status)
                    
            try:
                input_path = video.get("download_path")
                drive_download_id = video.get("drive_download_id")
                temp_downloaded_path = None
                
                # Cần tải từ Drive nếu không có file local
                if not input_path or not Path(input_path).exists():
                    if drive_download_id:
                        cb(10, "Đang tải video từ Google Drive...")
                        from uploader.google_drive_uploader import GoogleDriveUploader
                        uploader = GoogleDriveUploader(self.username or "default")
                        import uuid
                        temp_downloaded_path = str(self.downloads_dir / f"drive_temp_{uuid.uuid4().hex[:8]}.mp4")
                        if uploader.download_file(drive_download_id, temp_downloaded_path):
                            input_path = temp_downloaded_path
                        else:
                            raise Exception("Không thể tải video từ Google Drive")
                    else:
                        raise Exception("Không tìm thấy file video (cả local và Drive)")

                processed_path = self.process_video(input_path=input_path, title=title, progress_cb=cb)
                if processed_path:
                    from config.settings import GOOGLE_DRIVE_CONFIG
                    drive_processed_id = None
                    
                    if GOOGLE_DRIVE_CONFIG.get("auto_backup"):
                        try:
                            cb(95, "Đang đẩy thành phẩm lên Drive...")
                            from uploader.google_drive_uploader import GoogleDriveUploader
                            uploader = GoogleDriveUploader(self.username or "default")
                            drive_processed_id = uploader.upload_file(processed_path, delete_after=True, folder_name=video.get("author", "Unknown"))
                            processed_path = "" # Đã bị xóa trên máy
                        except Exception as e:
                            logger.error(f"Lỗi upload Drive khi process: {e}")
                            
                    self.db.update_translated_title(video_id, title)
                    self.db.update_video_status(video_id=video_id, status="processed", processed_path=processed_path, drive_processed_id=drive_processed_id)
                    cb(100, "Hoàn thành!")
                    results.append({"video_id": video_id, "processed_path": processed_path, "drive_processed_id": drive_processed_id})
                else:
                    self.db.update_video_status(video_id=video_id, status="failed", error_message="Processing failed")
                    cb(0, "Lỗi xử lý!")
                    
                # Clean up file tải tạm từ Drive nếu có
                if temp_downloaded_path and Path(temp_downloaded_path).exists():
                    try: Path(temp_downloaded_path).unlink()
                    except: pass

            except Exception as e:
                import traceback
                logger.error(f"Lỗi không xác định khi xử lý video {video_id}: {traceback.format_exc()}")
                self.db.update_video_status(video_id=video_id, status="failed", error_message=str(e))
                cb(0, f"Lỗi Code: {str(e)[:100]}")

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
