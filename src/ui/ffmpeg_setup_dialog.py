from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar, QPushButton,
)

from src.utils.ffmpeg_manager import FFmpegManager


class _DownloadThread(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool)

    def run(self):
        def callback(percent: int, message: str):
            self.progress.emit(percent, message)

        success = FFmpegManager.download(progress_callback=callback)
        self.finished.emit(success)


class FFmpegSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FFmpeg 未安装")
        self.setFixedWidth(460)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._thread = None
        self._success = False

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        info = QLabel(
            "未检测到 FFmpeg，视频合成功能需要 FFmpeg 才能运行。\n\n"
            "点击「下载安装」将自动下载并安装到项目 bin/ 目录（约 80 MB）。"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self._status_label = QLabel("就绪")
        layout.addWidget(self._status_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        btn_layout = QHBoxLayout()
        self._download_btn = QPushButton("下载安装")
        self._skip_btn = QPushButton("跳过")
        btn_layout.addWidget(self._download_btn)
        btn_layout.addWidget(self._skip_btn)
        layout.addLayout(btn_layout)

        self._download_btn.clicked.connect(self._start_download)
        self._skip_btn.clicked.connect(self.reject)

    def _start_download(self):
        self._download_btn.setEnabled(False)
        self._skip_btn.setEnabled(False)
        self._status_label.setText("准备下载...")

        self._thread = _DownloadThread(self)
        self._thread.progress.connect(self._on_progress)
        self._thread.finished.connect(self._on_finished)
        self._thread.start()

    def _on_progress(self, percent: int, message: str):
        self._progress_bar.setValue(percent)
        self._status_label.setText(message)

    def _on_finished(self, success: bool):
        self._success = success
        if success:
            self._status_label.setText("安装完成，即将继续启动...")
            self._progress_bar.setValue(100)
            self.accept()
        else:
            self._status_label.setText("下载失败，请检查网络后重试")
            self._download_btn.setEnabled(True)
            self._skip_btn.setEnabled(True)

    def was_successful(self) -> bool:
        return self._success
