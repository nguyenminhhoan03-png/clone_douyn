"""
Backward-compatibility wrapper for UploadLogHistoryDialog.
Tự động kế thừa và chuyển tiếp tới UnifiedLogHistoryDialog với initial_module='upload'.
"""
from ui.unified_log_dialog import UnifiedLogHistoryDialog
from uploader.upload_logger import UploadLogManager, UPLOAD_LOGS_DIR


class UploadLogHistoryDialog(UnifiedLogHistoryDialog):
    """Cửa sổ tra cứu lịch sử và chi tiết logs các phiên Upload (kế thừa UnifiedLogHistoryDialog)."""

    def __init__(self, master, **kwargs):
        kwargs.pop("initial_module", None)
        super().__init__(master, initial_module="upload", **kwargs)
