from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from ..utils.whisper_model_manager import WhisperModelManager


class _ModelDownloadThread(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, model_name: str):
        super().__init__()
        self.model_name = model_name

    def run(self):
        try:
            ok = WhisperModelManager.download_model(
                self.model_name,
                progress_callback=lambda p, m: self.progress.emit(p, m),
            )
            self.finished.emit(ok, "" if ok else "下载失败")
        except Exception as e:
            self.finished.emit(False, str(e))


class WhisperDownloadTab(QWidget):
    def __init__(self):
        super().__init__()
        self._download_thread: _ModelDownloadThread = None
        self._setup_ui()
        self._refresh_status()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Whisper 本地模型管理")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        title.setStyleSheet("color: #333333;")
        layout.addWidget(title)

        hint = QLabel(
            "模型文件将下载到 models/ 目录。优先使用 HuggingFace，国内网络自动切换镜像站。"
        )
        hint.setFont(QFont("Microsoft YaHei", 9))
        hint.setStyleSheet("color: #666666;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Table
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["模型", "大小", "状态", "操作"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.NoSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.setStyleSheet("""
            QTableWidget { border: 1px solid #d0d0d0; gridline-color: #e8e8e8; }
            QHeaderView::section {
                background-color: #f5f5f5;
                border: 1px solid #d0d0d0;
                padding: 4px 8px;
                font-size: 12px;
            }
        """)
        layout.addWidget(self._table)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #d0d0d0;
                text-align: center;
                height: 18px;
                font-size: 11px;
            }
            QProgressBar::chunk { background-color: #0066cc; }
        """)
        layout.addWidget(self._progress_bar)

        # Status label
        self._status_label = QLabel("就绪")
        self._status_label.setFont(QFont("Microsoft YaHei", 9))
        self._status_label.setStyleSheet("color: #555555;")
        layout.addWidget(self._status_label)

        layout.addStretch()

    def _refresh_status(self):
        models = list(WhisperModelManager.MODEL_INFO.items())
        self._table.setRowCount(len(models))

        for row, (name, info) in enumerate(models):
            downloaded = WhisperModelManager.is_model_downloaded(name)

            name_item = QTableWidgetItem(name)
            name_item.setFont(QFont("Microsoft YaHei", 9))
            self._table.setItem(row, 0, name_item)

            size_item = QTableWidgetItem(info["size_hint"])
            size_item.setFont(QFont("Microsoft YaHei", 9))
            size_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 1, size_item)

            status_item = QTableWidgetItem("已下载" if downloaded else "未下载")
            status_item.setFont(QFont("Microsoft YaHei", 9))
            status_item.setTextAlignment(Qt.AlignCenter)
            if downloaded:
                status_item.setForeground(QColor("#2e7d32"))
            else:
                status_item.setForeground(QColor("#888888"))
            self._table.setItem(row, 2, status_item)

            btn = QPushButton("删除" if downloaded else "下载")
            btn.setFont(QFont("Microsoft YaHei", 9))
            if downloaded:
                btn.setStyleSheet(
                    "QPushButton { color:#c62828; border:1px solid #c62828; padding:3px 10px; }"
                    "QPushButton:hover { background-color:#ffebee; }"
                    "QPushButton:disabled { color:#aaaaaa; border-color:#cccccc; }"
                )
                btn.clicked.connect(lambda _, n=name: self._on_delete(n))
            else:
                btn.setStyleSheet(
                    "QPushButton { color:#ffffff; background-color:#0066cc; border:1px solid #0055aa; padding:3px 10px; }"
                    "QPushButton:hover { background-color:#0055aa; }"
                    "QPushButton:disabled { background-color:#aaaaaa; border-color:#cccccc; }"
                )
                btn.clicked.connect(lambda _, n=name: self._on_download(n))

            self._table.setCellWidget(row, 3, btn)

        self._table.resizeRowsToContents()

    def _set_buttons_enabled(self, enabled: bool):
        for row in range(self._table.rowCount()):
            w = self._table.cellWidget(row, 3)
            if w:
                w.setEnabled(enabled)

    def _on_download(self, model_name: str):
        if self._download_thread and self._download_thread.isRunning():
            return

        self._set_buttons_enabled(False)
        self._progress_bar.setValue(0)
        self._status_label.setText(f"正在下载 {model_name}...")

        self._download_thread = _ModelDownloadThread(model_name)
        self._download_thread.progress.connect(self._on_progress)
        self._download_thread.finished.connect(
            lambda ok, msg: self._on_finished(ok, msg, model_name)
        )
        self._download_thread.start()

    def _on_delete(self, model_name: str):
        WhisperModelManager.delete_model(model_name)
        self._status_label.setText(f"已删除 {model_name}")
        self._refresh_status()

    def _on_progress(self, percent: int, message: str):
        self._progress_bar.setValue(percent)
        self._status_label.setText(message)

    def _on_finished(self, ok: bool, msg: str, model_name: str):
        self._set_buttons_enabled(True)
        if ok:
            self._progress_bar.setValue(100)
            self._status_label.setText(f"{model_name} 下载完成")
        else:
            self._progress_bar.setValue(0)
            self._status_label.setText(f"下载失败: {msg}")
        self._refresh_status()
