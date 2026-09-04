import os
import time
from pathlib import Path
from loguru import logger
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config.settings import COOKIES_DIR

# Yêu cầu quyền chỉ xem và quản lý các file do app này tạo ra trên Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive.file']

class GoogleDriveUploader:
    def __init__(self, username: str, client_secret_path: str = "config/client_secret.json"):
        self.username = username
        self.client_secret_path = client_secret_path
        self.token_path = COOKIES_DIR / username.replace("@", "_").replace(".", "_") / "drive_token.json"
        self.service = None
        
        # Đảm bảo thư mục cookies cho user tồn tại
        self.token_path.parent.mkdir(parents=True, exist_ok=True)

    def authenticate(self):
        """Xác thực với Google Drive bằng OAuth2."""
        creds = None
        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
            except Exception as e:
                logger.warning(f"Lỗi đọc token.json: {e}")
                
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    logger.warning(f"Lỗi refresh token: {e}")
                    creds = None

            if not creds:
                if not Path(self.client_secret_path).exists():
                    raise FileNotFoundError(f"Không tìm thấy file {self.client_secret_path}. Vui lòng tải file OAuth 2.0 Client ID từ Google Cloud Console và đổi tên thành client_secret.json để vào thư mục config.")
                
                flow = InstalledAppFlow.from_client_secrets_file(self.client_secret_path, SCOPES)
                # Mở trình duyệt để người dùng đăng nhập
                creds = flow.run_local_server(port=0)
                
            # Lưu lại thông tin xác thực cho lần sau
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
                
        self.service = build('drive', 'v3', credentials=creds)
        logger.info(f"Đã xác thực Google Drive thành công cho user: {self.username}")

    def _get_or_create_folder(self, folder_name: str, parent_id: str = None) -> str:
        """Lấy ID của thư mục nếu tồn tại, nếu chưa có thì tạo mới."""
        if not self.service:
            self.authenticate()
            
        # 1. Tìm thư mục
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
            
        response = self.service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = response.get('files', [])
        
        if files:
            return files[0].get('id')
            
        # 2. Không tìm thấy thì tạo mới
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        if parent_id:
            folder_metadata['parents'] = [parent_id]
            
        folder = self.service.files().create(body=folder_metadata, fields='id').execute()
        folder_id = folder.get('id')
        try:
            self.service.permissions().create(
                fileId=folder_id,
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()
        except Exception:
            pass
        return folder_id

    def upload_file(self, file_path: str, delete_after: bool = False, folder_name: str = None) -> str:
        """Upload file lên Google Drive. Tự động chia nhỏ (Chunked Upload) cho file lớn."""
        if not self.service:
            self.authenticate()
            
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File không tồn tại: {file_path}")

        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        logger.info(f"Bắt đầu upload {file_name} lên Google Drive ({file_size / (1024*1024):.2f} MB)...")

        file_metadata = {'name': file_name}
        
        # Nếu có truyền folder_name, thì gom vào folder 'DouyinBot' -> 'folder_name'
        if folder_name:
            try:
                root_folder_id = self._get_or_create_folder("DouyinBot")
                channel_folder_id = self._get_or_create_folder(folder_name, parent_id=root_folder_id)
                file_metadata['parents'] = [channel_folder_id]
            except Exception as e:
                logger.warning(f"Lỗi khi tạo thư mục trên Drive ({folder_name}): {e}")
        
        import mimetypes
        import gc
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = 'video/mp4' if file_path.lower().endswith(('.mp4', '.mov', '.mkv', '.avi', '.webm')) else 'application/octet-stream'
            
        file_metadata['mimeType'] = mime_type

        # Resumable upload cho các file lớn
        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
        request = self.service.files().create(body=file_metadata, media_body=media, fields='id')
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.debug(f"Đang upload {file_name}: {int(status.progress() * 100)}%")

        file_id = response.get('id')
        logger.info(f"✅ Upload thành công: {file_name} (File ID: {file_id})")
        
        # Tự động cấp quyền xem công khai (bất kỳ ai có link đều xem được mà không cần yêu cầu quyền)
        try:
            self.service.permissions().create(
                fileId=file_id,
                body={'type': 'anyone', 'role': 'reader'}
            ).execute()
        except Exception as e:
            logger.debug(f"Không thể gán quyền chia sẻ cho {file_id}: {e}")
        
        # Xóa file sau khi upload thành công (giải phóng handle stream để không dính WinError 32)
        if hasattr(media, '_fd') and media._fd:
            try:
                media._fd.close()
            except Exception:
                pass
        del request
        del media
        gc.collect()

        if delete_after:
            try:
                # Đợi một chút để nhả file descriptor trên Windows
                time.sleep(0.5)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.success(f"Đã xóa file local sau khi backup: {file_path}")
            except Exception as e:
                logger.error(f"Không thể xóa file {file_path}: {e}")
                
        return file_id

    def download_file(self, file_id: str, dest_path: str) -> bool:
        """Tải file từ Google Drive về máy cục bộ."""
        if not self.service:
            self.authenticate()
            
        import io
        from googleapiclient.http import MediaIoBaseDownload
        
        try:
            request = self.service.files().get_media(fileId=file_id)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
            with open(dest_path, "wb") as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                    if status:
                        logger.debug(f"Đang tải {os.path.basename(dest_path)}: {int(status.progress() * 100)}%")
                        
            logger.info(f"✅ Tải thành công từ Drive: {dest_path}")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi tải file {file_id} từ Drive: {e}")
            return False

    def delete_file(self, file_id: str) -> bool:
        """Xóa file trên Google Drive để giải phóng dung lượng."""
        if not self.service:
            self.authenticate()
            
        try:
            self.service.files().delete(fileId=file_id).execute()
            logger.info(f"🗑️ Đã xóa file {file_id} trên Google Drive.")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi xóa file {file_id} trên Drive: {e}")
            return False
