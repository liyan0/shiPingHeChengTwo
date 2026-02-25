import asyncio
import os
import time
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QSpinBox,
    QPushButton,
    QProgressBar,
    QGroupBox,
    QFormLayout,
    QPlainTextEdit,
    QMessageBox,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QFont

from ..models.config import Config
from ..models.history import HistoryManager, HistoryRecord
from ..core.api_client import JimengAPIClient
from ..core.task_manager import TaskManager, TaskState, TaskProgress
from ..core.downloader import ImageDownloader


class AsyncWorker(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(object)
    finished_signal = pyqtSignal(object)

    def __init__(self, task_manager: TaskManager, prompt: str, request_count: int):
        super().__init__()
        self.task_manager = task_manager
        self.prompt = prompt
        self.request_count = request_count
        self._loop = None

        # 设置回调，通过信号发送到主线程
        self.task_manager.set_log_callback(lambda msg: self.log_signal.emit(msg))
        self.task_manager.set_progress_callback(lambda p: self.progress_signal.emit(p))

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            result = self._loop.run_until_complete(
                self.task_manager.run(self.prompt, self.request_count)
            )
            self.finished_signal.emit(result)
        except Exception as e:
            self.log_signal.emit(f"任务异常: {str(e)}")
            self.finished_signal.emit(None)
        finally:
            self._loop.close()


class GeneratePage(QWidget):
    def __init__(self, config: Config, history_manager: HistoryManager, project_dir: str):
        super().__init__()
        self.config = config
        self.history_manager = history_manager
        self.project_dir = project_dir
        self.save_dir = os.path.join(project_dir, "input", "视频图片素材文件夹")

        self.task_manager: TaskManager = None
        self.worker: AsyncWorker = None
        self.start_time: float = 0

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        prompt_group = self._create_prompt_group()
        layout.addWidget(prompt_group)

        params_layout = self._create_params_layout()
        layout.addLayout(params_layout)

        buttons_layout = self._create_buttons_layout()
        layout.addLayout(buttons_layout)

        progress_group = self._create_progress_group()
        layout.addWidget(progress_group)

        log_group = self._create_log_group()
        layout.addWidget(log_group, 1)

    def _create_prompt_group(self) -> QGroupBox:
        group = QGroupBox("提示词")
        group.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        layout = QVBoxLayout(group)

        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("输入图片描述提示词...")
        self.prompt_input.setMinimumHeight(100)
        self.prompt_input.setMaximumHeight(150)
        self.prompt_input.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(self.prompt_input)

        return group

    def _create_params_layout(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(12)

        request_label = QLabel("请求次数:")
        request_label.setFont(QFont("Microsoft YaHei", 10))
        self.request_spin = QSpinBox()
        self.request_spin.setRange(1, 1000)
        self.request_spin.setValue(10)
        self.request_spin.setMinimumWidth(80)
        self.request_spin.setMinimumHeight(18)

        concurrent_label = QLabel("并行数量:")
        concurrent_label.setFont(QFont("Microsoft YaHei", 10))
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 200)
        self.concurrent_spin.setValue(100)
        self.concurrent_spin.setMinimumWidth(80)
        self.concurrent_spin.setMinimumHeight(18)

        layout.addWidget(request_label)
        layout.addWidget(self.request_spin)
        layout.addSpacing(20)
        layout.addWidget(concurrent_label)
        layout.addWidget(self.concurrent_spin)
        layout.addStretch()

        return layout

    def _create_buttons_layout(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(4)

        btn_style = """
            QPushButton {{
                background-color: {bg};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
            QPushButton:disabled {{
                background-color: #bdc3c7;
            }}
        """

        self.start_btn = QPushButton("开始生图")
        self.start_btn.setStyleSheet(btn_style.format(bg="#3498db", hover="#2980b9"))
        self.start_btn.clicked.connect(self._on_start)

        self.pause_btn = QPushButton("暂停")
        self.pause_btn.setStyleSheet(btn_style.format(bg="#f39c12", hover="#d68910"))
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._on_pause)

        self.resume_btn = QPushButton("继续")
        self.resume_btn.setStyleSheet(btn_style.format(bg="#27ae60", hover="#219a52"))
        self.resume_btn.setEnabled(False)
        self.resume_btn.clicked.connect(self._on_resume)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setStyleSheet(btn_style.format(bg="#e74c3c", hover="#c0392b"))
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop)

        layout.addWidget(self.start_btn)
        layout.addWidget(self.pause_btn)
        layout.addWidget(self.resume_btn)
        layout.addWidget(self.stop_btn)
        layout.addStretch()

        return layout

    def _create_progress_group(self) -> QGroupBox:
        group = QGroupBox("进度")
        group.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        layout = QVBoxLayout(group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setMinimumHeight(14)
        layout.addWidget(self.progress_bar)

        self.stats_label = QLabel("请求: 0/0  图片: 0/0")
        self.stats_label.setFont(QFont("Microsoft YaHei", 10))
        self.stats_label.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(self.stats_label)

        return group

    def _create_log_group(self) -> QGroupBox:
        group = QGroupBox("日志")
        group.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        layout = QVBoxLayout(group)

        self.log_area = QPlainTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFont(QFont("Consolas", 9))
        self.log_area.setStyleSheet("""
            QPlainTextEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                border: none;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.log_area)

        return group

    def refresh_config(self):
        """Refresh config values from settings"""
        self.concurrent_spin.setValue(self.config.settings.max_concurrent)

    def _log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_area.appendPlainText(f"[{timestamp}] {message}")
        self.log_area.verticalScrollBar().setValue(
            self.log_area.verticalScrollBar().maximum()
        )

    def _update_progress(self, progress: TaskProgress):
        if progress.total_requests > 0:
            percent = int(progress.completed_requests / progress.total_requests * 100)
            self.progress_bar.setValue(percent)

        self.stats_label.setText(
            f"请求: {progress.completed_requests}/{progress.total_requests} "
            f"(成功: {progress.success_requests}, 失败: {progress.failed_requests})  "
            f"图片: {progress.downloaded_images}/{progress.total_images}"
        )

    def _set_buttons_state(self, state: str):
        if state == "idle":
            self.start_btn.setEnabled(True)
            self.pause_btn.setEnabled(False)
            self.resume_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self.prompt_input.setEnabled(True)
            self.request_spin.setEnabled(True)
            self.concurrent_spin.setEnabled(True)
        elif state == "running":
            self.start_btn.setEnabled(False)
            self.pause_btn.setEnabled(True)
            self.resume_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.prompt_input.setEnabled(False)
            self.request_spin.setEnabled(False)
            self.concurrent_spin.setEnabled(False)
        elif state == "paused":
            self.start_btn.setEnabled(False)
            self.pause_btn.setEnabled(False)
            self.resume_btn.setEnabled(True)
            self.stop_btn.setEnabled(True)

    def _on_start(self):
        prompt = self.prompt_input.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "提示", "请输入提示词")
            return

        if not self.config.api.api_key:
            QMessageBox.warning(self, "提示", "请先在设置页面配置 API Key")
            return

        request_count = self.request_spin.value()
        max_concurrent = self.concurrent_spin.value()

        self.log_area.clear()
        self.progress_bar.setValue(0)
        self.stats_label.setText("请求: 0/0  图片: 0/0")

        api_client = JimengAPIClient(
            base_url=self.config.api.base_url,
            api_key=self.config.api.api_key,
            model=self.config.api.model,
            ratio=self.config.api.ratio,
            resolution=self.config.api.resolution,
        )

        downloader = ImageDownloader(self.save_dir)

        self.task_manager = TaskManager(
            api_client=api_client,
            downloader=downloader,
            max_concurrent=max_concurrent,
            max_retries=self.config.settings.max_retries,
        )

        self.start_time = time.time()

        self.worker = AsyncWorker(self.task_manager, prompt, request_count)
        self.worker.log_signal.connect(self._log)
        self.worker.progress_signal.connect(self._update_progress)
        self.worker.finished_signal.connect(self._on_task_finished)
        self.worker.start()

        self._set_buttons_state("running")

    def _on_pause(self):
        if self.task_manager:
            self.task_manager.pause()
            self._set_buttons_state("paused")

    def _on_resume(self):
        if self.task_manager:
            self.task_manager.resume()
            self._set_buttons_state("running")

    def _on_stop(self):
        if self.task_manager:
            self.task_manager.stop()

    def _on_task_finished(self, progress: TaskProgress):
        self._set_buttons_state("idle")

        if progress:
            duration = time.time() - self.start_time
            prompt = self.prompt_input.toPlainText().strip()

            record = HistoryRecord(
                prompt=prompt,
                request_count=progress.total_requests,
                success_count=progress.success_requests,
                failed_count=progress.failed_requests,
                image_count=progress.downloaded_images,
                duration_seconds=duration,
            )
            self.history_manager.add_record(record)

        self.task_manager = None
        self.worker = None
