import asyncio
import os
import random
import subprocess
import sys
import time
import logging
from datetime import datetime

# 设置文件日志
_log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "error_log.txt")
_logger = logging.getLogger("home_page")
if not _logger.handlers:
    _handler = logging.FileHandler(_log_file, encoding='utf-8')
    _handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.DEBUG)

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QTextEdit,
    QSpinBox,
    QPushButton,
    QProgressBar,
    QFrame,
    QMessageBox,
    QComboBox,
    QInputDialog,
    QTabWidget,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QCheckBox,
    QSlider,
    QDoubleSpinBox,
    QSplitter,
    QRadioButton,
    QLineEdit,
    QButtonGroup,
    QGroupBox,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor

from ..models.config import Config, SubtitleStyleConfig
from ..models.history import HistoryManager, HistoryRecord
from .theme import Styles
from ..core.api_client import JimengAPIClient
from ..core.task_manager import TaskManager, TaskProgress
from ..core.downloader import ImageDownloader
from ..core.video_api_client import VideoAPIClient
from ..core.video_task_manager import VideoTaskManager, VideoTaskProgress
from ..core.video_downloader import VideoDownloader
from ..core.copywriting_api_client import CopywritingAPIClient
from ..core.copywriting_task_manager import CopywritingTaskManager, CopywritingTaskProgress
from ..core.image_recognition_api_client import ImageRecognitionAPIClient
from ..core.image_recognition_task_manager import ImageRecognitionTaskManager, ImageRecognitionTaskProgress
from ..core.merge_copywriting_api_client import MergeCopywritingAPIClient
from ..core.merge_copywriting_task_manager import MergeCopywritingTaskManager, MergeCopywritingTaskProgress
from ..core.tts_api_client import TTSAPIClient
from ..core.tts_task_manager import TTSTaskManager, TTSTaskProgress
from ..core.subtitle_api_client import SubtitleAPIClient
from ..core.product_time_api_client import ProductTimeAPIClient
from ..core.video_compose_task_manager import VideoComposeTaskManager, VideoComposeTaskProgress
from ..core.extract_copywriting_task_manager import ExtractCopywritingTaskManager, ExtractCopywritingTaskProgress
from ..core.rewrite_copywriting_task_manager import RewriteCopywritingTaskManager, RewriteCopywritingTaskProgress
from ..core.normal_video_task_manager import NormalVideoTaskManager, NormalVideoTaskProgress


class AsyncWorker(QThread):
    log_signal = pyqtSignal(str, str)  # message, level
    progress_signal = pyqtSignal(object)
    finished_signal = pyqtSignal(object)

    def __init__(self, task_manager: TaskManager, prompt: str, request_count: int):
        super().__init__()
        self.task_manager = task_manager
        self.prompt = prompt
        self.request_count = request_count
        self._loop = None

        self.task_manager.set_log_callback(lambda msg: self.log_signal.emit(msg, "info"))
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
            self.log_signal.emit(f"任务异常: {str(e)}", "error")
            self.finished_signal.emit(None)
        finally:
            self._loop.close()


class VideoAsyncWorker(QThread):
    log_signal = pyqtSignal(str, str)  # message, level
    progress_signal = pyqtSignal(object)
    finished_signal = pyqtSignal(object)

    def __init__(self, task_manager: VideoTaskManager, image_paths: list, prompt: str):
        super().__init__()
        self.task_manager = task_manager
        self.image_paths = image_paths
        self.prompt = prompt
        self._loop = None

        self.task_manager.set_log_callback(lambda msg: self.log_signal.emit(msg, "info"))
        self.task_manager.set_progress_callback(lambda p: self.progress_signal.emit(p))

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            result = self._loop.run_until_complete(
                self.task_manager.run(self.image_paths, self.prompt)
            )
            self.finished_signal.emit(result)
        except Exception as e:
            self.log_signal.emit(f"任务异常: {str(e)}", "error")
            self.finished_signal.emit(None)
        finally:
            self._loop.close()


class CopywritingAsyncWorker(QThread):
    log_signal = pyqtSignal(str, str)  # message, level
    progress_signal = pyqtSignal(object)
    finished_signal = pyqtSignal(object)

    def __init__(self, task_manager: CopywritingTaskManager, prompt: str, request_count: int):
        super().__init__()
        self.task_manager = task_manager
        self.prompt = prompt
        self.request_count = request_count
        self._loop = None

        self.task_manager.set_log_callback(lambda msg: self.log_signal.emit(msg, "info"))
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
            self.log_signal.emit(f"任务异常: {str(e)}", "error")
            self.finished_signal.emit(None)
        finally:
            self._loop.close()


class ImageRecognitionAsyncWorker(QThread):
    log_signal = pyqtSignal(str, str)  # message, level
    progress_signal = pyqtSignal(object)
    finished_signal = pyqtSignal(object)

    def __init__(
        self,
        task_manager: ImageRecognitionTaskManager,
        folder_names: list,
        prompt: str,
        file_count: int,
    ):
        super().__init__()
        self.task_manager = task_manager
        self.folder_names = folder_names
        self.prompt = prompt
        self.file_count = file_count
        self._loop = None

        self.task_manager.set_log_callback(lambda msg: self.log_signal.emit(msg, "info"))
        self.task_manager.set_progress_callback(lambda p: self.progress_signal.emit(p))

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            result = self._loop.run_until_complete(
                self.task_manager.run(self.folder_names, self.prompt, self.file_count)
            )
            self.finished_signal.emit(result)
        except Exception as e:
            self.log_signal.emit(f"任务异常: {str(e)}", "error")
            self.finished_signal.emit(None)
        finally:
            self._loop.close()


class MergeCopywritingAsyncWorker(QThread):
    log_signal = pyqtSignal(str, str)  # message, level
    progress_signal = pyqtSignal(object)
    finished_signal = pyqtSignal(object)

    def __init__(
        self,
        task_manager: MergeCopywritingTaskManager,
        folder_names: list,
        prompt: str,
        max_pairs: int,
    ):
        super().__init__()
        self.task_manager = task_manager
        self.folder_names = folder_names
        self.prompt = prompt
        self.max_pairs = max_pairs
        self._loop = None

        self.task_manager.set_log_callback(lambda msg: self.log_signal.emit(msg, "info"))
        self.task_manager.set_progress_callback(lambda p: self.progress_signal.emit(p))

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            result = self._loop.run_until_complete(
                self.task_manager.run(self.folder_names, self.prompt, self.max_pairs)
            )
            self.finished_signal.emit(result)
        except Exception as e:
            self.log_signal.emit(f"任务异常: {str(e)}", "error")
            self.finished_signal.emit(None)
        finally:
            self._loop.close()


class TTSAsyncWorker(QThread):
    log_signal = pyqtSignal(str, str)  # message, level
    progress_signal = pyqtSignal(object)
    finished_signal = pyqtSignal(object)

    def __init__(
        self,
        task_manager: TTSTaskManager,
        folder_names: list,
        max_count: int,
    ):
        super().__init__()
        self.task_manager = task_manager
        self.folder_names = folder_names
        self.max_count = max_count
        self._loop = None

        self.task_manager.set_log_callback(lambda msg, level="info": self.log_signal.emit(msg, level))
        self.task_manager.set_progress_callback(lambda p: self.progress_signal.emit(p))

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            result = self._loop.run_until_complete(
                self.task_manager.run(self.folder_names, self.max_count)
            )
            self.finished_signal.emit(result)
        except Exception as e:
            self.log_signal.emit(f"Task exception: {str(e)}", "error")
            self.finished_signal.emit(None)
        finally:
            self._loop.close()


class TTSLiuliangAsyncWorker(QThread):
    """Worker for liuliang mode TTS generation"""
    log_signal = pyqtSignal(str, str)  # message, level
    progress_signal = pyqtSignal(object)
    finished_signal = pyqtSignal(object)

    def __init__(
        self,
        task_manager: TTSTaskManager,
        file_paths: list,
        recycle_dir: str,
    ):
        super().__init__()
        self.task_manager = task_manager
        self.file_paths = file_paths
        self.recycle_dir = recycle_dir
        self._loop = None

        self.task_manager.set_log_callback(lambda msg, level="info": self.log_signal.emit(msg, level))
        self.task_manager.set_progress_callback(lambda p: self.progress_signal.emit(p))

    def run(self):
        _logger.info("TTSLiuliangAsyncWorker.run 开始")
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            _logger.info("开始执行 run_with_files")
            result = self._loop.run_until_complete(
                self.task_manager.run_with_files(self.file_paths, self.recycle_dir)
            )
            _logger.info("run_with_files 完成")
            self.finished_signal.emit(result)
        except Exception as e:
            _logger.error(f"TTSLiuliangAsyncWorker 异常: {e}", exc_info=True)
            self.log_signal.emit(f"Task exception: {str(e)}", "error")
            self.finished_signal.emit(None)
        finally:
            self._loop.close()
            _logger.info("TTSLiuliangAsyncWorker.run 结束")


class VideoComposeAsyncWorker(QThread):
    log_signal = pyqtSignal(str, str)  # message, level
    progress_signal = pyqtSignal(object)
    finished_signal = pyqtSignal(object)

    def __init__(
        self,
        task_manager: VideoComposeTaskManager,
        folder_names: list,
        max_count: int,
    ):
        super().__init__()
        self.task_manager = task_manager
        self.folder_names = folder_names
        self.max_count = max_count
        self._loop = None

        self.task_manager.set_log_callback(lambda msg: self.log_signal.emit(msg, "info"))
        self.task_manager.set_progress_callback(lambda p: self.progress_signal.emit(p))

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            result = self._loop.run_until_complete(
                self.task_manager.run(self.folder_names, self.max_count)
            )
            self.finished_signal.emit(result)
        except Exception as e:
            self.log_signal.emit(f"Task exception: {str(e)}", "error")
            self.finished_signal.emit(None)
        finally:
            self._loop.close()


class ExtractCopywritingAsyncWorker(QThread):
    log_signal = pyqtSignal(str, str)  # message, level
    progress_signal = pyqtSignal(object)
    finished_signal = pyqtSignal(object)

    def __init__(self, task_manager: ExtractCopywritingTaskManager, url_text: str):
        super().__init__()
        self.task_manager = task_manager
        self.url_text = url_text
        self._loop = None

        self.task_manager.set_log_callback(lambda msg: self.log_signal.emit(msg, "info"))
        self.task_manager.set_progress_callback(lambda p: self.progress_signal.emit(p))

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            result = self._loop.run_until_complete(
                self.task_manager.run(self.url_text)
            )
            self.finished_signal.emit(result)
        except Exception as e:
            self.log_signal.emit(f"Task exception: {str(e)}", "error")
            self.finished_signal.emit(None)
        finally:
            self._loop.close()


class RewriteCopywritingAsyncWorker(QThread):
    log_signal = pyqtSignal(str, str)  # message, level
    progress_signal = pyqtSignal(object)
    finished_signal = pyqtSignal(object)

    def __init__(self, task_manager: RewriteCopywritingTaskManager, prompt: str):
        super().__init__()
        self.task_manager = task_manager
        self.prompt = prompt
        self._loop = None

        self.task_manager.set_log_callback(lambda msg: self.log_signal.emit(msg, "info"))
        self.task_manager.set_progress_callback(lambda p: self.progress_signal.emit(p))

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            result = self._loop.run_until_complete(
                self.task_manager.run(self.prompt)
            )
            self.finished_signal.emit(result)
        except Exception as e:
            self.log_signal.emit(f"Task exception: {str(e)}", "error")
            self.finished_signal.emit(None)
        finally:
            self._loop.close()


class YindaoRewriteCopywritingAsyncWorker(QThread):
    log_signal = pyqtSignal(str, str)  # message, level
    progress_signal = pyqtSignal(object)
    finished_signal = pyqtSignal(object)

    def __init__(self, task_manager: RewriteCopywritingTaskManager, prompt: str):
        super().__init__()
        self.task_manager = task_manager
        self.prompt = prompt
        self._loop = None

        self.task_manager.set_log_callback(lambda msg: self.log_signal.emit(msg, "info"))
        self.task_manager.set_progress_callback(lambda p: self.progress_signal.emit(p))

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            result = self._loop.run_until_complete(
                self.task_manager.run(self.prompt)
            )
            self.finished_signal.emit(result)
        except Exception as e:
            self.log_signal.emit(f"Task exception: {str(e)}", "error")
            self.finished_signal.emit(None)
        finally:
            self._loop.close()


class NormalVideoAsyncWorker(QThread):
    log_signal = pyqtSignal(str, str)
    progress_signal = pyqtSignal(object)
    finished_signal = pyqtSignal(object)

    def __init__(self, task_manager: NormalVideoTaskManager, max_count: int):
        super().__init__()
        self.task_manager = task_manager
        self.max_count = max_count
        self._loop = None

        self.task_manager.set_log_callback(lambda msg: self.log_signal.emit(msg, "info"))
        self.task_manager.set_progress_callback(lambda p: self.progress_signal.emit(p))

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            result = self._loop.run_until_complete(
                self.task_manager.run(self.max_count)
            )
            self.finished_signal.emit(result)
        except Exception as e:
            self.log_signal.emit(f"Task exception: {str(e)}", "error")
            self.finished_signal.emit(None)
        finally:
            self._loop.close()


class HomePage(QWidget):
    def __init__(self, config: Config, history_manager: HistoryManager, project_dir: str):
        super().__init__()
        self.config = config
        self.history_manager = history_manager
        self.project_dir = project_dir
        self.save_dir = os.path.join(project_dir, "input", "视频图片素材文件夹")
        self.video_save_dir = os.path.join(project_dir, "input", "视频素材")
        self.copywriting_save_dir = os.path.join(project_dir, "input", "视频文案")
        self.image_recognition_input_dir = os.path.join(project_dir, "input", "商品")
        self.image_recognition_output_dir = os.path.join(project_dir, "input", "商品文案")
        self.merge_copywriting_output_dir = os.path.join(project_dir, "input", "合并文案")
        self.tts_output_dir = os.path.join(project_dir, "input", "视频配音")
        self.liuliang_output_dir = os.path.join(project_dir, "input", "视频配音", "流量语音")
        self.yindao_output_dir = os.path.join(project_dir, "input", "视频配音", "引导语音")
        self.recycle_dir = os.path.join(project_dir, "input", "回收站")
        self.bgm_dir = os.path.join(project_dir, "input", "背景音乐")
        self.product_image_dir = os.path.join(project_dir, "input", "商品图片")
        self.video_compose_output_dir = os.path.join(project_dir, "output")
        self.extract_copywriting_output_dir = os.path.join(project_dir, "input", "提取的视频文案")
        self.liuliang_copywriting_dir = os.path.join(project_dir, "input", "视频文案", "流量文案")
        self.yindao_copywriting_dir = os.path.join(project_dir, "input", "视频文案", "引导文案")
        self.temp_dir = os.path.join(project_dir, "temp")

        # Image generation state
        self.task_manager: TaskManager = None
        self.worker: AsyncWorker = None
        self.start_time: float = 0

        # Video generation state
        self.video_task_manager: VideoTaskManager = None
        self.video_worker: VideoAsyncWorker = None
        self.video_start_time: float = 0

        # Copywriting generation state
        self.copywriting_task_manager: CopywritingTaskManager = None
        self.copywriting_worker: CopywritingAsyncWorker = None
        self.copywriting_start_time: float = 0

        # Image recognition state
        self.image_recognition_task_manager: ImageRecognitionTaskManager = None
        self.image_recognition_worker: ImageRecognitionAsyncWorker = None
        self.image_recognition_start_time: float = 0

        # Merge copywriting state
        self.merge_copywriting_task_manager: MergeCopywritingTaskManager = None
        self.merge_copywriting_worker: MergeCopywritingAsyncWorker = None
        self.merge_copywriting_start_time: float = 0

        # TTS generation state
        self.tts_task_manager: TTSTaskManager = None
        self.tts_worker: TTSAsyncWorker = None
        self.tts_start_time: float = 0

        # Video compose state
        self.video_compose_task_manager: VideoComposeTaskManager = None
        self.video_compose_worker: VideoComposeAsyncWorker = None
        self.video_compose_start_time: float = 0

        # Extract copywriting state
        self.extract_copywriting_task_manager: ExtractCopywritingTaskManager = None
        self.extract_copywriting_worker: ExtractCopywritingAsyncWorker = None
        self.extract_copywriting_start_time: float = 0

        # Rewrite copywriting state
        self.rewrite_copywriting_task_manager: RewriteCopywritingTaskManager = None
        self.rewrite_copywriting_worker: RewriteCopywritingAsyncWorker = None
        self.rewrite_copywriting_start_time: float = 0

        # Yindao rewrite copywriting state
        self.yindao_rewrite_copywriting_task_manager: RewriteCopywritingTaskManager = None
        self.yindao_rewrite_copywriting_worker = None
        self.yindao_rewrite_copywriting_start_time: float = 0

        # Normal video state
        self.normal_video_source_dir = r"D:\BaiduNetdiskDownload\真实视频素材"
        self.normal_video_output_dir = os.path.join(project_dir, "output", "普通视频")
        self.liuliang_video_output_dir = os.path.join(project_dir, "output", "流量视频")
        self.yindao_video_output_dir = os.path.join(project_dir, "output", "引导视频")
        self.chuchuang_output_dir = os.path.join(project_dir, "input", "视频配音", "橱窗语音")
        self.chuchuang_video_output_dir = os.path.join(project_dir, "output", "橱窗视频")
        self.chuchuang_material_dir = os.path.join(project_dir, "input", "橱窗素材")
        self.overlay_material_dir = os.path.join(project_dir, "input", "叠加素材")
        self.normal_video_task_manager: NormalVideoTaskManager = None
        self.normal_video_worker: NormalVideoAsyncWorker = None
        self.normal_video_start_time: float = 0
        self._normal_video_pending_configs: list = []
        self._normal_video_max_count: int = 0

        self._setup_ui()
        self._load_templates()
        self.load_last_prompt()
        self._load_last_copywriting_prompt()
        self._load_last_image_recognition_prompt()
        self._load_last_merge_copywriting_prompt()
        self._load_last_rewrite_copywriting_prompt()
        self._load_rewrite_copywriting_templates()
        self._load_yindao_rewrite_copywriting_templates()
        self._update_video_image_count()
        self._load_ui_state()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setFont(QFont("Microsoft YaHei", 10))
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #d0d0d0;
                background: #ffffff;
            }
            QTabBar::tab {
                background: #f0f0f0;
                border: 1px solid #d0d0d0;
                padding: 4px 10px;
                margin-right: 1px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                border-bottom-color: #ffffff;
            }
            QTabBar::tab:hover {
                background: #e8f4fc;
            }
        """)

        self.tab_widget.addTab(self._create_extract_copywriting_tab(), "扒文案")
        self.tab_widget.addTab(self._create_new_extract_tab(), "提取文案(新)")
        self.tab_widget.addTab(self._create_copywriting_tab(), "视频文案")
        self.tab_widget.addTab(self._create_image_recognition_tab(), "图片识别")
        self.tab_widget.addTab(self._create_merge_copywriting_tab(), "合并文案")
        self.tab_widget.addTab(self._create_tts_tab(), "语音生成")
        self.tab_widget.addTab(self._create_image_tab(), "图片生成")
        self.tab_widget.addTab(self._create_video_tab(), "视频生成")
        self.tab_widget.addTab(self._create_video_compose_tab(), "带货视频合成")
        self.tab_widget.addTab(self._create_normal_video_tab(), "普通视频生成")

        layout.addWidget(self.tab_widget)

    def _create_extract_copywriting_tab(self) -> QWidget:
        """Create extract copywriting tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(3)

        # Top area: left input + right settings
        top_frame = QFrame()
        top_layout = QHBoxLayout(top_frame)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)

        # Left: URL input
        input_panel = self._create_extract_copywriting_input_panel()
        top_layout.addWidget(input_panel, 2)

        # Right: Settings
        settings_panel = self._create_extract_copywriting_settings_panel()
        top_layout.addWidget(settings_panel, 1)

        layout.addWidget(top_frame, 1)

        # Progress bar
        progress_frame = self._create_extract_copywriting_progress_area()
        layout.addWidget(progress_frame)

        # Status bar
        status_bar = self._create_extract_copywriting_status_bar()
        layout.addWidget(status_bar)

        # Log area
        log_frame = self._create_extract_copywriting_log_area()
        layout.addWidget(log_frame)

        return widget

    def _create_extract_copywriting_input_panel(self) -> QFrame:
        """Create URL input panel"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame#extract_input_frame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)
        frame.setObjectName("extract_input_frame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        label = QLabel("视频链接 (每行一个)")
        label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(label)

        self.extract_copywriting_url_input = QTextEdit()
        self.extract_copywriting_url_input.setPlaceholderText(
            "输入视频链接，每行一个...\n"
            "支持平台: 百家号\n\n"
            "示例:\n"
            "https://baijiahao.baidu.com/s?id=xxx"
        )
        self.extract_copywriting_url_input.setFont(QFont("Microsoft YaHei", 10))
        self.extract_copywriting_url_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #d0d0d0;
                padding: 4px;
            }
        """)
        layout.addWidget(self.extract_copywriting_url_input, 1)

        return frame

    def _create_extract_copywriting_settings_panel(self) -> QFrame:
        """Create settings panel"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame#extract_settings_frame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)
        frame.setObjectName("extract_settings_frame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        label = QLabel("参数设置")
        label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(label)

        label_style = "color: #333333; background: transparent; border: none;"

        # Concurrent
        concurrent_layout = QHBoxLayout()
        concurrent_label = QLabel("并行数量:")
        concurrent_label.setFont(QFont("Microsoft YaHei", 9))
        concurrent_label.setStyleSheet(label_style)
        self.extract_copywriting_concurrent_spin = QSpinBox()
        self.extract_copywriting_concurrent_spin.setRange(1, 5)
        self.extract_copywriting_concurrent_spin.setValue(2)
        concurrent_layout.addWidget(concurrent_label)
        concurrent_layout.addWidget(self.extract_copywriting_concurrent_spin)
        concurrent_layout.addStretch()
        layout.addLayout(concurrent_layout)

        # Model
        model_layout = QHBoxLayout()
        model_label = QLabel("Whisper模型:")
        model_label.setFont(QFont("Microsoft YaHei", 9))
        model_label.setStyleSheet(label_style)
        self.extract_copywriting_model_combo = QComboBox()
        self.extract_copywriting_model_combo.addItems(["small", "medium", "large-v2", "large-v3"])
        self.extract_copywriting_model_combo.setCurrentText("small")
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.extract_copywriting_model_combo)
        model_layout.addStretch()
        layout.addLayout(model_layout)

        # Device
        device_layout = QHBoxLayout()
        device_label = QLabel("计算设备:")
        device_label.setFont(QFont("Microsoft YaHei", 9))
        device_label.setStyleSheet(label_style)
        self.extract_copywriting_device_combo = QComboBox()
        self.extract_copywriting_device_combo.addItems(["cpu", "cuda"])
        self.extract_copywriting_device_combo.setCurrentText("cpu")
        device_layout.addWidget(device_label)
        device_layout.addWidget(self.extract_copywriting_device_combo)
        device_layout.addStretch()
        layout.addLayout(device_layout)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()

        primary_btn_style = """
            QPushButton {
                color: #ffffff;
                background-color: #0066cc;
                border: 1px solid #0055aa;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0055aa;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                border-color: #bbbbbb;
            }
        """

        btn_style = """
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e8f4fc;
            }
            QPushButton:disabled {
                color: #999999;
                background-color: #f0f0f0;
            }
        """

        stop_btn_style = """
            QPushButton {
                color: #cc0000;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 4px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #ffeeee;
            }
            QPushButton:disabled {
                color: #999999;
                background-color: #f0f0f0;
            }
        """

        self.extract_copywriting_start_btn = QPushButton("开始提取")
        self.extract_copywriting_start_btn.setFont(QFont("Microsoft YaHei", 9))
        self.extract_copywriting_start_btn.setStyleSheet(primary_btn_style)
        self.extract_copywriting_start_btn.clicked.connect(self._on_extract_copywriting_start)

        self.extract_copywriting_pause_btn = QPushButton("暂停")
        self.extract_copywriting_pause_btn.setFont(QFont("Microsoft YaHei", 9))
        self.extract_copywriting_pause_btn.setStyleSheet(btn_style)
        self.extract_copywriting_pause_btn.setEnabled(False)
        self.extract_copywriting_pause_btn.clicked.connect(self._on_extract_copywriting_pause)

        self.extract_copywriting_stop_btn = QPushButton("停止")
        self.extract_copywriting_stop_btn.setFont(QFont("Microsoft YaHei", 9))
        self.extract_copywriting_stop_btn.setStyleSheet(stop_btn_style)
        self.extract_copywriting_stop_btn.setEnabled(False)
        self.extract_copywriting_stop_btn.clicked.connect(self._on_extract_copywriting_stop)

        btn_layout.addWidget(self.extract_copywriting_start_btn)
        btn_layout.addWidget(self.extract_copywriting_pause_btn)
        btn_layout.addWidget(self.extract_copywriting_stop_btn)
        layout.addLayout(btn_layout)

        return frame

    def _create_extract_copywriting_progress_area(self) -> QFrame:
        """Create progress bar area"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(6, 4, 6, 4)

        label = QLabel("进度:")
        label.setFont(QFont("Microsoft YaHei", 9))
        label.setStyleSheet("border: none;")
        layout.addWidget(label)

        self.extract_copywriting_progress_bar = QProgressBar()
        self.extract_copywriting_progress_bar.setMinimum(0)
        self.extract_copywriting_progress_bar.setMaximum(100)
        self.extract_copywriting_progress_bar.setValue(0)
        self.extract_copywriting_progress_bar.setStyleSheet("border: none;")
        layout.addWidget(self.extract_copywriting_progress_bar, 1)

        self.extract_copywriting_progress_label = QLabel("0/0 (0%)")
        self.extract_copywriting_progress_label.setFont(QFont("Microsoft YaHei", 9))
        self.extract_copywriting_progress_label.setStyleSheet("border: none;")
        layout.addWidget(self.extract_copywriting_progress_label)

        return frame

    def _create_extract_copywriting_status_bar(self) -> QFrame:
        """Create status bar"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
            }
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(6, 2, 6, 2)

        self.extract_copywriting_status_label = QLabel("就绪")
        self.extract_copywriting_status_label.setFont(QFont("Microsoft YaHei", 9))
        self.extract_copywriting_status_label.setStyleSheet("color: #666666; border: none;")
        layout.addWidget(self.extract_copywriting_status_label)

        layout.addStretch()

        return frame

    def _create_extract_copywriting_log_area(self) -> QFrame:
        """Create log output area"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame#extract_log_frame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)
        frame.setObjectName("extract_log_frame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(3)

        label = QLabel("日志输出")
        label.setFont(QFont("Microsoft YaHei", 9, QFont.Bold))
        label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(label)

        self.extract_copywriting_log_output = QTextEdit()
        self.extract_copywriting_log_output.setReadOnly(True)
        self.extract_copywriting_log_output.setMaximumHeight(120)
        self.extract_copywriting_log_output.setFont(QFont("Consolas", 9))
        self.extract_copywriting_log_output.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #333333;
            }
        """)
        layout.addWidget(self.extract_copywriting_log_output)

        return frame

    def _check_whisper_model(self, model_name: str) -> bool:
        from src.utils.whisper_model_manager import WhisperModelManager
        if WhisperModelManager.is_model_downloaded(model_name):
            return True
        QMessageBox.warning(
            self, "模型未下载",
            f"未找到 Whisper 模型「{model_name}」。\n\n"
            f"请前往 设置 > Whisper下载 下载对应模型后再使用此功能。",
        )
        return False

    def _on_extract_copywriting_start(self):
        """Start extract copywriting task"""
        url_text = self.extract_copywriting_url_input.toPlainText().strip()
        if not url_text:
            QMessageBox.warning(self, "提示", "请输入视频链接")
            return

        model = self.extract_copywriting_model_combo.currentText()
        if not self._check_whisper_model(model):
            return

        # Get settings
        concurrent = self.extract_copywriting_concurrent_spin.value()
        device = self.extract_copywriting_device_combo.currentText()

        # Create task manager
        self.extract_copywriting_task_manager = ExtractCopywritingTaskManager(
            output_dir=self.extract_copywriting_output_dir,
            temp_dir=self.temp_dir,
            whisper_model=model,
            whisper_device=device,
            max_concurrent=concurrent,
        )

        # Create worker
        self.extract_copywriting_worker = ExtractCopywritingAsyncWorker(
            self.extract_copywriting_task_manager,
            url_text,
        )
        self.extract_copywriting_worker.log_signal.connect(self._on_extract_copywriting_log)
        self.extract_copywriting_worker.progress_signal.connect(self._on_extract_copywriting_progress)
        self.extract_copywriting_worker.finished_signal.connect(self._on_extract_copywriting_finished)

        # Update UI
        self.extract_copywriting_start_btn.setEnabled(False)
        self.extract_copywriting_pause_btn.setEnabled(True)
        self.extract_copywriting_stop_btn.setEnabled(True)
        self.extract_copywriting_url_input.setEnabled(False)

        self.extract_copywriting_log_output.clear()
        self.extract_copywriting_progress_bar.setValue(0)
        self.extract_copywriting_status_label.setText("正在处理...")
        self.extract_copywriting_start_time = time.time()

        self.extract_copywriting_worker.start()

    def _on_extract_copywriting_pause(self):
        """Pause/Resume extract copywriting task"""
        if not self.extract_copywriting_task_manager:
            return

        if self.extract_copywriting_pause_btn.text() == "暂停":
            self.extract_copywriting_task_manager.pause()
            self.extract_copywriting_pause_btn.setText("继续")
            self.extract_copywriting_status_label.setText("已暂停")
        else:
            self.extract_copywriting_task_manager.resume()
            self.extract_copywriting_pause_btn.setText("暂停")
            self.extract_copywriting_status_label.setText("正在处理...")

    def _on_extract_copywriting_stop(self):
        """Stop extract copywriting task"""
        if self.extract_copywriting_task_manager:
            self.extract_copywriting_task_manager.stop()
            self.extract_copywriting_status_label.setText("正在停止...")

    def _on_extract_copywriting_log(self, message: str, level: str):
        """Handle log message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.extract_copywriting_log_output.append(f"[{timestamp}] {message}")
        self.extract_copywriting_log_output.moveCursor(QTextCursor.End)

    def _on_extract_copywriting_progress(self, progress: ExtractCopywritingTaskProgress):
        """Handle progress update"""
        total = progress.total_tasks
        completed = progress.completed_tasks + progress.failed_tasks

        if total > 0:
            percent = int(completed / total * 100)
            self.extract_copywriting_progress_bar.setValue(percent)
            self.extract_copywriting_progress_label.setText(
                f"{completed}/{total} ({percent}%)"
            )

        if progress.current_task:
            self.extract_copywriting_status_label.setText(progress.current_task)

    def _on_extract_copywriting_finished(self, result):
        """Handle task finished"""
        # Reset UI
        self.extract_copywriting_start_btn.setEnabled(True)
        self.extract_copywriting_pause_btn.setEnabled(False)
        self.extract_copywriting_pause_btn.setText("暂停")
        self.extract_copywriting_stop_btn.setEnabled(False)
        self.extract_copywriting_url_input.setEnabled(True)

        elapsed = time.time() - self.extract_copywriting_start_time
        elapsed_str = f"{int(elapsed // 60)}分{int(elapsed % 60)}秒"

        if result:
            self.extract_copywriting_status_label.setText(
                f"完成 - 成功: {result.completed_tasks}, 失败: {result.failed_tasks}, "
                f"保存: {result.saved_files}, 耗时: {elapsed_str}"
            )
        else:
            self.extract_copywriting_status_label.setText("任务异常终止")

        self.extract_copywriting_task_manager = None
        self.extract_copywriting_worker = None

    def _create_image_recognition_tab(self) -> QWidget:
        """Create image recognition tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(3)

        toolbar = self._create_image_recognition_toolbar()
        layout.addWidget(toolbar)

        content_frame = self._create_image_recognition_content_area()
        layout.addWidget(content_frame, 1)

        status_bar = self._create_image_recognition_status_bar()
        layout.addWidget(status_bar)

        log_frame = self._create_image_recognition_log_area()
        layout.addWidget(log_frame)

        return widget

    def _create_image_tab(self) -> QWidget:
        """Create image generation tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(3)

        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        content_frame = self._create_content_area()
        layout.addWidget(content_frame, 1)

        status_bar = self._create_status_bar()
        layout.addWidget(status_bar)

        log_frame = self._create_log_area()
        layout.addWidget(log_frame)

        return widget

    def _create_video_tab(self) -> QWidget:
        """Create video generation tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(3)

        toolbar = self._create_video_toolbar()
        layout.addWidget(toolbar)

        content_frame = self._create_video_content_area()
        layout.addWidget(content_frame, 1)

        status_bar = self._create_video_status_bar()
        layout.addWidget(status_bar)

        log_frame = self._create_video_log_area()
        layout.addWidget(log_frame)

        return widget

    def _create_copywriting_tab(self) -> QWidget:
        """Create copywriting tab with nested sub-tabs"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create third-level tab container
        sub_tab_widget = QTabWidget()
        sub_tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: transparent;
            }
            QTabBar::tab {
                padding: 4px 12px;
                font-size: 11px;
                color: #666666;
                background: #f5f5f5;
                border: 1px solid #d0d0d0;
                border-bottom: none;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                color: #0066cc;
                background: #ffffff;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background: #e8e8e8;
            }
        """)

        # Add third-level tabs
        sub_tab_widget.addTab(self._create_copywriting_generate_tab(), "文案生成")
        sub_tab_widget.addTab(self._create_copywriting_rewrite_tab(), "流量文案改写")
        sub_tab_widget.addTab(self._create_copywriting_yindao_rewrite_tab(), "引导文案改写")

        layout.addWidget(sub_tab_widget)
        return widget

    def _create_copywriting_generate_tab(self) -> QWidget:
        """Create copywriting generation sub-tab (original copywriting functionality)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(3)

        toolbar = self._create_copywriting_toolbar()
        layout.addWidget(toolbar)

        content_frame = self._create_copywriting_content_area()
        layout.addWidget(content_frame, 1)

        status_bar = self._create_copywriting_status_bar()
        layout.addWidget(status_bar)

        log_frame = self._create_copywriting_log_area()
        layout.addWidget(log_frame)

        return widget

    def _create_copywriting_rewrite_tab(self) -> QWidget:
        """Create copywriting rewrite sub-tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(3)

        toolbar = self._create_rewrite_copywriting_toolbar()
        layout.addWidget(toolbar)

        content_frame = self._create_rewrite_copywriting_content_area()
        layout.addWidget(content_frame, 1)

        status_bar = self._create_rewrite_copywriting_status_bar()
        layout.addWidget(status_bar)

        log_frame = self._create_rewrite_copywriting_log_area()
        layout.addWidget(log_frame)

        return widget

    def _create_rewrite_copywriting_toolbar(self) -> QFrame:
        toolbar = QFrame()
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)

        label_style = "color: #333333; background: transparent; border: none;"

        concurrent_label = QLabel("并发数:")
        concurrent_label.setFont(QFont("Microsoft YaHei", 9))
        concurrent_label.setStyleSheet(label_style)
        self.rewrite_copywriting_concurrent_spin = QSpinBox()
        self.rewrite_copywriting_concurrent_spin.setRange(1, 10)
        self.rewrite_copywriting_concurrent_spin.setValue(3)

        versions_label = QLabel("版本数:")
        versions_label.setFont(QFont("Microsoft YaHei", 9))
        versions_label.setStyleSheet(label_style)
        self.rewrite_copywriting_versions_spin = QSpinBox()
        self.rewrite_copywriting_versions_spin.setRange(1, 10)
        self.rewrite_copywriting_versions_spin.setValue(1)

        layout.addWidget(concurrent_label)
        layout.addWidget(self.rewrite_copywriting_concurrent_spin)
        layout.addWidget(versions_label)
        layout.addWidget(self.rewrite_copywriting_versions_spin)

        layout.addStretch()

        btn_style = """
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e8f4fc;
            }
            QPushButton:disabled {
                color: #999999;
                background-color: #f0f0f0;
            }
        """

        primary_btn_style = """
            QPushButton {
                color: #ffffff;
                background-color: #0066cc;
                border: 1px solid #0055aa;
                padding: 2px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0055aa;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                border-color: #bbbbbb;
            }
        """

        stop_btn_style = """
            QPushButton {
                color: #cc0000;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #ffeeee;
            }
            QPushButton:disabled {
                color: #999999;
                background-color: #f0f0f0;
            }
        """

        self.rewrite_copywriting_start_btn = QPushButton("开始改写")
        self.rewrite_copywriting_start_btn.setFont(QFont("Microsoft YaHei", 9))
        self.rewrite_copywriting_start_btn.setStyleSheet(primary_btn_style)
        self.rewrite_copywriting_start_btn.clicked.connect(self._on_rewrite_copywriting_start)

        self.rewrite_copywriting_pause_btn = QPushButton("暂停")
        self.rewrite_copywriting_pause_btn.setFont(QFont("Microsoft YaHei", 9))
        self.rewrite_copywriting_pause_btn.setStyleSheet(btn_style)
        self.rewrite_copywriting_pause_btn.setEnabled(False)
        self.rewrite_copywriting_pause_btn.clicked.connect(self._on_rewrite_copywriting_pause)

        self.rewrite_copywriting_resume_btn = QPushButton("继续")
        self.rewrite_copywriting_resume_btn.setFont(QFont("Microsoft YaHei", 9))
        self.rewrite_copywriting_resume_btn.setStyleSheet(btn_style)
        self.rewrite_copywriting_resume_btn.setEnabled(False)
        self.rewrite_copywriting_resume_btn.clicked.connect(self._on_rewrite_copywriting_resume)

        self.rewrite_copywriting_stop_btn = QPushButton("停止")
        self.rewrite_copywriting_stop_btn.setFont(QFont("Microsoft YaHei", 9))
        self.rewrite_copywriting_stop_btn.setStyleSheet(stop_btn_style)
        self.rewrite_copywriting_stop_btn.setEnabled(False)
        self.rewrite_copywriting_stop_btn.clicked.connect(self._on_rewrite_copywriting_stop)

        layout.addWidget(self.rewrite_copywriting_start_btn)
        layout.addWidget(self.rewrite_copywriting_pause_btn)
        layout.addWidget(self.rewrite_copywriting_resume_btn)
        layout.addWidget(self.rewrite_copywriting_stop_btn)

        return toolbar

    def _create_rewrite_copywriting_content_area(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame#rewrite_copywriting_content_frame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)
        frame.setObjectName("rewrite_copywriting_content_frame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        prompt_label = QLabel("提示词 (使用 {content} 变量代表原文案内容)")
        prompt_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        prompt_label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(prompt_label)

        # Template selection area
        template_layout = QHBoxLayout()
        template_layout.setSpacing(3)

        self.rewrite_copywriting_template_combo = QComboBox()
        self.rewrite_copywriting_template_combo.setMinimumWidth(200)
        self.rewrite_copywriting_template_combo.setFont(QFont("Microsoft YaHei", 9))
        self.rewrite_copywriting_template_combo.currentIndexChanged.connect(self._on_rewrite_copywriting_template_selected)
        template_layout.addWidget(self.rewrite_copywriting_template_combo)

        btn_style = """
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e8f4fc;
            }
        """

        self.rewrite_copywriting_save_template_btn = QPushButton("保存为模板")
        self.rewrite_copywriting_save_template_btn.setFont(QFont("Microsoft YaHei", 9))
        self.rewrite_copywriting_save_template_btn.setStyleSheet(btn_style)
        self.rewrite_copywriting_save_template_btn.clicked.connect(self._on_rewrite_copywriting_save_template)
        template_layout.addWidget(self.rewrite_copywriting_save_template_btn)

        self.rewrite_copywriting_delete_template_btn = QPushButton("删除模板")
        self.rewrite_copywriting_delete_template_btn.setFont(QFont("Microsoft YaHei", 9))
        self.rewrite_copywriting_delete_template_btn.setStyleSheet(btn_style)
        self.rewrite_copywriting_delete_template_btn.clicked.connect(self._on_rewrite_copywriting_delete_template)
        template_layout.addWidget(self.rewrite_copywriting_delete_template_btn)

        template_layout.addStretch()
        layout.addLayout(template_layout)

        self.rewrite_copywriting_prompt_input = QTextEdit()
        self.rewrite_copywriting_prompt_input.setPlaceholderText(
            "输入文案改写提示词...\n\n"
            "示例:\n"
            "请将以下文案改写成更加生动有趣的风格，保持原意不变：\n\n"
            "{content}"
        )
        self.rewrite_copywriting_prompt_input.setMinimumHeight(80)
        self.rewrite_copywriting_prompt_input.setMaximumHeight(150)
        self.rewrite_copywriting_prompt_input.setFont(QFont("Microsoft YaHei", 10))
        self.rewrite_copywriting_prompt_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #d0d0d0;
                background-color: #ffffff;
                padding: 5px;
            }
        """)
        layout.addWidget(self.rewrite_copywriting_prompt_input)

        progress_label = QLabel("进度")
        progress_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        progress_label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(progress_label)

        self.rewrite_copywriting_progress_bar = QProgressBar()
        self.rewrite_copywriting_progress_bar.setMinimum(0)
        self.rewrite_copywriting_progress_bar.setMaximum(100)
        self.rewrite_copywriting_progress_bar.setValue(0)
        self.rewrite_copywriting_progress_bar.setFixedHeight(12)
        self.rewrite_copywriting_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #d0d0d0;
                background-color: #f0f0f0;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #0066cc;
            }
        """)
        layout.addWidget(self.rewrite_copywriting_progress_bar)

        self.rewrite_copywriting_stats_label = QLabel("已完成: 0/0  失败: 0  已保存: 0")
        self.rewrite_copywriting_stats_label.setFont(QFont("Microsoft YaHei", 9))
        self.rewrite_copywriting_stats_label.setStyleSheet("color: #666666; border: none;")
        layout.addWidget(self.rewrite_copywriting_stats_label)

        layout.addStretch()

        return frame

    def _create_rewrite_copywriting_status_bar(self) -> QFrame:
        frame = QFrame()
        frame.setFixedHeight(18)
        frame.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border: 1px solid #d0d0d0;
            }
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(6, 1, 6, 1)

        self.rewrite_copywriting_status_text = QLabel("没有运行项目...")
        self.rewrite_copywriting_status_text.setFont(QFont("Microsoft YaHei", 9))
        self.rewrite_copywriting_status_text.setStyleSheet("color: #0066cc; border: none; background: transparent;")
        layout.addWidget(self.rewrite_copywriting_status_text)

        layout.addStretch()

        return frame

    def _create_rewrite_copywriting_log_area(self) -> QFrame:
        frame = QFrame()
        frame.setMinimumHeight(120)
        frame.setMaximumHeight(200)
        frame.setStyleSheet("""
            QFrame#rewrite_copywriting_log_frame {
                background-color: #1e1e1e;
                border: 1px solid #333333;
            }
        """)
        frame.setObjectName("rewrite_copywriting_log_frame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel(" 日志")
        header.setFixedHeight(14)
        header.setFont(QFont("Microsoft YaHei", 9))
        header.setStyleSheet("color: #888888; background-color: #2d2d2d; border: none; padding-left: 8px;")
        layout.addWidget(header)

        self.rewrite_copywriting_log_area = QTextEdit()
        self.rewrite_copywriting_log_area.setReadOnly(True)
        self.rewrite_copywriting_log_area.setFont(QFont("Consolas", 10))
        self.rewrite_copywriting_log_area.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #00ff00;
                border: none;
                padding: 3px;
            }
        """)
        layout.addWidget(self.rewrite_copywriting_log_area)

        return frame

    def _create_copywriting_yindao_rewrite_tab(self) -> QWidget:
        """Create yindao copywriting rewrite sub-tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(3)

        toolbar = self._create_yindao_rewrite_copywriting_toolbar()
        layout.addWidget(toolbar)

        content_frame = self._create_yindao_rewrite_copywriting_content_area()
        layout.addWidget(content_frame, 1)

        status_bar = self._create_yindao_rewrite_copywriting_status_bar()
        layout.addWidget(status_bar)

        log_frame = self._create_yindao_rewrite_copywriting_log_area()
        layout.addWidget(log_frame)

        return widget

    def _create_yindao_rewrite_copywriting_toolbar(self) -> QFrame:
        toolbar = QFrame()
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)

        label_style = "color: #333333; background: transparent; border: none;"

        concurrent_label = QLabel("并发数:")
        concurrent_label.setFont(QFont("Microsoft YaHei", 9))
        concurrent_label.setStyleSheet(label_style)
        self.yindao_rewrite_copywriting_concurrent_spin = QSpinBox()
        self.yindao_rewrite_copywriting_concurrent_spin.setRange(1, 10)
        self.yindao_rewrite_copywriting_concurrent_spin.setValue(3)

        versions_label = QLabel("版本数:")
        versions_label.setFont(QFont("Microsoft YaHei", 9))
        versions_label.setStyleSheet(label_style)
        self.yindao_rewrite_copywriting_versions_spin = QSpinBox()
        self.yindao_rewrite_copywriting_versions_spin.setRange(1, 10)
        self.yindao_rewrite_copywriting_versions_spin.setValue(1)

        layout.addWidget(concurrent_label)
        layout.addWidget(self.yindao_rewrite_copywriting_concurrent_spin)
        layout.addWidget(versions_label)
        layout.addWidget(self.yindao_rewrite_copywriting_versions_spin)

        layout.addStretch()

        btn_style = """
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e8f4fc;
            }
            QPushButton:disabled {
                color: #999999;
                background-color: #f0f0f0;
            }
        """

        primary_btn_style = """
            QPushButton {
                color: #ffffff;
                background-color: #0066cc;
                border: 1px solid #0055aa;
                padding: 2px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0055aa;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                border-color: #bbbbbb;
            }
        """

        stop_btn_style = """
            QPushButton {
                color: #cc0000;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #ffeeee;
            }
            QPushButton:disabled {
                color: #999999;
                background-color: #f0f0f0;
            }
        """

        self.yindao_rewrite_copywriting_start_btn = QPushButton("开始改写")
        self.yindao_rewrite_copywriting_start_btn.setFont(QFont("Microsoft YaHei", 9))
        self.yindao_rewrite_copywriting_start_btn.setStyleSheet(primary_btn_style)
        self.yindao_rewrite_copywriting_start_btn.clicked.connect(self._on_yindao_rewrite_copywriting_start)

        self.yindao_rewrite_copywriting_pause_btn = QPushButton("暂停")
        self.yindao_rewrite_copywriting_pause_btn.setFont(QFont("Microsoft YaHei", 9))
        self.yindao_rewrite_copywriting_pause_btn.setStyleSheet(btn_style)
        self.yindao_rewrite_copywriting_pause_btn.setEnabled(False)
        self.yindao_rewrite_copywriting_pause_btn.clicked.connect(self._on_yindao_rewrite_copywriting_pause)

        self.yindao_rewrite_copywriting_resume_btn = QPushButton("继续")
        self.yindao_rewrite_copywriting_resume_btn.setFont(QFont("Microsoft YaHei", 9))
        self.yindao_rewrite_copywriting_resume_btn.setStyleSheet(btn_style)
        self.yindao_rewrite_copywriting_resume_btn.setEnabled(False)
        self.yindao_rewrite_copywriting_resume_btn.clicked.connect(self._on_yindao_rewrite_copywriting_resume)

        self.yindao_rewrite_copywriting_stop_btn = QPushButton("停止")
        self.yindao_rewrite_copywriting_stop_btn.setFont(QFont("Microsoft YaHei", 9))
        self.yindao_rewrite_copywriting_stop_btn.setStyleSheet(stop_btn_style)
        self.yindao_rewrite_copywriting_stop_btn.setEnabled(False)
        self.yindao_rewrite_copywriting_stop_btn.clicked.connect(self._on_yindao_rewrite_copywriting_stop)

        layout.addWidget(self.yindao_rewrite_copywriting_start_btn)
        layout.addWidget(self.yindao_rewrite_copywriting_pause_btn)
        layout.addWidget(self.yindao_rewrite_copywriting_resume_btn)
        layout.addWidget(self.yindao_rewrite_copywriting_stop_btn)

        return toolbar

    def _create_yindao_rewrite_copywriting_content_area(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame#yindao_rewrite_copywriting_content_frame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)
        frame.setObjectName("yindao_rewrite_copywriting_content_frame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        prompt_label = QLabel("提示词 (使用 {content} 变量代表原文案内容)")
        prompt_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        prompt_label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(prompt_label)

        template_layout = QHBoxLayout()
        template_layout.setSpacing(3)

        self.yindao_rewrite_copywriting_template_combo = QComboBox()
        self.yindao_rewrite_copywriting_template_combo.setMinimumWidth(200)
        self.yindao_rewrite_copywriting_template_combo.setFont(QFont("Microsoft YaHei", 9))
        self.yindao_rewrite_copywriting_template_combo.currentIndexChanged.connect(self._on_yindao_rewrite_copywriting_template_selected)
        template_layout.addWidget(self.yindao_rewrite_copywriting_template_combo)

        btn_style = """
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e8f4fc;
            }
        """

        self.yindao_rewrite_copywriting_save_template_btn = QPushButton("保存为模板")
        self.yindao_rewrite_copywriting_save_template_btn.setFont(QFont("Microsoft YaHei", 9))
        self.yindao_rewrite_copywriting_save_template_btn.setStyleSheet(btn_style)
        self.yindao_rewrite_copywriting_save_template_btn.clicked.connect(self._on_yindao_rewrite_copywriting_save_template)
        template_layout.addWidget(self.yindao_rewrite_copywriting_save_template_btn)

        self.yindao_rewrite_copywriting_delete_template_btn = QPushButton("删除模板")
        self.yindao_rewrite_copywriting_delete_template_btn.setFont(QFont("Microsoft YaHei", 9))
        self.yindao_rewrite_copywriting_delete_template_btn.setStyleSheet(btn_style)
        self.yindao_rewrite_copywriting_delete_template_btn.clicked.connect(self._on_yindao_rewrite_copywriting_delete_template)
        template_layout.addWidget(self.yindao_rewrite_copywriting_delete_template_btn)

        template_layout.addStretch()
        layout.addLayout(template_layout)

        self.yindao_rewrite_copywriting_prompt_input = QTextEdit()
        self.yindao_rewrite_copywriting_prompt_input.setPlaceholderText(
            "输入文案改写提示词...\n\n"
            "示例:\n"
            "请将以下文案改写成更加生动有趣的风格，保持原意不变：\n\n"
            "{content}"
        )
        self.yindao_rewrite_copywriting_prompt_input.setMinimumHeight(80)
        self.yindao_rewrite_copywriting_prompt_input.setMaximumHeight(150)
        self.yindao_rewrite_copywriting_prompt_input.setFont(QFont("Microsoft YaHei", 10))
        self.yindao_rewrite_copywriting_prompt_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #d0d0d0;
                background-color: #ffffff;
                padding: 5px;
            }
        """)
        layout.addWidget(self.yindao_rewrite_copywriting_prompt_input)

        progress_label = QLabel("进度")
        progress_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        progress_label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(progress_label)

        self.yindao_rewrite_copywriting_progress_bar = QProgressBar()
        self.yindao_rewrite_copywriting_progress_bar.setMinimum(0)
        self.yindao_rewrite_copywriting_progress_bar.setMaximum(100)
        self.yindao_rewrite_copywriting_progress_bar.setValue(0)
        self.yindao_rewrite_copywriting_progress_bar.setFixedHeight(12)
        self.yindao_rewrite_copywriting_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #d0d0d0;
                background-color: #f0f0f0;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #0066cc;
            }
        """)
        layout.addWidget(self.yindao_rewrite_copywriting_progress_bar)

        self.yindao_rewrite_copywriting_stats_label = QLabel("已完成: 0/0  失败: 0  已保存: 0")
        self.yindao_rewrite_copywriting_stats_label.setFont(QFont("Microsoft YaHei", 9))
        self.yindao_rewrite_copywriting_stats_label.setStyleSheet("color: #666666; border: none;")
        layout.addWidget(self.yindao_rewrite_copywriting_stats_label)

        layout.addStretch()

        return frame

    def _create_yindao_rewrite_copywriting_status_bar(self) -> QFrame:
        frame = QFrame()
        frame.setFixedHeight(18)
        frame.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border: 1px solid #d0d0d0;
            }
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(6, 1, 6, 1)

        self.yindao_rewrite_copywriting_status_text = QLabel("没有运行项目...")
        self.yindao_rewrite_copywriting_status_text.setFont(QFont("Microsoft YaHei", 9))
        self.yindao_rewrite_copywriting_status_text.setStyleSheet("color: #0066cc; border: none; background: transparent;")
        layout.addWidget(self.yindao_rewrite_copywriting_status_text)

        layout.addStretch()

        return frame

    def _create_yindao_rewrite_copywriting_log_area(self) -> QFrame:
        frame = QFrame()
        frame.setMinimumHeight(120)
        frame.setMaximumHeight(200)
        frame.setStyleSheet("""
            QFrame#yindao_rewrite_copywriting_log_frame {
                background-color: #1e1e1e;
                border: 1px solid #333333;
            }
        """)
        frame.setObjectName("yindao_rewrite_copywriting_log_frame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel(" 日志")
        header.setFixedHeight(14)
        header.setFont(QFont("Microsoft YaHei", 9))
        header.setStyleSheet("color: #888888; background-color: #2d2d2d; border: none; padding-left: 8px;")
        layout.addWidget(header)

        self.yindao_rewrite_copywriting_log_area = QTextEdit()
        self.yindao_rewrite_copywriting_log_area.setReadOnly(True)
        self.yindao_rewrite_copywriting_log_area.setFont(QFont("Consolas", 10))
        self.yindao_rewrite_copywriting_log_area.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #00ff00;
                border: none;
                padding: 3px;
            }
        """)
        layout.addWidget(self.yindao_rewrite_copywriting_log_area)

        return frame

    def _create_copywriting_toolbar(self) -> QFrame:
        toolbar = QFrame()
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)

        label_style = "color: #333333; background: transparent; border: none;"

        count_label = QLabel("请求次数:")
        count_label.setFont(QFont("Microsoft YaHei", 9))
        count_label.setStyleSheet(label_style)
        self.copywriting_count_spin = QSpinBox()
        self.copywriting_count_spin.setRange(1, 100)
        self.copywriting_count_spin.setValue(10)

        concurrent_label = QLabel("并发数:")
        concurrent_label.setFont(QFont("Microsoft YaHei", 9))
        concurrent_label.setStyleSheet(label_style)
        self.copywriting_concurrent_spin = QSpinBox()
        self.copywriting_concurrent_spin.setRange(1, 10)
        self.copywriting_concurrent_spin.setValue(3)

        layout.addWidget(count_label)
        layout.addWidget(self.copywriting_count_spin)
        layout.addWidget(concurrent_label)
        layout.addWidget(self.copywriting_concurrent_spin)

        layout.addStretch()

        btn_style = """
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e8f4fc;
            }
            QPushButton:disabled {
                color: #999999;
                background-color: #f0f0f0;
            }
        """

        primary_btn_style = """
            QPushButton {
                color: #ffffff;
                background-color: #0066cc;
                border: 1px solid #0055aa;
                padding: 2px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0055aa;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                border-color: #bbbbbb;
            }
        """

        stop_btn_style = """
            QPushButton {
                color: #cc0000;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #ffeeee;
            }
            QPushButton:disabled {
                color: #999999;
                background-color: #f0f0f0;
            }
        """

        self.copywriting_start_btn = QPushButton("开始生成")
        self.copywriting_start_btn.setFont(QFont("Microsoft YaHei", 9))
        self.copywriting_start_btn.setStyleSheet(primary_btn_style)
        self.copywriting_start_btn.clicked.connect(self._on_copywriting_start)

        self.copywriting_pause_btn = QPushButton("暂停")
        self.copywriting_pause_btn.setFont(QFont("Microsoft YaHei", 9))
        self.copywriting_pause_btn.setStyleSheet(btn_style)
        self.copywriting_pause_btn.setEnabled(False)
        self.copywriting_pause_btn.clicked.connect(self._on_copywriting_pause)

        self.copywriting_resume_btn = QPushButton("继续")
        self.copywriting_resume_btn.setFont(QFont("Microsoft YaHei", 9))
        self.copywriting_resume_btn.setStyleSheet(btn_style)
        self.copywriting_resume_btn.setEnabled(False)
        self.copywriting_resume_btn.clicked.connect(self._on_copywriting_resume)

        self.copywriting_stop_btn = QPushButton("停止")
        self.copywriting_stop_btn.setFont(QFont("Microsoft YaHei", 9))
        self.copywriting_stop_btn.setStyleSheet(stop_btn_style)
        self.copywriting_stop_btn.setEnabled(False)
        self.copywriting_stop_btn.clicked.connect(self._on_copywriting_stop)

        layout.addWidget(self.copywriting_start_btn)
        layout.addWidget(self.copywriting_pause_btn)
        layout.addWidget(self.copywriting_resume_btn)
        layout.addWidget(self.copywriting_stop_btn)

        return toolbar

    def _create_copywriting_content_area(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame#copywriting_content_frame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)
        frame.setObjectName("copywriting_content_frame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        prompt_label = QLabel("提示词")
        prompt_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        prompt_label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(prompt_label)

        # Template selection area
        template_layout = QHBoxLayout()
        template_layout.setSpacing(3)

        self.copywriting_template_combo = QComboBox()
        self.copywriting_template_combo.setMinimumWidth(200)
        self.copywriting_template_combo.setFont(QFont("Microsoft YaHei", 9))
        self.copywriting_template_combo.currentIndexChanged.connect(self._on_copywriting_template_selected)
        template_layout.addWidget(self.copywriting_template_combo)

        btn_style = """
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e8f4fc;
            }
        """

        self.copywriting_save_template_btn = QPushButton("保存为模板")
        self.copywriting_save_template_btn.setFont(QFont("Microsoft YaHei", 9))
        self.copywriting_save_template_btn.setStyleSheet(btn_style)
        self.copywriting_save_template_btn.clicked.connect(self._on_copywriting_save_template)
        template_layout.addWidget(self.copywriting_save_template_btn)

        self.copywriting_delete_template_btn = QPushButton("删除模板")
        self.copywriting_delete_template_btn.setFont(QFont("Microsoft YaHei", 9))
        self.copywriting_delete_template_btn.setStyleSheet(btn_style)
        self.copywriting_delete_template_btn.clicked.connect(self._on_copywriting_delete_template)
        template_layout.addWidget(self.copywriting_delete_template_btn)

        template_layout.addStretch()
        layout.addLayout(template_layout)

        self.copywriting_prompt_input = QTextEdit()
        self.copywriting_prompt_input.setPlaceholderText("输入视频文案生成提示词...")
        self.copywriting_prompt_input.setMinimumHeight(60)
        self.copywriting_prompt_input.setMaximumHeight(120)
        self.copywriting_prompt_input.setFont(QFont("Microsoft YaHei", 10))
        self.copywriting_prompt_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #d0d0d0;
                background-color: #ffffff;
                padding: 5px;
            }
        """)
        layout.addWidget(self.copywriting_prompt_input)

        progress_label = QLabel("进度")
        progress_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        progress_label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(progress_label)

        self.copywriting_progress_bar = QProgressBar()
        self.copywriting_progress_bar.setMinimum(0)
        self.copywriting_progress_bar.setMaximum(100)
        self.copywriting_progress_bar.setValue(0)
        self.copywriting_progress_bar.setFixedHeight(12)
        self.copywriting_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #d0d0d0;
                background-color: #f0f0f0;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #0066cc;
            }
        """)
        layout.addWidget(self.copywriting_progress_bar)

        self.copywriting_stats_label = QLabel("已完成: 0/0  失败: 0  已保存: 0")
        self.copywriting_stats_label.setFont(QFont("Microsoft YaHei", 9))
        self.copywriting_stats_label.setStyleSheet("color: #666666; border: none;")
        layout.addWidget(self.copywriting_stats_label)

        layout.addStretch()

        return frame

    def _create_copywriting_status_bar(self) -> QFrame:
        frame = QFrame()
        frame.setFixedHeight(18)
        frame.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border: 1px solid #d0d0d0;
            }
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(6, 1, 6, 1)

        self.copywriting_status_text = QLabel("没有运行项目...")
        self.copywriting_status_text.setFont(QFont("Microsoft YaHei", 9))
        self.copywriting_status_text.setStyleSheet("color: #0066cc; border: none; background: transparent;")
        layout.addWidget(self.copywriting_status_text)

        layout.addStretch()

        return frame

    def _create_copywriting_log_area(self) -> QFrame:
        frame = QFrame()
        frame.setMinimumHeight(120)
        frame.setMaximumHeight(200)
        frame.setStyleSheet("""
            QFrame#copywriting_log_frame {
                background-color: #1e1e1e;
                border: 1px solid #333333;
            }
        """)
        frame.setObjectName("copywriting_log_frame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel(" 日志")
        header.setFixedHeight(14)
        header.setFont(QFont("Microsoft YaHei", 9))
        header.setStyleSheet("color: #888888; background-color: #2d2d2d; border: none; padding-left: 8px;")
        layout.addWidget(header)

        self.copywriting_log_area = QTextEdit()
        self.copywriting_log_area.setReadOnly(True)
        self.copywriting_log_area.setFont(QFont("Consolas", 10))
        self.copywriting_log_area.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #00ff00;
                border: none;
                padding: 3px;
            }
        """)
        layout.addWidget(self.copywriting_log_area)

        return frame

    def _create_video_toolbar(self) -> QFrame:
        toolbar = QFrame()
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)

        label_style = "color: #333333; background: transparent; border: none;"
        spin_style = """
            QSpinBox {
                border: 1px solid #d0d0d0;
                padding: 1px 4px;
                background: #ffffff;
                min-width: 70px;
            }
        """

        count_label = QLabel("转换数量:")
        count_label.setFont(QFont("Microsoft YaHei", 9))
        count_label.setStyleSheet(label_style)
        self.video_count_spin = QSpinBox()
        self.video_count_spin.setRange(1, 1000)
        self.video_count_spin.setValue(5)
        self.video_count_spin.setStyleSheet(spin_style)

        concurrent_label = QLabel("并发数:")
        concurrent_label.setFont(QFont("Microsoft YaHei", 9))
        concurrent_label.setStyleSheet(label_style)
        self.video_concurrent_spin = QSpinBox()
        self.video_concurrent_spin.setRange(1, 20)
        self.video_concurrent_spin.setValue(3)
        self.video_concurrent_spin.setStyleSheet(spin_style)

        layout.addWidget(count_label)
        layout.addWidget(self.video_count_spin)
        layout.addWidget(concurrent_label)
        layout.addWidget(self.video_concurrent_spin)

        layout.addStretch()

        btn_style = """
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e8f4fc;
            }
            QPushButton:disabled {
                color: #999999;
                background-color: #f0f0f0;
            }
        """

        primary_btn_style = """
            QPushButton {
                color: #ffffff;
                background-color: #0066cc;
                border: 1px solid #0055aa;
                padding: 2px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0055aa;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                border-color: #bbbbbb;
            }
        """

        stop_btn_style = """
            QPushButton {
                color: #cc0000;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #ffeeee;
            }
            QPushButton:disabled {
                color: #999999;
                background-color: #f0f0f0;
            }
        """

        self.video_start_btn = QPushButton("开始生成")
        self.video_start_btn.setFont(QFont("Microsoft YaHei", 9))
        self.video_start_btn.setStyleSheet(primary_btn_style)
        self.video_start_btn.clicked.connect(self._on_video_start)

        self.video_pause_btn = QPushButton("暂停")
        self.video_pause_btn.setFont(QFont("Microsoft YaHei", 9))
        self.video_pause_btn.setStyleSheet(btn_style)
        self.video_pause_btn.setEnabled(False)
        self.video_pause_btn.clicked.connect(self._on_video_pause)

        self.video_resume_btn = QPushButton("继续")
        self.video_resume_btn.setFont(QFont("Microsoft YaHei", 9))
        self.video_resume_btn.setStyleSheet(btn_style)
        self.video_resume_btn.setEnabled(False)
        self.video_resume_btn.clicked.connect(self._on_video_resume)

        self.video_stop_btn = QPushButton("停止")
        self.video_stop_btn.setFont(QFont("Microsoft YaHei", 9))
        self.video_stop_btn.setStyleSheet(stop_btn_style)
        self.video_stop_btn.setEnabled(False)
        self.video_stop_btn.clicked.connect(self._on_video_stop)

        layout.addWidget(self.video_start_btn)
        layout.addWidget(self.video_pause_btn)
        layout.addWidget(self.video_resume_btn)
        layout.addWidget(self.video_stop_btn)

        return toolbar

    def _create_video_content_area(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame#video_content_frame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)
        frame.setObjectName("video_content_frame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        prompt_label = QLabel("提示词")
        prompt_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        prompt_label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(prompt_label)

        # Template selection area
        template_layout = QHBoxLayout()
        template_layout.setSpacing(3)

        self.video_template_combo = QComboBox()
        self.video_template_combo.setMinimumWidth(200)
        self.video_template_combo.setFont(QFont("Microsoft YaHei", 9))
        self.video_template_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #d0d0d0;
                padding: 1px 4px;
                background: #ffffff;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        self.video_template_combo.currentIndexChanged.connect(self._on_video_template_selected)
        template_layout.addWidget(self.video_template_combo)

        btn_style = """
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e8f4fc;
            }
        """

        self.video_save_template_btn = QPushButton("保存为模板")
        self.video_save_template_btn.setFont(QFont("Microsoft YaHei", 9))
        self.video_save_template_btn.setStyleSheet(btn_style)
        self.video_save_template_btn.clicked.connect(self._on_video_save_template)
        template_layout.addWidget(self.video_save_template_btn)

        self.video_delete_template_btn = QPushButton("删除模板")
        self.video_delete_template_btn.setFont(QFont("Microsoft YaHei", 9))
        self.video_delete_template_btn.setStyleSheet(btn_style)
        self.video_delete_template_btn.clicked.connect(self._on_video_delete_template)
        template_layout.addWidget(self.video_delete_template_btn)

        template_layout.addStretch()
        layout.addLayout(template_layout)

        self.video_prompt_input = QTextEdit()
        self.video_prompt_input.setPlaceholderText("输入视频生成提示词...")
        self.video_prompt_input.setMinimumHeight(60)
        self.video_prompt_input.setMaximumHeight(120)
        self.video_prompt_input.setFont(QFont("Microsoft YaHei", 10))
        self.video_prompt_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #d0d0d0;
                background-color: #ffffff;
                padding: 5px;
            }
        """)
        layout.addWidget(self.video_prompt_input)

        # Image count info
        self.video_image_info_label = QLabel("图片素材: 当前文件夹有 0 张图片")
        self.video_image_info_label.setFont(QFont("Microsoft YaHei", 9))
        self.video_image_info_label.setStyleSheet("color: #666666; border: none;")
        layout.addWidget(self.video_image_info_label)

        progress_label = QLabel("进度")
        progress_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        progress_label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(progress_label)

        self.video_progress_bar = QProgressBar()
        self.video_progress_bar.setMinimum(0)
        self.video_progress_bar.setMaximum(100)
        self.video_progress_bar.setValue(0)
        self.video_progress_bar.setFixedHeight(12)
        self.video_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #d0d0d0;
                background-color: #f0f0f0;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #0066cc;
            }
        """)
        layout.addWidget(self.video_progress_bar)

        self.video_stats_label = QLabel("提交: 0/0  完成: 0/0  下载: 0/0")
        self.video_stats_label.setFont(QFont("Microsoft YaHei", 9))
        self.video_stats_label.setStyleSheet("color: #666666; border: none;")
        layout.addWidget(self.video_stats_label)

        layout.addStretch()

        return frame

    def _create_video_status_bar(self) -> QFrame:
        frame = QFrame()
        frame.setFixedHeight(18)
        frame.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border: 1px solid #d0d0d0;
            }
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(6, 1, 6, 1)

        self.video_status_text = QLabel("没有运行项目...")
        self.video_status_text.setFont(QFont("Microsoft YaHei", 9))
        self.video_status_text.setStyleSheet("color: #0066cc; border: none; background: transparent;")
        layout.addWidget(self.video_status_text)

        layout.addStretch()

        return frame

    def _create_video_log_area(self) -> QFrame:
        frame = QFrame()
        frame.setMinimumHeight(120)
        frame.setMaximumHeight(200)
        frame.setStyleSheet("""
            QFrame#video_log_frame {
                background-color: #1e1e1e;
                border: 1px solid #333333;
            }
        """)
        frame.setObjectName("video_log_frame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel(" 日志")
        header.setFixedHeight(14)
        header.setFont(QFont("Microsoft YaHei", 9))
        header.setStyleSheet("color: #888888; background-color: #2d2d2d; border: none; padding-left: 8px;")
        layout.addWidget(header)

        self.video_log_area = QTextEdit()
        self.video_log_area.setReadOnly(True)
        self.video_log_area.setFont(QFont("Consolas", 10))
        self.video_log_area.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #00ff00;
                border: none;
                padding: 3px;
            }
        """)
        layout.addWidget(self.video_log_area)

        return frame

    def _create_toolbar(self) -> QFrame:
        toolbar = QFrame()
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)

        label_style = "color: #333333; background: transparent; border: none;"
        spin_style = """
            QSpinBox {
                border: 1px solid #d0d0d0;
                padding: 1px 4px;
                background: #ffffff;
                min-width: 70px;
            }
        """

        request_label = QLabel("请求次数:")
        request_label.setFont(QFont("Microsoft YaHei", 9))
        request_label.setStyleSheet(label_style)
        self.request_spin = QSpinBox()
        self.request_spin.setRange(1, 1000)
        self.request_spin.setValue(10)
        self.request_spin.setStyleSheet(spin_style)

        concurrent_label = QLabel("并行数:")
        concurrent_label.setFont(QFont("Microsoft YaHei", 9))
        concurrent_label.setStyleSheet(label_style)
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 200)
        self.concurrent_spin.setValue(self.config.settings.max_concurrent)
        self.concurrent_spin.setStyleSheet(spin_style)

        layout.addWidget(request_label)
        layout.addWidget(self.request_spin)
        layout.addWidget(concurrent_label)
        layout.addWidget(self.concurrent_spin)

        layout.addStretch()

        btn_style = """
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e8f4fc;
            }
            QPushButton:disabled {
                color: #999999;
                background-color: #f0f0f0;
            }
        """

        primary_btn_style = """
            QPushButton {
                color: #ffffff;
                background-color: #0066cc;
                border: 1px solid #0055aa;
                padding: 2px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0055aa;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                border-color: #bbbbbb;
            }
        """

        stop_btn_style = """
            QPushButton {
                color: #cc0000;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #ffeeee;
            }
            QPushButton:disabled {
                color: #999999;
                background-color: #f0f0f0;
            }
        """

        self.start_btn = QPushButton("开始生图")
        self.start_btn.setFont(QFont("Microsoft YaHei", 9))
        self.start_btn.setStyleSheet(primary_btn_style)
        self.start_btn.clicked.connect(self._on_start)

        self.pause_btn = QPushButton("暂停")
        self.pause_btn.setFont(QFont("Microsoft YaHei", 9))
        self.pause_btn.setStyleSheet(btn_style)
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._on_pause)

        self.resume_btn = QPushButton("继续")
        self.resume_btn.setFont(QFont("Microsoft YaHei", 9))
        self.resume_btn.setStyleSheet(btn_style)
        self.resume_btn.setEnabled(False)
        self.resume_btn.clicked.connect(self._on_resume)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setFont(QFont("Microsoft YaHei", 9))
        self.stop_btn.setStyleSheet(stop_btn_style)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop)

        layout.addWidget(self.start_btn)
        layout.addWidget(self.pause_btn)
        layout.addWidget(self.resume_btn)
        layout.addWidget(self.stop_btn)

        return toolbar

    def _create_content_area(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame#content_frame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)
        frame.setObjectName("content_frame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        prompt_label = QLabel("提示词")
        prompt_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        prompt_label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(prompt_label)

        # Template selection area
        template_layout = QHBoxLayout()
        template_layout.setSpacing(3)

        self.template_combo = QComboBox()
        self.template_combo.setMinimumWidth(200)
        self.template_combo.setFont(QFont("Microsoft YaHei", 9))
        self.template_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #d0d0d0;
                padding: 1px 4px;
                background: #ffffff;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        self.template_combo.currentIndexChanged.connect(self._on_template_selected)
        template_layout.addWidget(self.template_combo)

        btn_style = """
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e8f4fc;
            }
        """

        self.save_template_btn = QPushButton("保存为模板")
        self.save_template_btn.setFont(QFont("Microsoft YaHei", 9))
        self.save_template_btn.setStyleSheet(btn_style)
        self.save_template_btn.clicked.connect(self._on_save_template)
        template_layout.addWidget(self.save_template_btn)

        self.delete_template_btn = QPushButton("删除模板")
        self.delete_template_btn.setFont(QFont("Microsoft YaHei", 9))
        self.delete_template_btn.setStyleSheet(btn_style)
        self.delete_template_btn.clicked.connect(self._on_delete_template)
        template_layout.addWidget(self.delete_template_btn)

        template_layout.addStretch()
        layout.addLayout(template_layout)

        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("输入图片描述提示词...")
        self.prompt_input.setMinimumHeight(60)
        self.prompt_input.setMaximumHeight(120)
        self.prompt_input.setFont(QFont("Microsoft YaHei", 10))
        self.prompt_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #d0d0d0;
                background-color: #ffffff;
                padding: 5px;
            }
        """)
        layout.addWidget(self.prompt_input)

        progress_label = QLabel("进度")
        progress_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        progress_label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #d0d0d0;
                background-color: #f0f0f0;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #0066cc;
            }
        """)
        layout.addWidget(self.progress_bar)

        self.stats_label = QLabel("请求: 0/0  图片: 0/0")
        self.stats_label.setFont(QFont("Microsoft YaHei", 9))
        self.stats_label.setStyleSheet("color: #666666; border: none;")
        layout.addWidget(self.stats_label)

        layout.addStretch()

        return frame

    def _create_status_bar(self) -> QFrame:
        frame = QFrame()
        frame.setFixedHeight(18)
        frame.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border: 1px solid #d0d0d0;
            }
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(6, 1, 6, 1)

        self.status_text = QLabel("没有运行项目...")
        self.status_text.setFont(QFont("Microsoft YaHei", 9))
        self.status_text.setStyleSheet("color: #0066cc; border: none; background: transparent;")
        layout.addWidget(self.status_text)

        layout.addStretch()

        return frame

    def _create_log_area(self) -> QFrame:
        frame = QFrame()
        frame.setMinimumHeight(120)
        frame.setMaximumHeight(200)
        frame.setStyleSheet("""
            QFrame#log_frame {
                background-color: #1e1e1e;
                border: 1px solid #333333;
            }
        """)
        frame.setObjectName("log_frame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel(" 日志")
        header.setFixedHeight(14)
        header.setFont(QFont("Microsoft YaHei", 9))
        header.setStyleSheet("color: #888888; background-color: #2d2d2d; border: none; padding-left: 8px;")
        layout.addWidget(header)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFont(QFont("Consolas", 10))
        self.log_area.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #00ff00;
                border: none;
                padding: 3px;
            }
        """)
        layout.addWidget(self.log_area)

        return frame

    def _log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

        color_map = {
            "info": "#00ff00",
            "warning": "#ffff00",
            "error": "#ff0000",
            "success": "#00ff00",
        }
        color = color_map.get(level, "#00ff00")

        html = f'<span style="color: #888888;">[{timestamp}]</span> '
        html += f'<span style="color: {color};">{message}</span>'
        self.log_area.append(html)

        cursor = self.log_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_area.setTextCursor(cursor)

    def _update_progress(self, progress: TaskProgress):
        if progress.total_requests > 0:
            percent = int(progress.completed_requests / progress.total_requests * 100)
            self.progress_bar.setValue(percent)

        self.stats_label.setText(
            f"请求: {progress.completed_requests}/{progress.total_requests} "
            f"(成功: {progress.success_requests}, 失败: {progress.failed_requests})  "
            f"图片: {progress.downloaded_images}/{progress.total_images}"
        )

        self.status_text.setText(
            f"运行中 - 请求: {progress.completed_requests}/{progress.total_requests}"
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
            self.status_text.setText("没有运行项目...")
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
            self.status_text.setText("已暂停")

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
        self._log(f"开始生图任务: {request_count} 次请求, 并行数: {max_concurrent}", "info")

    def _on_pause(self):
        if self.task_manager:
            self.task_manager.pause()
            self._set_buttons_state("paused")
            self._log("任务已暂停", "warning")

    def _on_resume(self):
        if self.task_manager:
            self.task_manager.resume()
            self._set_buttons_state("running")
            self._log("任务已继续", "info")

    def _on_stop(self):
        if self.task_manager:
            self.task_manager.stop()
            self._log("正在停止任务...", "warning")

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

            self._log(
                f"任务完成! 成功: {progress.success_requests}, "
                f"失败: {progress.failed_requests}, "
                f"图片: {progress.downloaded_images}",
                "success"
            )
        else:
            self._log("任务异常结束", "error")

        self.task_manager = None
        self.worker = None

    def refresh_config(self):
        self.concurrent_spin.setValue(self.config.settings.max_concurrent)

    def _load_templates(self):
        """Load templates into combo box"""
        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        self.template_combo.addItem("-- 选择模板 --", None)
        for template in self.config.templates:
            self.template_combo.addItem(template.name, template.content)
        self.template_combo.blockSignals(False)
        # Also load video templates
        self._load_video_templates()
        # Also load copywriting templates
        self._load_copywriting_templates()

    def _on_template_selected(self, index: int):
        """Fill prompt when template is selected"""
        if index <= 0:
            return
        content = self.template_combo.itemData(index)
        if content:
            self.prompt_input.setPlainText(content)

    def _on_save_template(self):
        """Save current prompt as template"""
        from ..models.config import PromptTemplate

        prompt = self.prompt_input.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "提示", "请先输入提示词")
            return

        name, ok = QInputDialog.getText(self, "保存模板", "请输入模板名称:")
        if not ok or not name.strip():
            return

        name = name.strip()

        # Check if name already exists
        for i, template in enumerate(self.config.templates):
            if template.name == name:
                reply = QMessageBox.question(
                    self, "确认",
                    f"模板 '{name}' 已存在，是否覆盖？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.config.templates[i] = PromptTemplate(name=name, content=prompt)
                    self.config.save()
                    self._load_templates()
                    QMessageBox.information(self, "成功", f"模板 '{name}' 已更新")
                return

        # Add new template
        self.config.templates.append(PromptTemplate(name=name, content=prompt))
        self.config.save()
        self._load_templates()
        QMessageBox.information(self, "成功", f"模板 '{name}' 已保存")

    def _on_delete_template(self):
        """Delete selected template"""
        index = self.template_combo.currentIndex()
        if index <= 0:
            QMessageBox.warning(self, "提示", "请先选择要删除的模板")
            return

        name = self.template_combo.currentText()
        reply = QMessageBox.question(
            self, "确认",
            f"确定要删除模板 '{name}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        # Find and remove template
        self.config.templates = [t for t in self.config.templates if t.name != name]
        self.config.save()
        self._load_templates()
        QMessageBox.information(self, "成功", f"模板 '{name}' 已删除")

    def load_last_prompt(self):
        """Load last prompt on startup"""
        if self.config.last_prompt:
            self.prompt_input.setPlainText(self.config.last_prompt)

    def save_current_prompt(self):
        """Save current prompt for next startup"""
        self.config.last_prompt = self.prompt_input.toPlainText().strip()
        self.config.last_copywriting_prompt = self.copywriting_prompt_input.toPlainText().strip()
        self.config.last_image_recognition_prompt = self.image_recognition_prompt_input.toPlainText().strip()
        self.config.last_merge_copywriting_prompt = self.merge_copywriting_prompt_input.toPlainText().strip()
        self.config.last_rewrite_copywriting_prompt = self.rewrite_copywriting_prompt_input.toPlainText().strip()
        self._save_ui_state()

    def _save_ui_state(self):
        """Save UI state for next startup"""
        state = self.config.ui_state

        # 标签页索引
        state.home_tab_index = self.tab_widget.currentIndex()

        # 视频文案
        state.copywriting_count = self.copywriting_count_spin.value()
        state.copywriting_concurrent = self.copywriting_concurrent_spin.value()

        # 图片识别
        state.image_recognition_count = self.image_recognition_count_spin.value()
        state.image_recognition_concurrent = self.image_recognition_concurrent_spin.value()
        state.image_recognition_folders = [
            item.text() for item in self.product_folder_list.selectedItems()
        ]

        # 合并文案
        state.merge_copywriting_count = self.merge_copywriting_count_spin.value()
        state.merge_copywriting_concurrent = self.merge_copywriting_concurrent_spin.value()
        state.merge_copywriting_folders = [
            item.text() for item in self.merge_product_folder_list.selectedItems()
        ]

        # 语音生成
        if self.tts_liuliang_radio.isChecked():
            state.tts_mode = "liuliang"
        elif self.tts_yindao_radio.isChecked():
            state.tts_mode = "yindao"
        else:
            state.tts_mode = "daihuo"
        state.tts_count = self.tts_count_spin.value()
        state.tts_concurrent = self.tts_concurrent_spin.value()
        state.tts_folders = [
            item.text() for item in self.tts_folder_list.selectedItems()
        ]

        # 图片生成
        state.image_request_count = self.request_spin.value()

        # 视频生成
        state.video_count = self.video_count_spin.value()
        state.video_concurrent = self.video_concurrent_spin.value()

        # 带货视频合成
        state.compose_count = self.video_compose_count_spin.value()
        state.compose_concurrent = self.video_compose_concurrent_spin.value()
        state.compose_clip_duration_min = self.video_compose_clip_duration_min_spin.value()
        state.compose_clip_duration_max = self.video_compose_clip_duration_max_spin.value()
        state.compose_resolution = self.video_compose_resolution_combo.currentText()
        state.compose_product_video_count = self.video_compose_product_video_count_spin.value()
        state.compose_product_image_count = self.video_compose_product_image_count_spin.value()
        state.compose_product_image_duration_min = self.video_compose_product_image_duration_min_spin.value()
        state.compose_product_image_duration_max = self.video_compose_product_image_duration_max_spin.value()
        state.compose_priority_video = self.video_compose_priority_video_checkbox.isChecked()
        state.compose_overlay_mode = self.video_compose_overlay_mode_checkbox.isChecked()
        state.compose_bgm_volume = self.video_compose_bgm_slider.value()
        state.compose_voice_volume = self.video_compose_voice_slider.value()
        state.compose_effect_type = self.video_compose_effect_combo.currentData()
        state.compose_effect_strength = self.video_compose_effect_slider.value()
        state.compose_folders = [
            item.text() for item in self.video_compose_folder_list.selectedItems()
        ]

        # 扒文案
        state.extract_copywriting_concurrent = self.extract_copywriting_concurrent_spin.value()
        state.extract_copywriting_model = self.extract_copywriting_model_combo.currentText()
        state.extract_copywriting_device = self.extract_copywriting_device_combo.currentText()

        # 字幕生成方式
        if self.tts_liuliang_radio.isChecked():
            state.tts_subtitle_method_liuliang = "local" if self.tts_subtitle_local_radio.isChecked() else "api"
        elif self.tts_yindao_radio.isChecked():
            state.tts_subtitle_method_yindao = "local" if self.tts_subtitle_local_radio.isChecked() else "api"
        else:
            state.tts_subtitle_method_daihuo = "local" if self.tts_subtitle_local_radio.isChecked() else "api"

        state.tts_local_model = self.tts_local_model_combo.currentText()
        state.tts_local_device = self.tts_local_device_combo.currentText()

        # 文案改写
        state.rewrite_copywriting_concurrent = self.rewrite_copywriting_concurrent_spin.value()
        state.rewrite_copywriting_versions = self.rewrite_copywriting_versions_spin.value()

        # 普通视频生成
        state.normal_video_count = self.normal_video_count_spin.value()
        state.normal_video_concurrent = self.normal_video_concurrent_spin.value()
        state.normal_video_clip_duration_min = self.normal_video_clip_duration_min_spin.value()
        state.normal_video_clip_duration_max = self.normal_video_clip_duration_max_spin.value()
        state.normal_video_resolution = self.normal_video_resolution_combo.currentText()
        state.normal_video_bgm_volume = self.normal_video_bgm_slider.value()
        state.normal_video_voice_volume = self.normal_video_voice_slider.value()
        state.normal_video_liuliang_checked = self.normal_video_liuliang_check.isChecked()
        state.normal_video_yindao_checked = self.normal_video_yindao_check.isChecked()
        state.normal_video_chuchuang_checked = self.normal_video_chuchuang_check.isChecked()
        state.normal_video_chuchuang_duration = self.normal_video_chuchuang_duration_spin.value()
        state.normal_video_chuchuang_material_type = self.normal_video_chuchuang_material_combo.currentText()

    def _load_ui_state(self):
        """Load UI state from config"""
        state = self.config.ui_state

        # 标签页索引
        if 0 <= state.home_tab_index < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(state.home_tab_index)

        # 视频文案
        self.copywriting_count_spin.setValue(state.copywriting_count)
        self.copywriting_concurrent_spin.setValue(state.copywriting_concurrent)

        # 图片识别
        self.image_recognition_count_spin.setValue(state.image_recognition_count)
        self.image_recognition_concurrent_spin.setValue(state.image_recognition_concurrent)
        self._restore_folder_selection(
            self.product_folder_list,
            state.image_recognition_folders,
            self.image_recognition_input_dir
        )

        # 合并文案
        self.merge_copywriting_count_spin.setValue(state.merge_copywriting_count)
        self.merge_copywriting_concurrent_spin.setValue(state.merge_copywriting_concurrent)
        self._restore_folder_selection(
            self.merge_product_folder_list,
            state.merge_copywriting_folders,
            self.image_recognition_output_dir
        )

        # 语音生成
        if state.tts_mode == "liuliang":
            self.tts_liuliang_radio.setChecked(True)
        elif state.tts_mode == "yindao":
            self.tts_yindao_radio.setChecked(True)
        else:
            self.tts_daihuo_radio.setChecked(True)
        self.tts_count_spin.setValue(state.tts_count)
        self.tts_concurrent_spin.setValue(state.tts_concurrent)
        self._restore_folder_selection(
            self.tts_folder_list,
            state.tts_folders,
            self.merge_copywriting_output_dir
        )

        # 图片生成
        self.request_spin.setValue(state.image_request_count)

        # 视频生成
        self.video_count_spin.setValue(state.video_count)
        self.video_concurrent_spin.setValue(state.video_concurrent)

        # 带货视频合成
        self.video_compose_count_spin.setValue(state.compose_count)
        self.video_compose_concurrent_spin.setValue(state.compose_concurrent)
        self.video_compose_clip_duration_min_spin.setValue(state.compose_clip_duration_min)
        self.video_compose_clip_duration_max_spin.setValue(state.compose_clip_duration_max)
        self._set_combo_by_text(self.video_compose_resolution_combo, state.compose_resolution)
        self.video_compose_product_video_count_spin.setValue(state.compose_product_video_count)
        self.video_compose_product_image_count_spin.setValue(state.compose_product_image_count)
        self.video_compose_product_image_duration_min_spin.setValue(state.compose_product_image_duration_min)
        self.video_compose_product_image_duration_max_spin.setValue(state.compose_product_image_duration_max)
        self.video_compose_priority_video_checkbox.setChecked(state.compose_priority_video)
        self.video_compose_overlay_mode_checkbox.setChecked(state.compose_overlay_mode)
        self.video_compose_bgm_slider.setValue(state.compose_bgm_volume)
        self.video_compose_voice_slider.setValue(state.compose_voice_volume)
        self._set_combo_by_data(self.video_compose_effect_combo, state.compose_effect_type)
        self.video_compose_effect_slider.setValue(state.compose_effect_strength)
        self._restore_folder_selection(
            self.video_compose_folder_list,
            state.compose_folders,
            self.tts_output_dir
        )

        # 扒文案
        self.extract_copywriting_concurrent_spin.setValue(state.extract_copywriting_concurrent)
        self._set_combo_by_text(self.extract_copywriting_model_combo, state.extract_copywriting_model)
        self._set_combo_by_text(self.extract_copywriting_device_combo, state.extract_copywriting_device)

        # 字幕生成方式
        self._set_combo_by_text(self.tts_local_model_combo, state.tts_local_model)
        self._set_combo_by_text(self.tts_local_device_combo, state.tts_local_device)
        self._restore_subtitle_method_for_mode()

        # 文案改写
        self.rewrite_copywriting_concurrent_spin.setValue(state.rewrite_copywriting_concurrent)
        self.rewrite_copywriting_versions_spin.setValue(state.rewrite_copywriting_versions)

        # 普通视频生成
        self.normal_video_count_spin.setValue(state.normal_video_count)
        self.normal_video_concurrent_spin.setValue(state.normal_video_concurrent)
        self.normal_video_clip_duration_min_spin.setValue(state.normal_video_clip_duration_min)
        self.normal_video_clip_duration_max_spin.setValue(state.normal_video_clip_duration_max)
        self._set_combo_by_text(self.normal_video_resolution_combo, state.normal_video_resolution)
        self.normal_video_bgm_slider.setValue(state.normal_video_bgm_volume)
        self.normal_video_voice_slider.setValue(state.normal_video_voice_volume)
        self.normal_video_liuliang_check.setChecked(state.normal_video_liuliang_checked)
        self.normal_video_yindao_check.setChecked(state.normal_video_yindao_checked)
        self.normal_video_chuchuang_check.setChecked(state.normal_video_chuchuang_checked)
        self.normal_video_chuchuang_duration_spin.setValue(state.normal_video_chuchuang_duration)
        self._set_combo_by_text(self.normal_video_chuchuang_material_combo, state.normal_video_chuchuang_material_type)

    def _restore_folder_selection(self, list_widget, saved_folders, base_dir):
        """Restore folder selection, validating existence"""
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            folder_name = item.text()
            folder_path = os.path.join(base_dir, folder_name)
            if folder_name in saved_folders and os.path.exists(folder_path):
                item.setSelected(True)

    def _set_combo_by_data(self, combo, data_value):
        """Set combo box selection by data value"""
        for i in range(combo.count()):
            if combo.itemData(i) == data_value:
                combo.setCurrentIndex(i)
                return

    def _set_combo_by_text(self, combo, text_value):
        """Set combo box selection by text value"""
        index = combo.findText(text_value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _update_video_image_count(self):
        """Update the video image count label"""
        image_dir = os.path.join(self.project_dir, "input", "视频图片素材文件夹")
        if os.path.exists(image_dir):
            images = [f for f in os.listdir(image_dir)
                      if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
            count = len(images)
        else:
            count = 0
        self.video_image_info_label.setText(f"图片素材: 当前文件夹有 {count} 张图片")

    def _get_video_images(self) -> list:
        """Get list of image paths from video image folder"""
        image_dir = os.path.join(self.project_dir, "input", "视频图片素材文件夹")
        if not os.path.exists(image_dir):
            return []
        images = sorted([f for f in os.listdir(image_dir)
                         if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))])
        return [os.path.join(image_dir, img) for img in images]

    def _load_video_templates(self):
        """Load templates into video combo box"""
        self.video_template_combo.blockSignals(True)
        self.video_template_combo.clear()
        self.video_template_combo.addItem("-- 选择模板 --", None)
        for template in self.config.templates:
            self.video_template_combo.addItem(template.name, template.content)
        self.video_template_combo.blockSignals(False)

    def _on_video_template_selected(self, index: int):
        """Fill prompt when template is selected"""
        if index <= 0:
            return
        content = self.video_template_combo.itemData(index)
        if content:
            self.video_prompt_input.setPlainText(content)

    def _on_video_save_template(self):
        """Save current video prompt as template"""
        from ..models.config import PromptTemplate

        prompt = self.video_prompt_input.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "提示", "请先输入提示词")
            return

        name, ok = QInputDialog.getText(self, "保存模板", "请输入模板名称:")
        if not ok or not name.strip():
            return

        name = name.strip()

        for i, template in enumerate(self.config.templates):
            if template.name == name:
                reply = QMessageBox.question(
                    self, "确认",
                    f"模板 '{name}' 已存在，是否覆盖？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.config.templates[i] = PromptTemplate(name=name, content=prompt)
                    self.config.save()
                    self._load_templates()
                    self._load_video_templates()
                    QMessageBox.information(self, "成功", f"模板 '{name}' 已更新")
                return

        self.config.templates.append(PromptTemplate(name=name, content=prompt))
        self.config.save()
        self._load_templates()
        self._load_video_templates()
        QMessageBox.information(self, "成功", f"模板 '{name}' 已保存")

    def _on_video_delete_template(self):
        """Delete selected video template"""
        index = self.video_template_combo.currentIndex()
        if index <= 0:
            QMessageBox.warning(self, "提示", "请先选择要删除的模板")
            return

        name = self.video_template_combo.currentText()
        reply = QMessageBox.question(
            self, "确认",
            f"确定要删除模板 '{name}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.config.templates = [t for t in self.config.templates if t.name != name]
        self.config.save()
        self._load_templates()
        self._load_video_templates()
        QMessageBox.information(self, "成功", f"模板 '{name}' 已删除")

    def _video_log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

        color_map = {
            "info": "#00ff00",
            "warning": "#ffff00",
            "error": "#ff0000",
            "success": "#00ff00",
        }
        color = color_map.get(level, "#00ff00")

        html = f'<span style="color: #888888;">[{timestamp}]</span> '
        html += f'<span style="color: {color};">{message}</span>'
        self.video_log_area.append(html)

        cursor = self.video_log_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.video_log_area.setTextCursor(cursor)

    def _update_video_progress(self, progress: VideoTaskProgress):
        if progress.total_tasks > 0:
            # 已完成任务的进度 + 当前任务的进度
            completed_percent = progress.completed_tasks / progress.total_tasks * 100
            current_task_percent = progress.current_task_progress / progress.total_tasks
            total_percent = int(completed_percent + current_task_percent)
            self.video_progress_bar.setValue(min(total_percent, 100))

        self.video_stats_label.setText(
            f"提交: {progress.submitted_tasks}/{progress.total_tasks}  "
            f"完成: {progress.completed_tasks}/{progress.total_tasks}  "
            f"下载: {progress.downloaded_videos}/{progress.total_tasks}"
        )

        self.video_status_text.setText(
            f"运行中 - 提交: {progress.submitted_tasks}/{progress.total_tasks}"
        )

    def _set_video_buttons_state(self, state: str):
        if state == "idle":
            self.video_start_btn.setEnabled(True)
            self.video_pause_btn.setEnabled(False)
            self.video_resume_btn.setEnabled(False)
            self.video_stop_btn.setEnabled(False)
            self.video_prompt_input.setEnabled(True)
            self.video_count_spin.setEnabled(True)
            self.video_concurrent_spin.setEnabled(True)
            self.video_status_text.setText("没有运行项目...")
        elif state == "running":
            self.video_start_btn.setEnabled(False)
            self.video_pause_btn.setEnabled(True)
            self.video_resume_btn.setEnabled(False)
            self.video_stop_btn.setEnabled(True)
            self.video_prompt_input.setEnabled(False)
            self.video_count_spin.setEnabled(False)
            self.video_concurrent_spin.setEnabled(False)
        elif state == "paused":
            self.video_start_btn.setEnabled(False)
            self.video_pause_btn.setEnabled(False)
            self.video_resume_btn.setEnabled(True)
            self.video_stop_btn.setEnabled(True)
            self.video_status_text.setText("已暂停")

    def _on_video_start(self):
        self._update_video_image_count()

        prompt = self.video_prompt_input.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "提示", "请输入提示词")
            return

        if not self.config.video_api.api_key:
            QMessageBox.warning(self, "提示", "请先在设置页面配置视频 API Key")
            return

        image_paths = self._get_video_images()
        if not image_paths:
            QMessageBox.warning(self, "提示", "视频图片素材文件夹中没有图片")
            return

        request_count = self.video_count_spin.value()
        if request_count > len(image_paths):
            QMessageBox.warning(
                self, "错误",
                f"设置的数量 ({request_count}) 超过文件夹中的图片数量 ({len(image_paths)})"
            )
            return

        selected_images = image_paths[:request_count]
        max_concurrent = self.video_concurrent_spin.value()

        self.video_log_area.clear()
        self.video_progress_bar.setValue(0)
        self.video_stats_label.setText("提交: 0/0  完成: 0/0  下载: 0/0")

        api_client = VideoAPIClient(
            base_url=self.config.video_api.base_url,
            api_key=self.config.video_api.api_key,
            model=self.config.video_api.model,
            seconds=self.config.video_api.seconds,
            size=self.config.video_api.size,
            watermark=getattr(self.config.video_api, 'watermark', 'false'),
        )

        downloader = VideoDownloader(self.video_save_dir)

        self.video_task_manager = VideoTaskManager(
            api_client=api_client,
            downloader=downloader,
            max_concurrent=max_concurrent,
            poll_interval=5,
            recycle_dir=self.recycle_dir,
        )

        self.video_start_time = time.time()

        self.video_worker = VideoAsyncWorker(self.video_task_manager, selected_images, prompt)
        self.video_worker.log_signal.connect(self._video_log)
        self.video_worker.progress_signal.connect(self._update_video_progress)
        self.video_worker.finished_signal.connect(self._on_video_task_finished)
        self.video_worker.start()

        self._set_video_buttons_state("running")
        self._video_log(f"开始视频生成任务: {request_count} 个任务, 并发数: {max_concurrent}", "info")

    def _on_video_pause(self):
        if self.video_task_manager:
            self.video_task_manager.pause()
            self._set_video_buttons_state("paused")
            self._video_log("任务已暂停", "warning")

    def _on_video_resume(self):
        if self.video_task_manager:
            self.video_task_manager.resume()
            self._set_video_buttons_state("running")
            self._video_log("任务已继续", "info")

    def _on_video_stop(self):
        if self.video_task_manager:
            self.video_task_manager.stop()
            self._video_log("正在停止任务...", "warning")

    def _on_video_task_finished(self, progress: VideoTaskProgress):
        self._set_video_buttons_state("idle")

        if progress:
            self._video_log(
                f"任务完成! 成功: {progress.downloaded_videos}, "
                f"失败: {progress.failed_tasks}",
                "success"
            )
        else:
            self._video_log("任务异常结束", "error")

        self.video_task_manager = None
        self.video_worker = None

    # Copywriting methods
    def _load_copywriting_templates(self):
        """Load templates into copywriting combo box"""
        self.copywriting_template_combo.blockSignals(True)
        self.copywriting_template_combo.clear()
        self.copywriting_template_combo.addItem("-- 选择模板 --", None)
        for template in self.config.copywriting_templates:
            self.copywriting_template_combo.addItem(template.name, template.content)
        self.copywriting_template_combo.blockSignals(False)

    def _on_copywriting_template_selected(self, index: int):
        """Fill prompt when template is selected"""
        if index <= 0:
            return
        content = self.copywriting_template_combo.itemData(index)
        if content:
            self.copywriting_prompt_input.setPlainText(content)

    def _on_copywriting_save_template(self):
        """Save current copywriting prompt as template"""
        from ..models.config import PromptTemplate

        prompt = self.copywriting_prompt_input.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "提示", "请先输入提示词")
            return

        name, ok = QInputDialog.getText(self, "保存模板", "请输入模板名称:")
        if not ok or not name.strip():
            return

        name = name.strip()

        for i, template in enumerate(self.config.copywriting_templates):
            if template.name == name:
                reply = QMessageBox.question(
                    self, "确认",
                    f"模板 '{name}' 已存在，是否覆盖？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.config.copywriting_templates[i] = PromptTemplate(name=name, content=prompt)
                    self.config.save()
                    self._load_copywriting_templates()
                    QMessageBox.information(self, "成功", f"模板 '{name}' 已更新")
                return

        self.config.copywriting_templates.append(PromptTemplate(name=name, content=prompt))
        self.config.save()
        self._load_copywriting_templates()
        QMessageBox.information(self, "成功", f"模板 '{name}' 已保存")

    def _on_copywriting_delete_template(self):
        """Delete selected copywriting template"""
        index = self.copywriting_template_combo.currentIndex()
        if index <= 0:
            QMessageBox.warning(self, "提示", "请先选择要删除的模板")
            return

        name = self.copywriting_template_combo.currentText()
        reply = QMessageBox.question(
            self, "确认",
            f"确定要删除模板 '{name}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.config.copywriting_templates = [t for t in self.config.copywriting_templates if t.name != name]
        self.config.save()
        self._load_copywriting_templates()
        QMessageBox.information(self, "成功", f"模板 '{name}' 已删除")

    def _copywriting_log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

        color_map = {
            "info": "#00ff00",
            "warning": "#ffff00",
            "error": "#ff0000",
            "success": "#00ff00",
        }
        color = color_map.get(level, "#00ff00")

        html = f'<span style="color: #888888;">[{timestamp}]</span> '
        html += f'<span style="color: {color};">{message}</span>'
        self.copywriting_log_area.append(html)

        cursor = self.copywriting_log_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.copywriting_log_area.setTextCursor(cursor)

    def _update_copywriting_progress(self, progress: CopywritingTaskProgress):
        if progress.total_tasks > 0:
            percent = int(progress.completed_tasks / progress.total_tasks * 100)
            self.copywriting_progress_bar.setValue(percent)

        self.copywriting_stats_label.setText(
            f"已完成: {progress.completed_tasks}/{progress.total_tasks}  "
            f"失败: {progress.failed_tasks}  "
            f"已保存: {progress.saved_files}"
        )

        self.copywriting_status_text.setText(
            f"运行中 - 完成: {progress.completed_tasks}/{progress.total_tasks}"
        )

    def _set_copywriting_buttons_state(self, state: str):
        if state == "idle":
            self.copywriting_start_btn.setEnabled(True)
            self.copywriting_pause_btn.setEnabled(False)
            self.copywriting_resume_btn.setEnabled(False)
            self.copywriting_stop_btn.setEnabled(False)
            self.copywriting_prompt_input.setEnabled(True)
            self.copywriting_count_spin.setEnabled(True)
            self.copywriting_concurrent_spin.setEnabled(True)
            self.copywriting_status_text.setText("没有运行项目...")
        elif state == "running":
            self.copywriting_start_btn.setEnabled(False)
            self.copywriting_pause_btn.setEnabled(True)
            self.copywriting_resume_btn.setEnabled(False)
            self.copywriting_stop_btn.setEnabled(True)
            self.copywriting_prompt_input.setEnabled(False)
            self.copywriting_count_spin.setEnabled(False)
            self.copywriting_concurrent_spin.setEnabled(False)
        elif state == "paused":
            self.copywriting_start_btn.setEnabled(False)
            self.copywriting_pause_btn.setEnabled(False)
            self.copywriting_resume_btn.setEnabled(True)
            self.copywriting_stop_btn.setEnabled(True)
            self.copywriting_status_text.setText("已暂停")

    def _on_copywriting_start(self):
        prompt = self.copywriting_prompt_input.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "提示", "请输入提示词")
            return

        if not self.config.copywriting_api.api_key:
            QMessageBox.warning(self, "提示", "请先在设置页面配置视频文案 API Key")
            return

        request_count = self.copywriting_count_spin.value()
        max_concurrent = self.copywriting_concurrent_spin.value()

        self.copywriting_log_area.clear()
        self.copywriting_progress_bar.setValue(0)
        self.copywriting_stats_label.setText("已完成: 0/0  失败: 0  已保存: 0")

        api_client = CopywritingAPIClient(
            base_url=self.config.copywriting_api.base_url,
            api_key=self.config.copywriting_api.api_key,
            model=self.config.copywriting_api.model,
        )

        self.copywriting_task_manager = CopywritingTaskManager(
            api_client=api_client,
            output_dir=self.copywriting_save_dir,
            max_concurrent=max_concurrent,
            max_retries=self.config.copywriting_api.max_retries,
        )

        self.copywriting_start_time = time.time()

        self.copywriting_worker = CopywritingAsyncWorker(
            self.copywriting_task_manager, prompt, request_count
        )
        self.copywriting_worker.log_signal.connect(self._copywriting_log)
        self.copywriting_worker.progress_signal.connect(self._update_copywriting_progress)
        self.copywriting_worker.finished_signal.connect(self._on_copywriting_task_finished)
        self.copywriting_worker.start()

        self._set_copywriting_buttons_state("running")
        self._copywriting_log(f"开始文案生成任务: {request_count} 次请求, 并发数: {max_concurrent}", "info")

    def _on_copywriting_pause(self):
        if self.copywriting_task_manager:
            self.copywriting_task_manager.pause()
            self._set_copywriting_buttons_state("paused")
            self._copywriting_log("任务已暂停", "warning")

    def _on_copywriting_resume(self):
        if self.copywriting_task_manager:
            self.copywriting_task_manager.resume()
            self._set_copywriting_buttons_state("running")
            self._copywriting_log("任务已继续", "info")

    def _on_copywriting_stop(self):
        if self.copywriting_task_manager:
            self.copywriting_task_manager.stop()
            self._copywriting_log("正在停止任务...", "warning")

    def _on_copywriting_task_finished(self, progress: CopywritingTaskProgress):
        self._set_copywriting_buttons_state("idle")

        if progress:
            self._copywriting_log(
                f"任务完成! 成功: {progress.saved_files}, "
                f"失败: {progress.failed_tasks}",
                "success"
            )
        else:
            self._copywriting_log("任务异常结束", "error")

        self.copywriting_task_manager = None
        self.copywriting_worker = None

    def _load_last_copywriting_prompt(self):
        """Load last copywriting prompt on startup"""
        if self.config.last_copywriting_prompt:
            self.copywriting_prompt_input.setPlainText(self.config.last_copywriting_prompt)

    def save_current_copywriting_prompt(self):
        """Save current copywriting prompt for next startup"""
        self.config.last_copywriting_prompt = self.copywriting_prompt_input.toPlainText().strip()

    # Rewrite Copywriting methods
    def _on_rewrite_copywriting_start(self):
        prompt = self.rewrite_copywriting_prompt_input.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "提示", "请输入提示词")
            return

        if not self.config.rewrite_copywriting_api.api_key:
            QMessageBox.warning(self, "提示", "请先在设置页面配置文案改写 API Key")
            return

        # Check if {content} placeholder exists
        if "{content}" not in prompt:
            reply = QMessageBox.question(
                self,
                "提示",
                "提示词中没有 {content} 变量，原文案内容将不会被包含在请求中。是否继续？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        max_concurrent = self.rewrite_copywriting_concurrent_spin.value()
        versions_per_file = self.rewrite_copywriting_versions_spin.value()

        self.rewrite_copywriting_log_area.clear()
        self.rewrite_copywriting_progress_bar.setValue(0)
        self.rewrite_copywriting_stats_label.setText("已完成: 0/0  失败: 0  已保存: 0")

        api_client = CopywritingAPIClient(
            base_url=self.config.rewrite_copywriting_api.base_url,
            api_key=self.config.rewrite_copywriting_api.api_key,
            model=self.config.rewrite_copywriting_api.model,
        )

        self.rewrite_copywriting_task_manager = RewriteCopywritingTaskManager(
            api_client=api_client,
            input_dir=self.extract_copywriting_output_dir,
            output_dir=self.liuliang_copywriting_dir,
            max_concurrent=max_concurrent,
            max_retries=self.config.rewrite_copywriting_api.max_retries,
            versions_per_file=versions_per_file,
        )

        self.rewrite_copywriting_start_time = time.time()

        self.rewrite_copywriting_worker = RewriteCopywritingAsyncWorker(
            self.rewrite_copywriting_task_manager, prompt
        )
        self.rewrite_copywriting_worker.log_signal.connect(self._rewrite_copywriting_log)
        self.rewrite_copywriting_worker.progress_signal.connect(self._update_rewrite_copywriting_progress)
        self.rewrite_copywriting_worker.finished_signal.connect(self._on_rewrite_copywriting_task_finished)
        self.rewrite_copywriting_worker.start()

        self._set_rewrite_copywriting_buttons_state("running")
        self._rewrite_copywriting_log(f"开始文案改写任务, 并发数: {max_concurrent}, 版本数: {versions_per_file}", "info")

    def _on_rewrite_copywriting_pause(self):
        if self.rewrite_copywriting_task_manager:
            self.rewrite_copywriting_task_manager.pause()
            self._set_rewrite_copywriting_buttons_state("paused")
            self._rewrite_copywriting_log("任务已暂停", "warning")

    def _on_rewrite_copywriting_resume(self):
        if self.rewrite_copywriting_task_manager:
            self.rewrite_copywriting_task_manager.resume()
            self._set_rewrite_copywriting_buttons_state("running")
            self._rewrite_copywriting_log("任务已继续", "info")

    def _on_rewrite_copywriting_stop(self):
        if self.rewrite_copywriting_task_manager:
            self.rewrite_copywriting_task_manager.stop()
            self._rewrite_copywriting_log("正在停止任务...", "warning")

    def _on_rewrite_copywriting_task_finished(self, progress: RewriteCopywritingTaskProgress):
        self._set_rewrite_copywriting_buttons_state("idle")

        if progress:
            self._rewrite_copywriting_log(
                f"任务完成! 成功: {progress.saved_files}, "
                f"失败: {progress.failed_tasks}",
                "success"
            )
        else:
            self._rewrite_copywriting_log("任务异常结束", "error")

        self.rewrite_copywriting_task_manager = None
        self.rewrite_copywriting_worker = None

    def _rewrite_copywriting_log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        color_map = {
            "info": "#00ff00",
            "warning": "#ffff00",
            "error": "#ff6666",
            "success": "#66ff66",
        }
        color = color_map.get(level, "#00ff00")
        self.rewrite_copywriting_log_area.append(
            f'<span style="color: {color}">[{timestamp}] {message}</span>'
        )
        cursor = self.rewrite_copywriting_log_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.rewrite_copywriting_log_area.setTextCursor(cursor)

    def _update_rewrite_copywriting_progress(self, progress: RewriteCopywritingTaskProgress):
        if progress.total_tasks > 0:
            percent = int(progress.completed_tasks / progress.total_tasks * 100)
            self.rewrite_copywriting_progress_bar.setValue(percent)

        self.rewrite_copywriting_stats_label.setText(
            f"已完成: {progress.completed_tasks}/{progress.total_tasks}  "
            f"失败: {progress.failed_tasks}  已保存: {progress.saved_files}"
        )

        if progress.current_task:
            elapsed = time.time() - self.rewrite_copywriting_start_time
            self.rewrite_copywriting_status_text.setText(
                f"正在处理: {progress.current_task} | 耗时: {elapsed:.1f}s"
            )

    def _set_rewrite_copywriting_buttons_state(self, state: str):
        if state == "idle":
            self.rewrite_copywriting_start_btn.setEnabled(True)
            self.rewrite_copywriting_pause_btn.setEnabled(False)
            self.rewrite_copywriting_resume_btn.setEnabled(False)
            self.rewrite_copywriting_stop_btn.setEnabled(False)
            self.rewrite_copywriting_status_text.setText("没有运行项目...")
        elif state == "running":
            self.rewrite_copywriting_start_btn.setEnabled(False)
            self.rewrite_copywriting_pause_btn.setEnabled(True)
            self.rewrite_copywriting_resume_btn.setEnabled(False)
            self.rewrite_copywriting_stop_btn.setEnabled(True)
            self.rewrite_copywriting_status_text.setText("正在运行...")
        elif state == "paused":
            self.rewrite_copywriting_start_btn.setEnabled(False)
            self.rewrite_copywriting_pause_btn.setEnabled(False)
            self.rewrite_copywriting_resume_btn.setEnabled(True)
            self.rewrite_copywriting_stop_btn.setEnabled(True)
            self.rewrite_copywriting_status_text.setText("已暂停")

    def _load_rewrite_copywriting_templates(self):
        """Load rewrite copywriting templates into combo box"""
        self.rewrite_copywriting_template_combo.clear()
        self.rewrite_copywriting_template_combo.addItem("-- 选择模板 --")
        for template in self.config.rewrite_copywriting_templates:
            self.rewrite_copywriting_template_combo.addItem(template.name)

    def _on_rewrite_copywriting_template_selected(self, index: int):
        if index <= 0:
            return
        template_index = index - 1
        if template_index < len(self.config.rewrite_copywriting_templates):
            template = self.config.rewrite_copywriting_templates[template_index]
            self.rewrite_copywriting_prompt_input.setPlainText(template.content)

    def _on_rewrite_copywriting_save_template(self):
        prompt = self.rewrite_copywriting_prompt_input.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "提示", "请先输入提示词")
            return

        name, ok = QInputDialog.getText(self, "保存模板", "请输入模板名称:")
        if ok and name:
            from ..models.config import PromptTemplate
            # Check if template with same name exists
            for i, t in enumerate(self.config.rewrite_copywriting_templates):
                if t.name == name:
                    self.config.rewrite_copywriting_templates[i] = PromptTemplate(name=name, content=prompt)
                    self.config.save()
                    self._load_rewrite_copywriting_templates()
                    QMessageBox.information(self, "成功", "模板已更新")
                    return

            self.config.rewrite_copywriting_templates.append(PromptTemplate(name=name, content=prompt))
            self.config.save()
            self._load_rewrite_copywriting_templates()
            QMessageBox.information(self, "成功", "模板已保存")

    def _on_rewrite_copywriting_delete_template(self):
        index = self.rewrite_copywriting_template_combo.currentIndex()
        if index <= 0:
            QMessageBox.warning(self, "提示", "请先选择要删除的模板")
            return

        template_index = index - 1
        if template_index < len(self.config.rewrite_copywriting_templates):
            template = self.config.rewrite_copywriting_templates[template_index]
            reply = QMessageBox.question(
                self,
                "确认删除",
                f"确定要删除模板 '{template.name}' 吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                del self.config.rewrite_copywriting_templates[template_index]
                self.config.save()
                self._load_rewrite_copywriting_templates()
                QMessageBox.information(self, "成功", "模板已删除")

    def _load_last_rewrite_copywriting_prompt(self):
        """Load last rewrite copywriting prompt on startup"""
        if self.config.last_rewrite_copywriting_prompt:
            self.rewrite_copywriting_prompt_input.setPlainText(self.config.last_rewrite_copywriting_prompt)

    def save_current_rewrite_copywriting_prompt(self):
        """Save current rewrite copywriting prompt for next startup"""
        self.config.last_rewrite_copywriting_prompt = self.rewrite_copywriting_prompt_input.toPlainText().strip()

    def _on_yindao_rewrite_copywriting_start(self):
        prompt = self.yindao_rewrite_copywriting_prompt_input.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "提示", "请输入提示词")
            return

        if not self.config.rewrite_copywriting_api.api_key:
            QMessageBox.warning(self, "提示", "请先在设置页面配置文案改写 API Key")
            return

        if "{content}" not in prompt:
            reply = QMessageBox.question(
                self,
                "提示",
                "提示词中没有 {content} 变量，原文案内容将不会被包含在请求中。是否继续？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        max_concurrent = self.yindao_rewrite_copywriting_concurrent_spin.value()
        versions_per_file = self.yindao_rewrite_copywriting_versions_spin.value()

        self.yindao_rewrite_copywriting_log_area.clear()
        self.yindao_rewrite_copywriting_progress_bar.setValue(0)
        self.yindao_rewrite_copywriting_stats_label.setText("已完成: 0/0  失败: 0  已保存: 0")

        api_client = CopywritingAPIClient(
            base_url=self.config.rewrite_copywriting_api.base_url,
            api_key=self.config.rewrite_copywriting_api.api_key,
            model=self.config.rewrite_copywriting_api.model,
        )

        self.yindao_rewrite_copywriting_task_manager = RewriteCopywritingTaskManager(
            api_client=api_client,
            input_dir=self.extract_copywriting_output_dir,
            output_dir=self.yindao_copywriting_dir,
            max_concurrent=max_concurrent,
            max_retries=self.config.rewrite_copywriting_api.max_retries,
            versions_per_file=versions_per_file,
        )

        self.yindao_rewrite_copywriting_start_time = time.time()

        self.yindao_rewrite_copywriting_worker = YindaoRewriteCopywritingAsyncWorker(
            self.yindao_rewrite_copywriting_task_manager, prompt
        )
        self.yindao_rewrite_copywriting_worker.log_signal.connect(self._yindao_rewrite_copywriting_log)
        self.yindao_rewrite_copywriting_worker.progress_signal.connect(self._update_yindao_rewrite_copywriting_progress)
        self.yindao_rewrite_copywriting_worker.finished_signal.connect(self._on_yindao_rewrite_copywriting_task_finished)
        self.yindao_rewrite_copywriting_worker.start()

        self._set_yindao_rewrite_copywriting_buttons_state("running")
        self._yindao_rewrite_copywriting_log(f"开始文案改写任务, 并发数: {max_concurrent}, 版本数: {versions_per_file}", "info")

    def _on_yindao_rewrite_copywriting_pause(self):
        if self.yindao_rewrite_copywriting_task_manager:
            self.yindao_rewrite_copywriting_task_manager.pause()
            self._set_yindao_rewrite_copywriting_buttons_state("paused")
            self._yindao_rewrite_copywriting_log("任务已暂停", "warning")

    def _on_yindao_rewrite_copywriting_resume(self):
        if self.yindao_rewrite_copywriting_task_manager:
            self.yindao_rewrite_copywriting_task_manager.resume()
            self._set_yindao_rewrite_copywriting_buttons_state("running")
            self._yindao_rewrite_copywriting_log("任务已继续", "info")

    def _on_yindao_rewrite_copywriting_stop(self):
        if self.yindao_rewrite_copywriting_task_manager:
            self.yindao_rewrite_copywriting_task_manager.stop()
            self._yindao_rewrite_copywriting_log("正在停止任务...", "warning")

    def _on_yindao_rewrite_copywriting_task_finished(self, progress: RewriteCopywritingTaskProgress):
        self._set_yindao_rewrite_copywriting_buttons_state("idle")

        if progress:
            self._yindao_rewrite_copywriting_log(
                f"任务完成! 成功: {progress.saved_files}, "
                f"失败: {progress.failed_tasks}",
                "success"
            )
        else:
            self._yindao_rewrite_copywriting_log("任务异常结束", "error")

        self.yindao_rewrite_copywriting_task_manager = None
        self.yindao_rewrite_copywriting_worker = None

    def _yindao_rewrite_copywriting_log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        color_map = {
            "info": "#00ff00",
            "warning": "#ffff00",
            "error": "#ff6666",
            "success": "#66ff66",
        }
        color = color_map.get(level, "#00ff00")
        self.yindao_rewrite_copywriting_log_area.append(
            f'<span style="color: {color}">[{timestamp}] {message}</span>'
        )
        cursor = self.yindao_rewrite_copywriting_log_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.yindao_rewrite_copywriting_log_area.setTextCursor(cursor)

    def _update_yindao_rewrite_copywriting_progress(self, progress: RewriteCopywritingTaskProgress):
        if progress.total_tasks > 0:
            percent = int(progress.completed_tasks / progress.total_tasks * 100)
            self.yindao_rewrite_copywriting_progress_bar.setValue(percent)

        self.yindao_rewrite_copywriting_stats_label.setText(
            f"已完成: {progress.completed_tasks}/{progress.total_tasks}  "
            f"失败: {progress.failed_tasks}  已保存: {progress.saved_files}"
        )

        if progress.current_task:
            elapsed = time.time() - self.yindao_rewrite_copywriting_start_time
            self.yindao_rewrite_copywriting_status_text.setText(
                f"正在处理: {progress.current_task} | 耗时: {elapsed:.1f}s"
            )

    def _set_yindao_rewrite_copywriting_buttons_state(self, state: str):
        if state == "idle":
            self.yindao_rewrite_copywriting_start_btn.setEnabled(True)
            self.yindao_rewrite_copywriting_pause_btn.setEnabled(False)
            self.yindao_rewrite_copywriting_resume_btn.setEnabled(False)
            self.yindao_rewrite_copywriting_stop_btn.setEnabled(False)
            self.yindao_rewrite_copywriting_status_text.setText("没有运行项目...")
        elif state == "running":
            self.yindao_rewrite_copywriting_start_btn.setEnabled(False)
            self.yindao_rewrite_copywriting_pause_btn.setEnabled(True)
            self.yindao_rewrite_copywriting_resume_btn.setEnabled(False)
            self.yindao_rewrite_copywriting_stop_btn.setEnabled(True)
            self.yindao_rewrite_copywriting_status_text.setText("正在运行...")
        elif state == "paused":
            self.yindao_rewrite_copywriting_start_btn.setEnabled(False)
            self.yindao_rewrite_copywriting_pause_btn.setEnabled(False)
            self.yindao_rewrite_copywriting_resume_btn.setEnabled(True)
            self.yindao_rewrite_copywriting_stop_btn.setEnabled(True)
            self.yindao_rewrite_copywriting_status_text.setText("已暂停")

    def _load_yindao_rewrite_copywriting_templates(self):
        """Load yindao rewrite copywriting templates into combo box"""
        self.yindao_rewrite_copywriting_template_combo.clear()
        self.yindao_rewrite_copywriting_template_combo.addItem("-- 选择模板 --")
        for template in self.config.rewrite_copywriting_templates:
            self.yindao_rewrite_copywriting_template_combo.addItem(template.name)

    def _on_yindao_rewrite_copywriting_template_selected(self, index: int):
        if index <= 0:
            return
        template_index = index - 1
        if template_index < len(self.config.rewrite_copywriting_templates):
            template = self.config.rewrite_copywriting_templates[template_index]
            self.yindao_rewrite_copywriting_prompt_input.setPlainText(template.content)

    def _on_yindao_rewrite_copywriting_save_template(self):
        prompt = self.yindao_rewrite_copywriting_prompt_input.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "提示", "请先输入提示词")
            return

        name, ok = QInputDialog.getText(self, "保存模板", "请输入模板名称:")
        if ok and name:
            from ..models.config import PromptTemplate
            for i, t in enumerate(self.config.rewrite_copywriting_templates):
                if t.name == name:
                    self.config.rewrite_copywriting_templates[i] = PromptTemplate(name=name, content=prompt)
                    self.config.save()
                    self._load_yindao_rewrite_copywriting_templates()
                    QMessageBox.information(self, "成功", "模板已更新")
                    return

            self.config.rewrite_copywriting_templates.append(PromptTemplate(name=name, content=prompt))
            self.config.save()
            self._load_yindao_rewrite_copywriting_templates()
            QMessageBox.information(self, "成功", "模板已保存")

    def _on_yindao_rewrite_copywriting_delete_template(self):
        index = self.yindao_rewrite_copywriting_template_combo.currentIndex()
        if index <= 0:
            QMessageBox.warning(self, "提示", "请先选择要删除的模板")
            return

        template_index = index - 1
        if template_index < len(self.config.rewrite_copywriting_templates):
            template = self.config.rewrite_copywriting_templates[template_index]
            reply = QMessageBox.question(
                self,
                "确认删除",
                f"确定要删除模板 '{template.name}' 吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                del self.config.rewrite_copywriting_templates[template_index]
                self.config.save()
                self._load_yindao_rewrite_copywriting_templates()
                QMessageBox.information(self, "成功", "模板已删除")
    def _create_image_recognition_toolbar(self) -> QFrame:
        toolbar = QFrame()
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)

        label_style = "color: #333333; background: transparent; border: none;"
        spin_style = """
            QSpinBox {
                border: 1px solid #d0d0d0;
                padding: 1px 4px;
                background: #ffffff;
                min-width: 70px;
            }
        """

        count_label = QLabel("生成数量:")
        count_label.setFont(QFont("Microsoft YaHei", 9))
        count_label.setStyleSheet(label_style)
        self.image_recognition_count_spin = QSpinBox()
        self.image_recognition_count_spin.setRange(1, 100)
        self.image_recognition_count_spin.setValue(1)
        self.image_recognition_count_spin.setStyleSheet(spin_style)

        concurrent_label = QLabel("并发数:")
        concurrent_label.setFont(QFont("Microsoft YaHei", 9))
        concurrent_label.setStyleSheet(label_style)
        self.image_recognition_concurrent_spin = QSpinBox()
        self.image_recognition_concurrent_spin.setRange(1, 10)
        self.image_recognition_concurrent_spin.setValue(3)
        self.image_recognition_concurrent_spin.setStyleSheet(spin_style)

        layout.addWidget(count_label)
        layout.addWidget(self.image_recognition_count_spin)
        layout.addWidget(concurrent_label)
        layout.addWidget(self.image_recognition_concurrent_spin)

        layout.addStretch()

        btn_style = """
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e8f4fc;
            }
            QPushButton:disabled {
                color: #999999;
                background-color: #f0f0f0;
            }
        """

        primary_btn_style = """
            QPushButton {
                color: #ffffff;
                background-color: #0066cc;
                border: 1px solid #0055aa;
                padding: 2px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0055aa;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                border-color: #bbbbbb;
            }
        """

        stop_btn_style = """
            QPushButton {
                color: #cc0000;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #ffeeee;
            }
            QPushButton:disabled {
                color: #999999;
                background-color: #f0f0f0;
            }
        """

        self.image_recognition_refresh_btn = QPushButton("刷新")
        self.image_recognition_refresh_btn.setFont(QFont("Microsoft YaHei", 9))
        self.image_recognition_refresh_btn.setStyleSheet(btn_style)
        self.image_recognition_refresh_btn.clicked.connect(self._refresh_product_folders)

        self.image_recognition_start_btn = QPushButton("开始识别")
        self.image_recognition_start_btn.setFont(QFont("Microsoft YaHei", 9))
        self.image_recognition_start_btn.setStyleSheet(primary_btn_style)
        self.image_recognition_start_btn.clicked.connect(self._on_image_recognition_start)

        self.image_recognition_pause_btn = QPushButton("暂停")
        self.image_recognition_pause_btn.setFont(QFont("Microsoft YaHei", 9))
        self.image_recognition_pause_btn.setStyleSheet(btn_style)
        self.image_recognition_pause_btn.setEnabled(False)
        self.image_recognition_pause_btn.clicked.connect(self._on_image_recognition_pause)

        self.image_recognition_resume_btn = QPushButton("继续")
        self.image_recognition_resume_btn.setFont(QFont("Microsoft YaHei", 9))
        self.image_recognition_resume_btn.setStyleSheet(btn_style)
        self.image_recognition_resume_btn.setEnabled(False)
        self.image_recognition_resume_btn.clicked.connect(self._on_image_recognition_resume)

        self.image_recognition_stop_btn = QPushButton("停止")
        self.image_recognition_stop_btn.setFont(QFont("Microsoft YaHei", 9))
        self.image_recognition_stop_btn.setStyleSheet(stop_btn_style)
        self.image_recognition_stop_btn.setEnabled(False)
        self.image_recognition_stop_btn.clicked.connect(self._on_image_recognition_stop)

        layout.addWidget(self.image_recognition_refresh_btn)
        layout.addWidget(self.image_recognition_start_btn)
        layout.addWidget(self.image_recognition_pause_btn)
        layout.addWidget(self.image_recognition_resume_btn)
        layout.addWidget(self.image_recognition_stop_btn)

        return toolbar

    def _create_image_recognition_content_area(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame#image_recognition_content_frame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)
        frame.setObjectName("image_recognition_content_frame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        # Folder selection area
        folder_label = QLabel("商品文件夹选择")
        folder_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        folder_label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(folder_label)

        self.product_folder_list = QListWidget()
        self.product_folder_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.product_folder_list.setMinimumHeight(80)
        self.product_folder_list.setMaximumHeight(150)
        self.product_folder_list.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(self.product_folder_list)

        # Prompt area
        prompt_label = QLabel("提示词")
        prompt_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        prompt_label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(prompt_label)

        # Template selection area
        template_layout = QHBoxLayout()
        template_layout.setSpacing(3)

        self.image_recognition_template_combo = QComboBox()
        self.image_recognition_template_combo.setMinimumWidth(200)
        self.image_recognition_template_combo.setFont(QFont("Microsoft YaHei", 9))
        self.image_recognition_template_combo.currentIndexChanged.connect(
            self._on_image_recognition_template_selected
        )
        template_layout.addWidget(self.image_recognition_template_combo)

        btn_style = """
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e8f4fc;
            }
        """

        self.image_recognition_save_template_btn = QPushButton("保存为模板")
        self.image_recognition_save_template_btn.setFont(QFont("Microsoft YaHei", 9))
        self.image_recognition_save_template_btn.setStyleSheet(btn_style)
        self.image_recognition_save_template_btn.clicked.connect(
            self._on_image_recognition_save_template
        )
        template_layout.addWidget(self.image_recognition_save_template_btn)

        self.image_recognition_delete_template_btn = QPushButton("删除模板")
        self.image_recognition_delete_template_btn.setFont(QFont("Microsoft YaHei", 9))
        self.image_recognition_delete_template_btn.setStyleSheet(btn_style)
        self.image_recognition_delete_template_btn.clicked.connect(
            self._on_image_recognition_delete_template
        )
        template_layout.addWidget(self.image_recognition_delete_template_btn)

        template_layout.addStretch()
        layout.addLayout(template_layout)

        self.image_recognition_prompt_input = QTextEdit()
        self.image_recognition_prompt_input.setPlaceholderText("输入图片识别提示词...")
        self.image_recognition_prompt_input.setMinimumHeight(60)
        self.image_recognition_prompt_input.setMaximumHeight(120)
        self.image_recognition_prompt_input.setFont(QFont("Microsoft YaHei", 10))
        self.image_recognition_prompt_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #d0d0d0;
                background-color: #ffffff;
                padding: 5px;
            }
        """)
        layout.addWidget(self.image_recognition_prompt_input)

        # Progress area
        progress_label = QLabel("进度")
        progress_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        progress_label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(progress_label)

        self.image_recognition_progress_bar = QProgressBar()
        self.image_recognition_progress_bar.setMinimum(0)
        self.image_recognition_progress_bar.setMaximum(100)
        self.image_recognition_progress_bar.setValue(0)
        self.image_recognition_progress_bar.setFixedHeight(12)
        self.image_recognition_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #d0d0d0;
                background-color: #f0f0f0;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #0066cc;
            }
        """)
        layout.addWidget(self.image_recognition_progress_bar)

        self.image_recognition_stats_label = QLabel("已完成: 0/0 文件夹  已保存: 0 个文件")
        self.image_recognition_stats_label.setFont(QFont("Microsoft YaHei", 9))
        self.image_recognition_stats_label.setStyleSheet("color: #666666; border: none;")
        layout.addWidget(self.image_recognition_stats_label)

        layout.addStretch()

        # Initialize folder list
        self._refresh_product_folders()

        return frame

    def _create_image_recognition_status_bar(self) -> QFrame:
        frame = QFrame()
        frame.setFixedHeight(18)
        frame.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border: 1px solid #d0d0d0;
            }
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(6, 1, 6, 1)

        self.image_recognition_status_text = QLabel("没有运行项目...")
        self.image_recognition_status_text.setFont(QFont("Microsoft YaHei", 9))
        self.image_recognition_status_text.setStyleSheet(
            "color: #0066cc; border: none; background: transparent;"
        )
        layout.addWidget(self.image_recognition_status_text)

        layout.addStretch()

        return frame

    def _create_image_recognition_log_area(self) -> QFrame:
        frame = QFrame()
        frame.setMinimumHeight(120)
        frame.setMaximumHeight(200)
        frame.setStyleSheet("""
            QFrame#image_recognition_log_frame {
                background-color: #1e1e1e;
                border: 1px solid #333333;
            }
        """)
        frame.setObjectName("image_recognition_log_frame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel(" 日志")
        header.setFixedHeight(14)
        header.setFont(QFont("Microsoft YaHei", 9))
        header.setStyleSheet(
            "color: #888888; background-color: #2d2d2d; border: none; padding-left: 8px;"
        )
        layout.addWidget(header)

        self.image_recognition_log_area = QTextEdit()
        self.image_recognition_log_area.setReadOnly(True)
        self.image_recognition_log_area.setFont(QFont("Consolas", 10))
        self.image_recognition_log_area.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #00ff00;
                border: none;
                padding: 3px;
            }
        """)
        layout.addWidget(self.image_recognition_log_area)

        return frame

    def _refresh_product_folders(self):
        """Refresh the product folder list"""
        self.product_folder_list.clear()

        if not os.path.exists(self.image_recognition_input_dir):
            os.makedirs(self.image_recognition_input_dir, exist_ok=True)
            return

        folders = []
        for name in sorted(os.listdir(self.image_recognition_input_dir)):
            folder_path = os.path.join(self.image_recognition_input_dir, name)
            if os.path.isdir(folder_path):
                folders.append(name)

        for folder in folders:
            item = QListWidgetItem(folder)
            self.product_folder_list.addItem(item)

    def _get_selected_folders(self) -> list:
        """Get list of selected folder names"""
        selected = []
        for item in self.product_folder_list.selectedItems():
            selected.append(item.text())
        return selected

    def _load_image_recognition_templates(self):
        """Load templates into image recognition combo box"""
        self.image_recognition_template_combo.blockSignals(True)
        self.image_recognition_template_combo.clear()
        self.image_recognition_template_combo.addItem("-- 选择模板 --", None)
        for template in self.config.image_recognition_templates:
            self.image_recognition_template_combo.addItem(template.name, template.content)
        self.image_recognition_template_combo.blockSignals(False)

    def _on_image_recognition_template_selected(self, index: int):
        """Fill prompt when template is selected"""
        if index <= 0:
            return
        content = self.image_recognition_template_combo.itemData(index)
        if content:
            self.image_recognition_prompt_input.setPlainText(content)

    def _on_image_recognition_save_template(self):
        """Save current image recognition prompt as template"""
        from ..models.config import PromptTemplate

        prompt = self.image_recognition_prompt_input.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "提示", "请先输入提示词")
            return

        name, ok = QInputDialog.getText(self, "保存模板", "请输入模板名称:")
        if not ok or not name.strip():
            return

        name = name.strip()

        for i, template in enumerate(self.config.image_recognition_templates):
            if template.name == name:
                reply = QMessageBox.question(
                    self, "确认",
                    f"模板 '{name}' 已存在，是否覆盖？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.config.image_recognition_templates[i] = PromptTemplate(
                        name=name, content=prompt
                    )
                    self.config.save()
                    self._load_image_recognition_templates()
                    QMessageBox.information(self, "成功", f"模板 '{name}' 已更新")
                return

        self.config.image_recognition_templates.append(PromptTemplate(name=name, content=prompt))
        self.config.save()
        self._load_image_recognition_templates()
        QMessageBox.information(self, "成功", f"模板 '{name}' 已保存")

    def _on_image_recognition_delete_template(self):
        """Delete selected image recognition template"""
        index = self.image_recognition_template_combo.currentIndex()
        if index <= 0:
            QMessageBox.warning(self, "提示", "请先选择要删除的模板")
            return

        name = self.image_recognition_template_combo.currentText()
        reply = QMessageBox.question(
            self, "确认",
            f"确定要删除模板 '{name}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.config.image_recognition_templates = [
            t for t in self.config.image_recognition_templates if t.name != name
        ]
        self.config.save()
        self._load_image_recognition_templates()
        QMessageBox.information(self, "成功", f"模板 '{name}' 已删除")

    def _image_recognition_log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

        color_map = {
            "info": "#00ff00",
            "warning": "#ffff00",
            "error": "#ff0000",
            "success": "#00ff00",
        }
        color = color_map.get(level, "#00ff00")

        html = f'<span style="color: #888888;">[{timestamp}]</span> '
        html += f'<span style="color: {color};">{message}</span>'
        self.image_recognition_log_area.append(html)

        cursor = self.image_recognition_log_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.image_recognition_log_area.setTextCursor(cursor)

    def _update_image_recognition_progress(self, progress: ImageRecognitionTaskProgress):
        if progress.total_files > 0:
            percent = int(progress.saved_files / progress.total_files * 100)
            self.image_recognition_progress_bar.setValue(percent)

        self.image_recognition_stats_label.setText(
            f"已完成: {progress.completed_folders}/{progress.total_folders} 文件夹  "
            f"已保存: {progress.saved_files} 个文件  "
            f"失败: {progress.failed_tasks}"
        )

        if progress.current_folder:
            self.image_recognition_status_text.setText(
                f"正在处理: {progress.current_folder} ({progress.current_file_index}/{self.image_recognition_count_spin.value()})"
            )

    def _set_image_recognition_buttons_state(self, state: str):
        if state == "idle":
            self.image_recognition_start_btn.setEnabled(True)
            self.image_recognition_pause_btn.setEnabled(False)
            self.image_recognition_resume_btn.setEnabled(False)
            self.image_recognition_stop_btn.setEnabled(False)
            self.image_recognition_refresh_btn.setEnabled(True)
            self.image_recognition_prompt_input.setEnabled(True)
            self.image_recognition_count_spin.setEnabled(True)
            self.image_recognition_concurrent_spin.setEnabled(True)
            self.product_folder_list.setEnabled(True)
            self.image_recognition_status_text.setText("没有运行项目...")
        elif state == "running":
            self.image_recognition_start_btn.setEnabled(False)
            self.image_recognition_pause_btn.setEnabled(True)
            self.image_recognition_resume_btn.setEnabled(False)
            self.image_recognition_stop_btn.setEnabled(True)
            self.image_recognition_refresh_btn.setEnabled(False)
            self.image_recognition_prompt_input.setEnabled(False)
            self.image_recognition_count_spin.setEnabled(False)
            self.image_recognition_concurrent_spin.setEnabled(False)
            self.product_folder_list.setEnabled(False)
        elif state == "paused":
            self.image_recognition_start_btn.setEnabled(False)
            self.image_recognition_pause_btn.setEnabled(False)
            self.image_recognition_resume_btn.setEnabled(True)
            self.image_recognition_stop_btn.setEnabled(True)
            self.image_recognition_status_text.setText("已暂停")

    def _on_image_recognition_start(self):
        prompt = self.image_recognition_prompt_input.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "提示", "请输入提示词")
            return

        if not self.config.image_recognition_api.api_key:
            QMessageBox.warning(self, "提示", "请先在设置页面配置识图 API Key")
            return

        selected_folders = self._get_selected_folders()
        if not selected_folders:
            QMessageBox.warning(self, "提示", "请选择至少一个商品文件夹")
            return

        file_count = self.image_recognition_count_spin.value()
        max_concurrent = self.image_recognition_concurrent_spin.value()

        self.image_recognition_log_area.clear()
        self.image_recognition_progress_bar.setValue(0)
        self.image_recognition_stats_label.setText("已完成: 0/0 文件夹  已保存: 0 个文件")

        api_client = ImageRecognitionAPIClient(
            base_url=self.config.image_recognition_api.base_url,
            api_key=self.config.image_recognition_api.api_key,
            model=self.config.image_recognition_api.model,
        )

        self.image_recognition_task_manager = ImageRecognitionTaskManager(
            api_client=api_client,
            input_base_dir=self.image_recognition_input_dir,
            output_base_dir=self.image_recognition_output_dir,
            max_concurrent=max_concurrent,
        )

        self.image_recognition_start_time = time.time()

        self.image_recognition_worker = ImageRecognitionAsyncWorker(
            self.image_recognition_task_manager,
            selected_folders,
            prompt,
            file_count,
        )
        self.image_recognition_worker.log_signal.connect(self._image_recognition_log)
        self.image_recognition_worker.progress_signal.connect(
            self._update_image_recognition_progress
        )
        self.image_recognition_worker.finished_signal.connect(
            self._on_image_recognition_task_finished
        )
        self.image_recognition_worker.start()

        self._set_image_recognition_buttons_state("running")
        self._image_recognition_log(
            f"开始图片识别任务: {len(selected_folders)} 个文件夹, "
            f"每个生成 {file_count} 个文件, 并发数: {max_concurrent}",
            "info"
        )

    def _on_image_recognition_pause(self):
        if self.image_recognition_task_manager:
            self.image_recognition_task_manager.pause()
            self._set_image_recognition_buttons_state("paused")
            self._image_recognition_log("任务已暂停", "warning")

    def _on_image_recognition_resume(self):
        if self.image_recognition_task_manager:
            self.image_recognition_task_manager.resume()
            self._set_image_recognition_buttons_state("running")
            self._image_recognition_log("任务已继续", "info")

    def _on_image_recognition_stop(self):
        if self.image_recognition_task_manager:
            self.image_recognition_task_manager.stop()
            self._image_recognition_log("正在停止任务...", "warning")

    def _on_image_recognition_task_finished(self, progress: ImageRecognitionTaskProgress):
        self._set_image_recognition_buttons_state("idle")

        if progress:
            self._image_recognition_log(
                f"任务完成! 已保存: {progress.saved_files} 个文件, "
                f"失败: {progress.failed_tasks}",
                "success"
            )
        else:
            self._image_recognition_log("任务异常结束", "error")

        self.image_recognition_task_manager = None
        self.image_recognition_worker = None

    def _load_last_image_recognition_prompt(self):
        """Load last image recognition prompt on startup"""
        if self.config.last_image_recognition_prompt:
            self.image_recognition_prompt_input.setPlainText(
                self.config.last_image_recognition_prompt
            )
        self._load_image_recognition_templates()

    def save_current_image_recognition_prompt(self):
        """Save current image recognition prompt for next startup"""
        self.config.last_image_recognition_prompt = (
            self.image_recognition_prompt_input.toPlainText().strip()
        )

    # Merge Copywriting methods
    def _create_merge_copywriting_tab(self) -> QWidget:
        """Create merge copywriting tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(3)

        toolbar = self._create_merge_copywriting_toolbar()
        layout.addWidget(toolbar)

        content_frame = self._create_merge_copywriting_content_area()
        layout.addWidget(content_frame, 1)

        status_bar = self._create_merge_copywriting_status_bar()
        layout.addWidget(status_bar)

        log_frame = self._create_merge_copywriting_log_area()
        layout.addWidget(log_frame)

        return widget

    def _create_merge_copywriting_toolbar(self) -> QFrame:
        toolbar = QFrame()
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(6)

        label_style = "color: #333333; background: transparent; border: none;"
        spin_style = """
            QSpinBox {
                border: 1px solid #d0d0d0;
                padding: 1px 4px;
                background: #ffffff;
                min-width: 70px;
            }
        """

        count_label = QLabel("合并数量:")
        count_label.setFont(QFont("Microsoft YaHei", 9))
        count_label.setStyleSheet(label_style)
        self.merge_copywriting_count_spin = QSpinBox()
        self.merge_copywriting_count_spin.setRange(1, 1000)
        self.merge_copywriting_count_spin.setValue(10)
        self.merge_copywriting_count_spin.setStyleSheet(spin_style)

        concurrent_label = QLabel("并发数:")
        concurrent_label.setFont(QFont("Microsoft YaHei", 9))
        concurrent_label.setStyleSheet(label_style)
        self.merge_copywriting_concurrent_spin = QSpinBox()
        self.merge_copywriting_concurrent_spin.setRange(1, 10)
        self.merge_copywriting_concurrent_spin.setValue(3)
        self.merge_copywriting_concurrent_spin.setStyleSheet(spin_style)

        layout.addWidget(count_label)
        layout.addWidget(self.merge_copywriting_count_spin)
        layout.addWidget(concurrent_label)
        layout.addWidget(self.merge_copywriting_concurrent_spin)

        layout.addStretch()

        btn_style = """
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e8f4fc;
            }
            QPushButton:disabled {
                color: #999999;
                background-color: #f0f0f0;
            }
        """

        primary_btn_style = """
            QPushButton {
                color: #ffffff;
                background-color: #0066cc;
                border: 1px solid #0055aa;
                padding: 2px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0055aa;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                border-color: #bbbbbb;
            }
        """

        stop_btn_style = """
            QPushButton {
                color: #cc0000;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #ffeeee;
            }
            QPushButton:disabled {
                color: #999999;
                background-color: #f0f0f0;
            }
        """

        self.merge_copywriting_refresh_btn = QPushButton("刷新")
        self.merge_copywriting_refresh_btn.setFont(QFont("Microsoft YaHei", 9))
        self.merge_copywriting_refresh_btn.setStyleSheet(btn_style)
        self.merge_copywriting_refresh_btn.clicked.connect(self._refresh_merge_product_folders)

        self.merge_copywriting_start_btn = QPushButton("开始合并")
        self.merge_copywriting_start_btn.setFont(QFont("Microsoft YaHei", 9))
        self.merge_copywriting_start_btn.setStyleSheet(primary_btn_style)
        self.merge_copywriting_start_btn.clicked.connect(self._on_merge_copywriting_start)

        self.merge_copywriting_pause_btn = QPushButton("暂停")
        self.merge_copywriting_pause_btn.setFont(QFont("Microsoft YaHei", 9))
        self.merge_copywriting_pause_btn.setStyleSheet(btn_style)
        self.merge_copywriting_pause_btn.setEnabled(False)
        self.merge_copywriting_pause_btn.clicked.connect(self._on_merge_copywriting_pause)

        self.merge_copywriting_resume_btn = QPushButton("继续")
        self.merge_copywriting_resume_btn.setFont(QFont("Microsoft YaHei", 9))
        self.merge_copywriting_resume_btn.setStyleSheet(btn_style)
        self.merge_copywriting_resume_btn.setEnabled(False)
        self.merge_copywriting_resume_btn.clicked.connect(self._on_merge_copywriting_resume)

        self.merge_copywriting_stop_btn = QPushButton("停止")
        self.merge_copywriting_stop_btn.setFont(QFont("Microsoft YaHei", 9))
        self.merge_copywriting_stop_btn.setStyleSheet(stop_btn_style)
        self.merge_copywriting_stop_btn.setEnabled(False)
        self.merge_copywriting_stop_btn.clicked.connect(self._on_merge_copywriting_stop)

        layout.addWidget(self.merge_copywriting_refresh_btn)
        layout.addWidget(self.merge_copywriting_start_btn)
        layout.addWidget(self.merge_copywriting_pause_btn)
        layout.addWidget(self.merge_copywriting_resume_btn)
        layout.addWidget(self.merge_copywriting_stop_btn)

        return toolbar

    def _create_merge_copywriting_content_area(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame#merge_copywriting_content_frame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)
        frame.setObjectName("merge_copywriting_content_frame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        # Folder selection area
        folder_label = QLabel("商品文案子文件夹选择")
        folder_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        folder_label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(folder_label)

        self.merge_product_folder_list = QListWidget()
        self.merge_product_folder_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.merge_product_folder_list.setMinimumHeight(80)
        self.merge_product_folder_list.setMaximumHeight(150)
        self.merge_product_folder_list.setFont(QFont("Microsoft YaHei", 10))
        self.merge_product_folder_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #d0d0d0;
                background-color: #ffffff;
            }
            QListWidget::item {
                padding: 3px;
            }
            QListWidget::item:selected {
                background-color: #e8f4fc;
                color: #333333;
            }
        """)
        layout.addWidget(self.merge_product_folder_list)

        # Prompt area
        prompt_label = QLabel("提示词")
        prompt_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        prompt_label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(prompt_label)

        # Template selection area
        template_layout = QHBoxLayout()
        template_layout.setSpacing(3)

        self.merge_copywriting_template_combo = QComboBox()
        self.merge_copywriting_template_combo.setMinimumWidth(200)
        self.merge_copywriting_template_combo.setFont(QFont("Microsoft YaHei", 9))
        self.merge_copywriting_template_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #d0d0d0;
                padding: 1px 4px;
                background: #ffffff;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        self.merge_copywriting_template_combo.currentIndexChanged.connect(
            self._on_merge_copywriting_template_selected
        )
        template_layout.addWidget(self.merge_copywriting_template_combo)

        btn_style = """
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e8f4fc;
            }
        """

        self.merge_copywriting_save_template_btn = QPushButton("保存为模板")
        self.merge_copywriting_save_template_btn.setFont(QFont("Microsoft YaHei", 9))
        self.merge_copywriting_save_template_btn.setStyleSheet(btn_style)
        self.merge_copywriting_save_template_btn.clicked.connect(
            self._on_merge_copywriting_save_template
        )
        template_layout.addWidget(self.merge_copywriting_save_template_btn)

        self.merge_copywriting_delete_template_btn = QPushButton("删除模板")
        self.merge_copywriting_delete_template_btn.setFont(QFont("Microsoft YaHei", 9))
        self.merge_copywriting_delete_template_btn.setStyleSheet(btn_style)
        self.merge_copywriting_delete_template_btn.clicked.connect(
            self._on_merge_copywriting_delete_template
        )
        template_layout.addWidget(self.merge_copywriting_delete_template_btn)

        template_layout.addStretch()
        layout.addLayout(template_layout)

        self.merge_copywriting_prompt_input = QTextEdit()
        self.merge_copywriting_prompt_input.setPlaceholderText("输入合并文案提示词...")
        self.merge_copywriting_prompt_input.setMinimumHeight(60)
        self.merge_copywriting_prompt_input.setMaximumHeight(120)
        self.merge_copywriting_prompt_input.setFont(QFont("Microsoft YaHei", 10))
        self.merge_copywriting_prompt_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #d0d0d0;
                background-color: #ffffff;
                padding: 5px;
            }
        """)
        layout.addWidget(self.merge_copywriting_prompt_input)

        # Progress area
        progress_label = QLabel("进度")
        progress_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        progress_label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(progress_label)

        self.merge_copywriting_progress_bar = QProgressBar()
        self.merge_copywriting_progress_bar.setMinimum(0)
        self.merge_copywriting_progress_bar.setMaximum(100)
        self.merge_copywriting_progress_bar.setValue(0)
        self.merge_copywriting_progress_bar.setFixedHeight(12)
        self.merge_copywriting_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #d0d0d0;
                background-color: #f0f0f0;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #0066cc;
            }
        """)
        layout.addWidget(self.merge_copywriting_progress_bar)

        self.merge_copywriting_stats_label = QLabel("已完成: 0/0  失败: 0  已保存: 0")
        self.merge_copywriting_stats_label.setFont(QFont("Microsoft YaHei", 9))
        self.merge_copywriting_stats_label.setStyleSheet("color: #666666; border: none;")
        layout.addWidget(self.merge_copywriting_stats_label)

        layout.addStretch()

        # Initialize folder list
        self._refresh_merge_product_folders()

        return frame

    def _create_merge_copywriting_status_bar(self) -> QFrame:
        frame = QFrame()
        frame.setFixedHeight(18)
        frame.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border: 1px solid #d0d0d0;
            }
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(6, 1, 6, 1)

        self.merge_copywriting_status_text = QLabel("没有运行项目...")
        self.merge_copywriting_status_text.setFont(QFont("Microsoft YaHei", 9))
        self.merge_copywriting_status_text.setStyleSheet(
            "color: #0066cc; border: none; background: transparent;"
        )
        layout.addWidget(self.merge_copywriting_status_text)

        layout.addStretch()

        return frame

    def _create_merge_copywriting_log_area(self) -> QFrame:
        frame = QFrame()
        frame.setMinimumHeight(120)
        frame.setMaximumHeight(200)
        frame.setStyleSheet("""
            QFrame#merge_copywriting_log_frame {
                background-color: #1e1e1e;
                border: 1px solid #333333;
            }
        """)
        frame.setObjectName("merge_copywriting_log_frame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel(" 日志")
        header.setFixedHeight(14)
        header.setFont(QFont("Microsoft YaHei", 9))
        header.setStyleSheet(
            "color: #888888; background-color: #2d2d2d; border: none; padding-left: 8px;"
        )
        layout.addWidget(header)

        self.merge_copywriting_log_area = QTextEdit()
        self.merge_copywriting_log_area.setReadOnly(True)
        self.merge_copywriting_log_area.setFont(QFont("Consolas", 10))
        self.merge_copywriting_log_area.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #00ff00;
                border: none;
                padding: 3px;
            }
        """)
        layout.addWidget(self.merge_copywriting_log_area)

        return frame

    def _refresh_merge_product_folders(self):
        """Refresh the merge product folder list"""
        self.merge_product_folder_list.clear()

        if not os.path.exists(self.image_recognition_output_dir):
            os.makedirs(self.image_recognition_output_dir, exist_ok=True)
            return

        folders = []
        for name in sorted(os.listdir(self.image_recognition_output_dir)):
            folder_path = os.path.join(self.image_recognition_output_dir, name)
            if os.path.isdir(folder_path):
                folders.append(name)

        for folder in folders:
            item = QListWidgetItem(folder)
            self.merge_product_folder_list.addItem(item)

    def _get_merge_selected_folders(self) -> list:
        """Get list of selected folder names for merge"""
        selected = []
        for item in self.merge_product_folder_list.selectedItems():
            selected.append(item.text())
        return selected

    def _load_merge_copywriting_templates(self):
        """Load templates into merge copywriting combo box"""
        self.merge_copywriting_template_combo.blockSignals(True)
        self.merge_copywriting_template_combo.clear()
        self.merge_copywriting_template_combo.addItem("-- 选择模板 --", None)
        for template in self.config.merge_copywriting_templates:
            self.merge_copywriting_template_combo.addItem(template.name, template.content)
        self.merge_copywriting_template_combo.blockSignals(False)

    def _on_merge_copywriting_template_selected(self, index: int):
        """Fill prompt when template is selected"""
        if index <= 0:
            return
        content = self.merge_copywriting_template_combo.itemData(index)
        if content:
            self.merge_copywriting_prompt_input.setPlainText(content)

    def _on_merge_copywriting_save_template(self):
        """Save current merge copywriting prompt as template"""
        from ..models.config import PromptTemplate

        prompt = self.merge_copywriting_prompt_input.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "提示", "请先输入提示词")
            return

        name, ok = QInputDialog.getText(self, "保存模板", "请输入模板名称:")
        if not ok or not name.strip():
            return

        name = name.strip()

        for i, template in enumerate(self.config.merge_copywriting_templates):
            if template.name == name:
                reply = QMessageBox.question(
                    self, "确认",
                    f"模板 '{name}' 已存在，是否覆盖？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.config.merge_copywriting_templates[i] = PromptTemplate(
                        name=name, content=prompt
                    )
                    self.config.save()
                    self._load_merge_copywriting_templates()
                    QMessageBox.information(self, "成功", f"模板 '{name}' 已更新")
                return

        self.config.merge_copywriting_templates.append(PromptTemplate(name=name, content=prompt))
        self.config.save()
        self._load_merge_copywriting_templates()
        QMessageBox.information(self, "成功", f"模板 '{name}' 已保存")

    def _on_merge_copywriting_delete_template(self):
        """Delete selected merge copywriting template"""
        index = self.merge_copywriting_template_combo.currentIndex()
        if index <= 0:
            QMessageBox.warning(self, "提示", "请先选择要删除的模板")
            return

        name = self.merge_copywriting_template_combo.currentText()
        reply = QMessageBox.question(
            self, "确认",
            f"确定要删除模板 '{name}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.config.merge_copywriting_templates = [
            t for t in self.config.merge_copywriting_templates if t.name != name
        ]
        self.config.save()
        self._load_merge_copywriting_templates()
        QMessageBox.information(self, "成功", f"模板 '{name}' 已删除")

    def _merge_copywriting_log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

        color_map = {
            "info": "#00ff00",
            "warning": "#ffff00",
            "error": "#ff0000",
            "success": "#00ff00",
        }
        color = color_map.get(level, "#00ff00")

        html = f'<span style="color: #888888;">[{timestamp}]</span> '
        html += f'<span style="color: {color};">{message}</span>'
        self.merge_copywriting_log_area.append(html)

        cursor = self.merge_copywriting_log_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.merge_copywriting_log_area.setTextCursor(cursor)

    def _update_merge_copywriting_progress(self, progress: MergeCopywritingTaskProgress):
        if progress.total_tasks > 0:
            percent = int(progress.completed_tasks / progress.total_tasks * 100)
            self.merge_copywriting_progress_bar.setValue(percent)

        self.merge_copywriting_stats_label.setText(
            f"已完成: {progress.completed_tasks}/{progress.total_tasks}  "
            f"失败: {progress.failed_tasks}  "
            f"已保存: {progress.saved_files}"
        )

        if progress.current_task:
            self.merge_copywriting_status_text.setText(
                f"正在处理: {progress.current_task}"
            )

    def _set_merge_copywriting_buttons_state(self, state: str):
        if state == "idle":
            self.merge_copywriting_start_btn.setEnabled(True)
            self.merge_copywriting_pause_btn.setEnabled(False)
            self.merge_copywriting_resume_btn.setEnabled(False)
            self.merge_copywriting_stop_btn.setEnabled(False)
            self.merge_copywriting_refresh_btn.setEnabled(True)
            self.merge_copywriting_prompt_input.setEnabled(True)
            self.merge_copywriting_count_spin.setEnabled(True)
            self.merge_copywriting_concurrent_spin.setEnabled(True)
            self.merge_product_folder_list.setEnabled(True)
            self.merge_copywriting_status_text.setText("没有运行项目...")
        elif state == "running":
            self.merge_copywriting_start_btn.setEnabled(False)
            self.merge_copywriting_pause_btn.setEnabled(True)
            self.merge_copywriting_resume_btn.setEnabled(False)
            self.merge_copywriting_stop_btn.setEnabled(True)
            self.merge_copywriting_refresh_btn.setEnabled(False)
            self.merge_copywriting_prompt_input.setEnabled(False)
            self.merge_copywriting_count_spin.setEnabled(False)
            self.merge_copywriting_concurrent_spin.setEnabled(False)
            self.merge_product_folder_list.setEnabled(False)
        elif state == "paused":
            self.merge_copywriting_start_btn.setEnabled(False)
            self.merge_copywriting_pause_btn.setEnabled(False)
            self.merge_copywriting_resume_btn.setEnabled(True)
            self.merge_copywriting_stop_btn.setEnabled(True)
            self.merge_copywriting_status_text.setText("已暂停")

    def _on_merge_copywriting_start(self):
        prompt = self.merge_copywriting_prompt_input.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "提示", "请输入提示词")
            return

        if not self.config.merge_copywriting_api.api_key:
            QMessageBox.warning(self, "提示", "请先在设置页面配置合并文案 API Key")
            return

        selected_folders = self._get_merge_selected_folders()
        if not selected_folders:
            QMessageBox.warning(self, "提示", "请选择至少一个商品文案子文件夹")
            return

        max_pairs = self.merge_copywriting_count_spin.value()
        max_concurrent = self.merge_copywriting_concurrent_spin.value()

        self.merge_copywriting_log_area.clear()
        self.merge_copywriting_progress_bar.setValue(0)
        self.merge_copywriting_stats_label.setText("已完成: 0/0  失败: 0  已保存: 0")

        api_client = MergeCopywritingAPIClient(
            base_url=self.config.merge_copywriting_api.base_url,
            api_key=self.config.merge_copywriting_api.api_key,
            model=self.config.merge_copywriting_api.model,
        )

        self.merge_copywriting_task_manager = MergeCopywritingTaskManager(
            api_client=api_client,
            product_copywriting_dir=self.image_recognition_output_dir,
            video_copywriting_dir=self.copywriting_save_dir,
            output_dir=self.merge_copywriting_output_dir,
            recycle_dir=self.recycle_dir,
            max_concurrent=max_concurrent,
            max_retries=self.config.merge_copywriting_api.max_retries,
        )

        self.merge_copywriting_start_time = time.time()

        self.merge_copywriting_worker = MergeCopywritingAsyncWorker(
            self.merge_copywriting_task_manager,
            selected_folders,
            prompt,
            max_pairs,
        )
        self.merge_copywriting_worker.log_signal.connect(self._merge_copywriting_log)
        self.merge_copywriting_worker.progress_signal.connect(
            self._update_merge_copywriting_progress
        )
        self.merge_copywriting_worker.finished_signal.connect(
            self._on_merge_copywriting_task_finished
        )
        self.merge_copywriting_worker.start()

        self._set_merge_copywriting_buttons_state("running")
        self._merge_copywriting_log(
            f"开始合并文案任务: {len(selected_folders)} 个文件夹, "
            f"最大配对数: {max_pairs}, 并发数: {max_concurrent}",
            "info"
        )

    def _on_merge_copywriting_pause(self):
        if self.merge_copywriting_task_manager:
            self.merge_copywriting_task_manager.pause()
            self._set_merge_copywriting_buttons_state("paused")
            self._merge_copywriting_log("任务已暂停", "warning")

    def _on_merge_copywriting_resume(self):
        if self.merge_copywriting_task_manager:
            self.merge_copywriting_task_manager.resume()
            self._set_merge_copywriting_buttons_state("running")
            self._merge_copywriting_log("任务已继续", "info")

    def _on_merge_copywriting_stop(self):
        if self.merge_copywriting_task_manager:
            self.merge_copywriting_task_manager.stop()
            self._merge_copywriting_log("正在停止任务...", "warning")

    def _on_merge_copywriting_task_finished(self, progress: MergeCopywritingTaskProgress):
        self._set_merge_copywriting_buttons_state("idle")

        if progress:
            self._merge_copywriting_log(
                f"任务完成! 已保存: {progress.saved_files} 个文件, "
                f"失败: {progress.failed_tasks}",
                "success"
            )
        else:
            self._merge_copywriting_log("任务异常结束", "error")

        self.merge_copywriting_task_manager = None
        self.merge_copywriting_worker = None

    def _load_last_merge_copywriting_prompt(self):
        """Load last merge copywriting prompt on startup"""
        if self.config.last_merge_copywriting_prompt:
            self.merge_copywriting_prompt_input.setPlainText(
                self.config.last_merge_copywriting_prompt
            )
        self._load_merge_copywriting_templates()

    def save_current_merge_copywriting_prompt(self):
        """Save current merge copywriting prompt for next startup"""
        self.config.last_merge_copywriting_prompt = (
            self.merge_copywriting_prompt_input.toPlainText().strip()
        )

    # ==================== TTS Tab Methods ====================

    def _create_tts_tab(self) -> QWidget:
        """Create TTS generation tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(3)

        toolbar = self._create_tts_toolbar()
        layout.addWidget(toolbar)

        content_frame = self._create_tts_content_area()
        layout.addWidget(content_frame, 1)

        status_bar = self._create_tts_status_bar()
        layout.addWidget(status_bar)

        log_frame = self._create_tts_log_area()
        layout.addWidget(log_frame)

        return widget

    def _create_tts_toolbar(self) -> QFrame:
        toolbar = QFrame()
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)

        # 主布局改为垂直布局
        main_layout = QVBoxLayout(toolbar)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        label_style = "color: #333333; background: transparent; border: none;"
        radio_style = "color: #333333; background: transparent; border: none;"
        spin_style = """
            QSpinBox {
                border: 1px solid #d0d0d0;
                padding: 1px 4px;
                background: #ffffff;
                min-width: 70px;
            }
        """
        input_style = """
            QComboBox {
                border: 1px solid #d0d0d0;
                padding: 1px 4px;
                background: #ffffff;
                min-width: 80px;
            }
        """

        # ========== 第一行：基础参数 ==========
        first_row = QWidget()
        first_row_layout = QHBoxLayout(first_row)
        first_row_layout.setContentsMargins(6, 2, 6, 2)
        first_row_layout.setSpacing(6)

        # 文案类型选择
        self.tts_mode_group = QButtonGroup(self)
        self.tts_daihuo_radio = QRadioButton("带货文案")
        self.tts_daihuo_radio.setFont(QFont("Microsoft YaHei", 9))
        self.tts_daihuo_radio.setStyleSheet(radio_style)
        self.tts_liuliang_radio = QRadioButton("流量文案")
        self.tts_liuliang_radio.setFont(QFont("Microsoft YaHei", 9))
        self.tts_liuliang_radio.setStyleSheet(radio_style)
        self.tts_yindao_radio = QRadioButton("引导文案")
        self.tts_yindao_radio.setFont(QFont("Microsoft YaHei", 9))
        self.tts_yindao_radio.setStyleSheet(radio_style)
        self.tts_mode_group.addButton(self.tts_daihuo_radio, 0)
        self.tts_mode_group.addButton(self.tts_liuliang_radio, 1)
        self.tts_mode_group.addButton(self.tts_yindao_radio, 2)
        self.tts_daihuo_radio.setChecked(True)  # 默认选中带货文案
        self.tts_mode_group.buttonClicked.connect(self._on_tts_mode_changed)

        first_row_layout.addWidget(self.tts_daihuo_radio)
        first_row_layout.addWidget(self.tts_liuliang_radio)
        first_row_layout.addWidget(self.tts_yindao_radio)

        # 分隔符
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setStyleSheet("color: #d0d0d0;")
        first_row_layout.addWidget(separator)

        # 生成数量
        count_label = QLabel("生成数量:")
        count_label.setFont(QFont("Microsoft YaHei", 9))
        count_label.setStyleSheet(label_style)
        self.tts_count_spin = QSpinBox()
        self.tts_count_spin.setRange(1, 1000)
        self.tts_count_spin.setValue(10)
        self.tts_count_spin.setStyleSheet(spin_style)

        first_row_layout.addWidget(count_label)
        first_row_layout.addWidget(self.tts_count_spin)

        # 并发数
        concurrent_label = QLabel("并发数:")
        concurrent_label.setFont(QFont("Microsoft YaHei", 9))
        concurrent_label.setStyleSheet(label_style)
        self.tts_concurrent_spin = QSpinBox()
        self.tts_concurrent_spin.setRange(1, 10)
        self.tts_concurrent_spin.setValue(3)
        self.tts_concurrent_spin.setStyleSheet(spin_style)

        first_row_layout.addWidget(concurrent_label)
        first_row_layout.addWidget(self.tts_concurrent_spin)

        # ========== 第二行：字幕功能 ==========
        second_row = QWidget()
        second_row_layout = QHBoxLayout(second_row)
        second_row_layout.setContentsMargins(6, 2, 6, 2)
        second_row_layout.setSpacing(6)

        # 同步生成字幕
        self.tts_subtitle_checkbox = QCheckBox("同步生成字幕")
        self.tts_subtitle_checkbox.setFont(QFont("Microsoft YaHei", 9))
        self.tts_subtitle_checkbox.setChecked(self.config.last_tts_subtitle_enabled)
        self.tts_subtitle_checkbox.stateChanged.connect(self._on_subtitle_checkbox_changed)
        second_row_layout.addWidget(self.tts_subtitle_checkbox)

        # 字幕生成方式选择
        self.tts_subtitle_method_group = QButtonGroup(self)
        self.tts_subtitle_api_radio = QRadioButton("使用API生成")
        self.tts_subtitle_api_radio.setFont(QFont("Microsoft YaHei", 9))
        self.tts_subtitle_api_radio.setStyleSheet(radio_style)
        self.tts_subtitle_local_radio = QRadioButton("使用本地模型生成")
        self.tts_subtitle_local_radio.setFont(QFont("Microsoft YaHei", 9))
        self.tts_subtitle_local_radio.setStyleSheet(radio_style)
        self.tts_subtitle_method_group.addButton(self.tts_subtitle_api_radio, 0)
        self.tts_subtitle_method_group.addButton(self.tts_subtitle_local_radio, 1)
        self.tts_subtitle_api_radio.setChecked(True)
        self.tts_subtitle_method_group.buttonClicked.connect(self._on_subtitle_method_changed)

        second_row_layout.addWidget(self.tts_subtitle_api_radio)
        second_row_layout.addWidget(self.tts_subtitle_local_radio)

        # 本地模型配置
        model_label = QLabel("本地模型:")
        model_label.setFont(QFont("Microsoft YaHei", 9))
        model_label.setStyleSheet(label_style)
        second_row_layout.addWidget(model_label)

        self.tts_local_model_combo = QComboBox()
        self.tts_local_model_combo.addItems(["small", "medium", "large-v2", "large-v3"])
        self.tts_local_model_combo.setStyleSheet(input_style)
        second_row_layout.addWidget(self.tts_local_model_combo)

        # 设备选择
        device_label = QLabel("设备:")
        device_label.setFont(QFont("Microsoft YaHei", 9))
        device_label.setStyleSheet(label_style)
        second_row_layout.addWidget(device_label)

        self.tts_local_device_combo = QComboBox()
        self.tts_local_device_combo.addItems(["cpu", "cuda"])
        self.tts_local_device_combo.setStyleSheet(input_style)
        second_row_layout.addWidget(self.tts_local_device_combo)

        # 生成商品时间段
        self.tts_product_time_checkbox = QCheckBox("生成商品时间段")
        self.tts_product_time_checkbox.setFont(QFont("Microsoft YaHei", 9))
        self.tts_product_time_checkbox.setChecked(self.config.last_tts_product_time_enabled)
        self.tts_product_time_checkbox.stateChanged.connect(self._on_product_time_checkbox_changed)
        second_row_layout.addWidget(self.tts_product_time_checkbox)

        # 字幕文本校正
        self.tts_subtitle_correction_checkbox = QCheckBox("字幕文本校正")
        self.tts_subtitle_correction_checkbox.setFont(QFont("Microsoft YaHei", 9))
        self.tts_subtitle_correction_checkbox.setChecked(self.config.last_tts_subtitle_correction_enabled)
        self.tts_subtitle_correction_checkbox.setToolTip("用原始文案替换ASR识别的字幕文本，保留时间轴，去除标点")
        self.tts_subtitle_correction_checkbox.setEnabled(self.config.last_tts_subtitle_enabled)
        second_row_layout.addWidget(self.tts_subtitle_correction_checkbox)

        second_row_layout.addStretch()

        # 添加两行到主布局
        main_layout.addWidget(first_row)
        main_layout.addWidget(second_row)

        # ========== 操作按钮样式定义 ==========
        btn_style = """
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e8f4fc;
            }
            QPushButton:disabled {
                color: #999999;
                background-color: #f0f0f0;
            }
        """

        primary_btn_style = """
            QPushButton {
                color: #ffffff;
                background-color: #0066cc;
                border: 1px solid #0055aa;
                padding: 2px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #0055aa;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                border-color: #bbbbbb;
            }
        """

        stop_btn_style = """
            QPushButton {
                color: #cc0000;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 2px 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #ffeeee;
            }
            QPushButton:disabled {
                color: #999999;
                background-color: #f0f0f0;
            }
        """

        self.tts_refresh_btn = QPushButton("刷新")
        self.tts_refresh_btn.setFont(QFont("Microsoft YaHei", 9))
        self.tts_refresh_btn.setStyleSheet(btn_style)
        self.tts_refresh_btn.clicked.connect(self._refresh_tts_folders)

        self.tts_start_btn = QPushButton("开始生成")
        self.tts_start_btn.setFont(QFont("Microsoft YaHei", 9))
        self.tts_start_btn.setStyleSheet(primary_btn_style)
        self.tts_start_btn.clicked.connect(self._on_tts_start)

        self.tts_pause_btn = QPushButton("暂停")
        self.tts_pause_btn.setFont(QFont("Microsoft YaHei", 9))
        self.tts_pause_btn.setStyleSheet(btn_style)
        self.tts_pause_btn.setEnabled(False)
        self.tts_pause_btn.clicked.connect(self._on_tts_pause)

        self.tts_resume_btn = QPushButton("继续")
        self.tts_resume_btn.setFont(QFont("Microsoft YaHei", 9))
        self.tts_resume_btn.setStyleSheet(btn_style)
        self.tts_resume_btn.setEnabled(False)
        self.tts_resume_btn.clicked.connect(self._on_tts_resume)

        self.tts_stop_btn = QPushButton("停止")
        self.tts_stop_btn.setFont(QFont("Microsoft YaHei", 9))
        self.tts_stop_btn.setStyleSheet(stop_btn_style)
        self.tts_stop_btn.setEnabled(False)
        self.tts_stop_btn.clicked.connect(self._on_tts_stop)

        self.tts_fix_subtitle_btn = QPushButton("修复存量字幕")
        self.tts_fix_subtitle_btn.setFont(QFont("Microsoft YaHei", 9))
        self.tts_fix_subtitle_btn.setStyleSheet(btn_style)
        self.tts_fix_subtitle_btn.setToolTip("扫描 output 和 input/视频配音 目录下的 SRT 文件并批量修复断句")
        self.tts_fix_subtitle_btn.clicked.connect(self._on_fix_subtitle_batch)

        # 将操作按钮添加到第一行
        first_row_layout.addWidget(self.tts_refresh_btn)
        first_row_layout.addWidget(self.tts_start_btn)
        first_row_layout.addWidget(self.tts_pause_btn)
        first_row_layout.addWidget(self.tts_resume_btn)
        first_row_layout.addWidget(self.tts_stop_btn)
        first_row_layout.addWidget(self.tts_fix_subtitle_btn)
        first_row_layout.addStretch()

        return toolbar

    def _create_tts_content_area(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame#tts_content_frame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)
        frame.setObjectName("tts_content_frame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        # Folder selection area
        folder_label = QLabel("合并文案子文件夹选择")
        folder_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        folder_label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(folder_label)

        self.tts_folder_list = QListWidget()
        self.tts_folder_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.tts_folder_list.setMinimumHeight(80)
        self.tts_folder_list.setMaximumHeight(200)
        self.tts_folder_list.setFont(QFont("Microsoft YaHei", 10))
        self.tts_folder_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #d0d0d0;
                background-color: #ffffff;
            }
            QListWidget::item {
                padding: 3px;
            }
            QListWidget::item:selected {
                background-color: #e8f4fc;
                color: #333333;
            }
        """)
        layout.addWidget(self.tts_folder_list)

        # Progress area
        progress_label = QLabel("进度")
        progress_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        progress_label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(progress_label)

        self.tts_progress_bar = QProgressBar()
        self.tts_progress_bar.setMinimum(0)
        self.tts_progress_bar.setMaximum(100)
        self.tts_progress_bar.setValue(0)
        self.tts_progress_bar.setFixedHeight(12)
        self.tts_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #d0d0d0;
                background-color: #f0f0f0;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #0066cc;
            }
        """)
        layout.addWidget(self.tts_progress_bar)

        self.tts_stats_label = QLabel("已完成: 0/0  失败: 0  已保存: 0")
        self.tts_stats_label.setFont(QFont("Microsoft YaHei", 9))
        self.tts_stats_label.setStyleSheet("color: #666666; border: none;")
        layout.addWidget(self.tts_stats_label)

        layout.addStretch()

        # Initialize folder list
        self._refresh_tts_folders()

        return frame

    def _create_tts_status_bar(self) -> QFrame:
        frame = QFrame()
        frame.setFixedHeight(18)
        frame.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border: 1px solid #d0d0d0;
            }
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(6, 1, 6, 1)

        self.tts_status_text = QLabel("没有运行项目...")
        self.tts_status_text.setFont(QFont("Microsoft YaHei", 9))
        self.tts_status_text.setStyleSheet(
            "color: #0066cc; border: none; background: transparent;"
        )
        layout.addWidget(self.tts_status_text)

        layout.addStretch()

        return frame

    def _create_tts_log_area(self) -> QFrame:
        frame = QFrame()
        frame.setMinimumHeight(120)
        frame.setMaximumHeight(200)
        frame.setStyleSheet("""
            QFrame#tts_log_frame {
                background-color: #1e1e1e;
                border: 1px solid #333333;
            }
        """)
        frame.setObjectName("tts_log_frame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel(" 日志")
        header.setFixedHeight(14)
        header.setFont(QFont("Microsoft YaHei", 9))
        header.setStyleSheet(
            "color: #888888; background-color: #2d2d2d; border: none; padding-left: 8px;"
        )
        layout.addWidget(header)

        self.tts_log_area = QTextEdit()
        self.tts_log_area.setReadOnly(True)
        self.tts_log_area.setFont(QFont("Consolas", 10))
        self.tts_log_area.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #00ff00;
                border: none;
                padding: 3px;
            }
        """)
        layout.addWidget(self.tts_log_area)

        return frame

    def _refresh_tts_folders(self):
        """Refresh the TTS folder list"""
        self.tts_folder_list.clear()

        if not os.path.exists(self.merge_copywriting_output_dir):
            os.makedirs(self.merge_copywriting_output_dir, exist_ok=True)
            return

        folders = []
        for name in sorted(os.listdir(self.merge_copywriting_output_dir)):
            folder_path = os.path.join(self.merge_copywriting_output_dir, name)
            if os.path.isdir(folder_path):
                folders.append(name)

        for folder in folders:
            item = QListWidgetItem(folder)
            self.tts_folder_list.addItem(item)

    def _get_tts_selected_folders(self) -> list:
        """Get list of selected folder names for TTS"""
        selected = []
        for item in self.tts_folder_list.selectedItems():
            selected.append(item.text())
        return selected

    def _tts_log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

        color_map = {
            "info": "#00ff00",
            "warning": "#ffff00",
            "error": "#ff0000",
            "success": "#00ff00",
        }
        color = color_map.get(level, "#00ff00")

        html = f'<span style="color: #888888;">[{timestamp}]</span> '
        html += f'<span style="color: {color};">{message}</span>'
        self.tts_log_area.append(html)

        cursor = self.tts_log_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.tts_log_area.setTextCursor(cursor)

    def _update_tts_progress(self, progress: TTSTaskProgress):
        if progress.total_tasks > 0:
            percent = int(progress.completed_tasks / progress.total_tasks * 100)
            self.tts_progress_bar.setValue(percent)

        # Build stats text with subtitle info if enabled
        stats_text = (
            f"已完成: {progress.completed_tasks}/{progress.total_tasks}  "
            f"失败: {progress.failed_tasks}  "
            f"已保存: {progress.saved_files}"
        )
        if self.tts_subtitle_checkbox.isChecked():
            stats_text += (
                f"  字幕: {progress.subtitle_completed}成功/{progress.subtitle_failed}失败"
            )
        if self.tts_product_time_checkbox.isChecked():
            stats_text += (
                f"  时间段: {progress.product_time_completed}成功/{progress.product_time_failed}失败"
            )
        self.tts_stats_label.setText(stats_text)

        # Update status text
        if progress.current_product_time_task:
            self.tts_status_text.setText(
                f"正在识别时间段: {progress.current_product_time_task}"
            )
        elif progress.current_subtitle_task:
            self.tts_status_text.setText(
                f"正在生成字幕: {progress.current_subtitle_task}"
            )
        elif progress.current_task:
            self.tts_status_text.setText(
                f"正在处理: {progress.current_task}"
            )

    def _on_subtitle_checkbox_changed(self, state: int):
        """Handle subtitle checkbox state change"""
        is_checked = (state == Qt.Checked)

        # Enable/disable subtitle generation method selection
        self.tts_subtitle_api_radio.setEnabled(is_checked)
        self.tts_subtitle_local_radio.setEnabled(is_checked)

        # Enable/disable local model configuration based on current selection
        is_local = self.tts_subtitle_local_radio.isChecked()
        self.tts_local_model_combo.setEnabled(is_checked and is_local)
        self.tts_local_device_combo.setEnabled(is_checked and is_local)

        # If subtitle is unchecked, also uncheck product time and correction
        if not is_checked:
            self.tts_product_time_checkbox.setChecked(False)
            self.tts_subtitle_correction_checkbox.setChecked(False)
        self.tts_subtitle_correction_checkbox.setEnabled(is_checked)

    def _on_subtitle_method_changed(self, button):
        """Handle subtitle generation method change"""
        is_local = self.tts_subtitle_local_radio.isChecked()
        is_subtitle_checked = self.tts_subtitle_checkbox.isChecked()

        # Only enable local model configuration when local method is selected and subtitle is checked
        self.tts_local_model_combo.setEnabled(is_subtitle_checked and is_local)
        self.tts_local_device_combo.setEnabled(is_subtitle_checked and is_local)

    def _restore_subtitle_method_for_mode(self):
        """Restore subtitle generation method for current mode"""
        if self.tts_liuliang_radio.isChecked():
            method = self.config.ui_state.tts_subtitle_method_liuliang
        elif self.tts_yindao_radio.isChecked():
            method = self.config.ui_state.tts_subtitle_method_yindao
        else:
            method = self.config.ui_state.tts_subtitle_method_daihuo

        if method == "local":
            self.tts_subtitle_local_radio.setChecked(True)
        else:
            self.tts_subtitle_api_radio.setChecked(True)

        # Trigger method change event to update control states
        self._on_subtitle_method_changed(None)

    def _on_product_time_checkbox_changed(self, state: int):
        """Handle product time checkbox state change"""
        # If product time is checked, also check subtitle
        if state == Qt.Checked:
            self.tts_subtitle_checkbox.setChecked(True)

    def _on_tts_mode_changed(self, button):
        """Handle TTS mode radio button change"""
        is_daihuo = self.tts_daihuo_radio.isChecked()

        # Subtitle checkbox is always enabled
        self.tts_subtitle_checkbox.setEnabled(True)

        # Product time and folder list are only enabled in daihuo mode
        self.tts_product_time_checkbox.setEnabled(is_daihuo)
        self.tts_folder_list.setEnabled(is_daihuo)

        if not is_daihuo:
            # Uncheck product time in non-daihuo mode
            self.tts_product_time_checkbox.setChecked(False)

        # Restore subtitle method for current mode
        self._restore_subtitle_method_for_mode()

    def _set_tts_buttons_state(self, state: str):
        if state == "idle":
            self.tts_start_btn.setEnabled(True)
            self.tts_pause_btn.setEnabled(False)
            self.tts_resume_btn.setEnabled(False)
            self.tts_stop_btn.setEnabled(False)
            self.tts_refresh_btn.setEnabled(True)
            self.tts_count_spin.setEnabled(True)
            self.tts_concurrent_spin.setEnabled(True)
            # 根据当前模式恢复控件状态
            is_liuliang = self.tts_liuliang_radio.isChecked()
            self.tts_folder_list.setEnabled(not is_liuliang and not self.tts_yindao_radio.isChecked())
            self.tts_subtitle_checkbox.setEnabled(True)
            self.tts_product_time_checkbox.setEnabled(not is_liuliang and not self.tts_yindao_radio.isChecked())
            self.tts_daihuo_radio.setEnabled(True)
            self.tts_liuliang_radio.setEnabled(True)
            self.tts_yindao_radio.setEnabled(True)

            # Restore subtitle generation method controls
            is_subtitle_checked = self.tts_subtitle_checkbox.isChecked()
            self.tts_subtitle_api_radio.setEnabled(is_subtitle_checked)
            self.tts_subtitle_local_radio.setEnabled(is_subtitle_checked)

            is_local = self.tts_subtitle_local_radio.isChecked()
            self.tts_local_model_combo.setEnabled(is_subtitle_checked and is_local)
            self.tts_local_device_combo.setEnabled(is_subtitle_checked and is_local)

            self.tts_status_text.setText("没有运行项目...")
        elif state == "running":
            self.tts_start_btn.setEnabled(False)
            self.tts_pause_btn.setEnabled(True)
            self.tts_resume_btn.setEnabled(False)
            self.tts_stop_btn.setEnabled(True)
            self.tts_refresh_btn.setEnabled(False)
            self.tts_count_spin.setEnabled(False)
            self.tts_concurrent_spin.setEnabled(False)
            self.tts_folder_list.setEnabled(False)
            self.tts_subtitle_checkbox.setEnabled(False)
            self.tts_product_time_checkbox.setEnabled(False)
            self.tts_daihuo_radio.setEnabled(False)
            self.tts_liuliang_radio.setEnabled(False)
            self.tts_yindao_radio.setEnabled(False)
            self.tts_subtitle_api_radio.setEnabled(False)
            self.tts_subtitle_local_radio.setEnabled(False)
            self.tts_local_model_combo.setEnabled(False)
            self.tts_local_device_combo.setEnabled(False)
        elif state == "paused":
            self.tts_start_btn.setEnabled(False)
            self.tts_pause_btn.setEnabled(False)
            self.tts_resume_btn.setEnabled(True)
            self.tts_stop_btn.setEnabled(True)
            self.tts_status_text.setText("已暂停")

    def _on_tts_start(self):
        if not self.config.tts_api.api_key:
            QMessageBox.warning(self, "提示", "请先在设置页面配置语音生成 API Key")
            return

        if (
            self.tts_subtitle_local_radio.isChecked()
            and self.tts_subtitle_checkbox.isChecked()
        ):
            if not self._check_whisper_model(self.tts_local_model_combo.currentText()):
                return

        if self.tts_liuliang_radio.isChecked():
            self._on_tts_start_liuliang()
        elif self.tts_yindao_radio.isChecked():
            self._on_tts_start_yindao()
        else:
            self._on_tts_start_daihuo()

    def _on_tts_start_liuliang(self):
        """流量文案模式的语音生成"""
        max_count = self.tts_count_spin.value()
        max_concurrent = self.tts_concurrent_spin.value()

        # 获取随机文案文件
        liuliang_files = self._get_random_liuliang_files(max_count)
        if not liuliang_files:
            QMessageBox.warning(self, "提示", "流量文案文件夹中没有可用的txt文件")
            return

        subtitle_enabled = self.tts_subtitle_checkbox.isChecked()

        # Check subtitle API config if subtitle is enabled and using API method
        if subtitle_enabled:
            is_using_api = self.tts_subtitle_api_radio.isChecked()
            if is_using_api and not self.config.subtitle_api.api_key:
                QMessageBox.warning(self, "提示", "请先在设置页面配置字幕生成 API Key")
                return

        # Save checkbox states
        self.config.last_tts_subtitle_correction_enabled = self.tts_subtitle_correction_checkbox.isChecked()
        self.config.save()

        self.tts_log_area.clear()
        self.tts_progress_bar.setValue(0)
        self.tts_stats_label.setText("已完成: 0/0  失败: 0  已保存: 0")

        api_client = TTSAPIClient(
            base_url=self.config.tts_api.base_url,
            api_key=self.config.tts_api.api_key,
            model=self.config.tts_api.model,
            voice=self.config.tts_api.voice,
            speed=self.config.tts_api.speed,
        )

        subtitle_api_client = None
        if subtitle_enabled:
            subtitle_api_client = SubtitleAPIClient(
                base_url=self.config.subtitle_api.base_url,
                api_key=self.config.subtitle_api.api_key,
                model=self.config.subtitle_api.model,
                language=self.config.subtitle_api.language,
            )

        # 确保输出目录存在
        os.makedirs(self.liuliang_output_dir, exist_ok=True)

        self.tts_task_manager = TTSTaskManager(
            api_client=api_client,
            input_dir=self.copywriting_save_dir,  # 视频文案目录
            output_dir=self.liuliang_output_dir,  # 流量语音输出目录
            recycle_dir=self.recycle_dir,
            max_concurrent=max_concurrent,
            max_retries=self.config.tts_api.max_retries,
            subtitle_enabled=subtitle_enabled,
            subtitle_api_client=subtitle_api_client,
            subtitle_method="local" if self.tts_subtitle_local_radio.isChecked() else "api",
            local_model=self.tts_local_model_combo.currentText(),
            local_device=self.tts_local_device_combo.currentText(),
            product_time_enabled=False,
            product_time_api_client=None,
            force_simplified=self.config.subtitle_api.force_simplified,
            max_chars_per_segment=self.config.subtitle_api.max_chars_per_segment,
            subtitle_correction_enabled=self.tts_subtitle_correction_checkbox.isChecked(),
        )

        self.tts_start_time = time.time()

        # 使用流量文案专用的 worker
        self.tts_worker = TTSLiuliangAsyncWorker(
            self.tts_task_manager,
            liuliang_files,
            self.recycle_dir,
        )
        self.tts_worker.log_signal.connect(self._tts_log)
        self.tts_worker.progress_signal.connect(self._update_tts_progress)
        self.tts_worker.finished_signal.connect(self._on_tts_task_finished)
        self.tts_worker.start()

        self._set_tts_buttons_state("running")
        self._tts_log(
            f"开始流量语音生成任务: {len(liuliang_files)} 个文件, "
            f"并发数: {max_concurrent}",
            "info"
        )

    def _on_tts_start_yindao(self):
        """引导文案模式的语音生成"""
        max_count = self.tts_count_spin.value()
        max_concurrent = self.tts_concurrent_spin.value()

        # 获取随机文案文件
        yindao_files = self._get_random_yindao_files(max_count)
        if not yindao_files:
            QMessageBox.warning(self, "提示", "引导文案文件夹中没有可用的txt文件")
            return

        subtitle_enabled = self.tts_subtitle_checkbox.isChecked()

        # Check subtitle API config if subtitle is enabled and using API method
        if subtitle_enabled:
            is_using_api = self.tts_subtitle_api_radio.isChecked()
            if is_using_api and not self.config.subtitle_api.api_key:
                QMessageBox.warning(self, "提示", "请先在设置页面配置字幕生成 API Key")
                return

        # Save checkbox states
        self.config.last_tts_subtitle_correction_enabled = self.tts_subtitle_correction_checkbox.isChecked()
        self.config.save()

        self.tts_log_area.clear()
        self.tts_progress_bar.setValue(0)
        self.tts_stats_label.setText("已完成: 0/0  失败: 0  已保存: 0")

        api_client = TTSAPIClient(
            base_url=self.config.tts_api.base_url,
            api_key=self.config.tts_api.api_key,
            model=self.config.tts_api.model,
            voice=self.config.tts_api.voice,
            speed=self.config.tts_api.speed,
        )

        subtitle_api_client = None
        if subtitle_enabled:
            subtitle_api_client = SubtitleAPIClient(
                base_url=self.config.subtitle_api.base_url,
                api_key=self.config.subtitle_api.api_key,
                model=self.config.subtitle_api.model,
                language=self.config.subtitle_api.language,
            )

        # 确保输出目录存在
        os.makedirs(self.yindao_output_dir, exist_ok=True)

        self.tts_task_manager = TTSTaskManager(
            api_client=api_client,
            input_dir=self.copywriting_save_dir,
            output_dir=self.yindao_output_dir,
            recycle_dir=self.recycle_dir,
            max_concurrent=max_concurrent,
            max_retries=self.config.tts_api.max_retries,
            subtitle_enabled=subtitle_enabled,
            subtitle_api_client=subtitle_api_client,
            subtitle_method="local" if self.tts_subtitle_local_radio.isChecked() else "api",
            local_model=self.tts_local_model_combo.currentText(),
            local_device=self.tts_local_device_combo.currentText(),
            product_time_enabled=False,
            product_time_api_client=None,
            force_simplified=self.config.subtitle_api.force_simplified,
            max_chars_per_segment=self.config.subtitle_api.max_chars_per_segment,
            subtitle_correction_enabled=self.tts_subtitle_correction_checkbox.isChecked(),
        )

        self.tts_start_time = time.time()

        self.tts_worker = TTSLiuliangAsyncWorker(
            self.tts_task_manager,
            yindao_files,
            self.recycle_dir,
        )
        self.tts_worker.log_signal.connect(self._tts_log)
        self.tts_worker.progress_signal.connect(self._update_tts_progress)
        self.tts_worker.finished_signal.connect(self._on_tts_task_finished)
        self.tts_worker.start()

        self._set_tts_buttons_state("running")
        self._tts_log(
            f"开始引导语音生成任务: {len(yindao_files)} 个文件, "
            f"并发数: {max_concurrent}",
            "info"
        )

    def _on_tts_start_daihuo(self):
        """带货文案模式的语音生成"""
        selected_folders = self._get_tts_selected_folders()
        if not selected_folders:
            QMessageBox.warning(self, "提示", "请选择至少一个合并文案子文件夹")
            return

        subtitle_enabled = self.tts_subtitle_checkbox.isChecked()
        product_time_enabled = self.tts_product_time_checkbox.isChecked()

        # Check subtitle API config if subtitle is enabled and using API method
        if subtitle_enabled:
            is_using_api = self.tts_subtitle_api_radio.isChecked()
            if is_using_api and not self.config.subtitle_api.api_key:
                QMessageBox.warning(self, "提示", "请先在设置页面配置字幕生成 API Key")
                return

        # Check product time API config if product time is enabled
        if product_time_enabled and not self.config.product_time_api.api_key:
            QMessageBox.warning(self, "提示", "请先在设置页面配置时间段识别 API Key")
            return

        # Save checkbox states
        self.config.last_tts_subtitle_enabled = subtitle_enabled
        self.config.last_tts_product_time_enabled = product_time_enabled
        self.config.last_tts_subtitle_correction_enabled = self.tts_subtitle_correction_checkbox.isChecked()
        self.config.save()

        max_count = self.tts_count_spin.value()
        max_concurrent = self.tts_concurrent_spin.value()

        self.tts_log_area.clear()
        self.tts_progress_bar.setValue(0)
        self.tts_stats_label.setText("已完成: 0/0  失败: 0  已保存: 0")

        api_client = TTSAPIClient(
            base_url=self.config.tts_api.base_url,
            api_key=self.config.tts_api.api_key,
            model=self.config.tts_api.model,
            voice=self.config.tts_api.voice,
            speed=self.config.tts_api.speed,
        )

        subtitle_api_client = None
        if subtitle_enabled:
            subtitle_api_client = SubtitleAPIClient(
                base_url=self.config.subtitle_api.base_url,
                api_key=self.config.subtitle_api.api_key,
                model=self.config.subtitle_api.model,
                language=self.config.subtitle_api.language,
            )

        product_time_api_client = None
        if product_time_enabled:
            product_time_api_client = ProductTimeAPIClient(
                base_url=self.config.product_time_api.base_url,
                api_key=self.config.product_time_api.api_key,
                model=self.config.product_time_api.model,
                prompt=self.config.product_time_api.prompt,
            )

        self.tts_task_manager = TTSTaskManager(
            api_client=api_client,
            input_dir=self.merge_copywriting_output_dir,
            output_dir=self.tts_output_dir,
            recycle_dir=self.recycle_dir,
            max_concurrent=max_concurrent,
            max_retries=self.config.tts_api.max_retries,
            subtitle_enabled=subtitle_enabled,
            subtitle_api_client=subtitle_api_client,
            subtitle_method="local" if self.tts_subtitle_local_radio.isChecked() else "api",
            local_model=self.tts_local_model_combo.currentText(),
            local_device=self.tts_local_device_combo.currentText(),
            product_time_enabled=product_time_enabled,
            product_time_api_client=product_time_api_client,
            force_simplified=self.config.subtitle_api.force_simplified,
            max_chars_per_segment=self.config.subtitle_api.max_chars_per_segment,
            subtitle_correction_enabled=self.tts_subtitle_correction_checkbox.isChecked(),
        )

        self.tts_start_time = time.time()

        self.tts_worker = TTSAsyncWorker(
            self.tts_task_manager,
            selected_folders,
            max_count,
        )
        self.tts_worker.log_signal.connect(self._tts_log)
        self.tts_worker.progress_signal.connect(self._update_tts_progress)
        self.tts_worker.finished_signal.connect(self._on_tts_task_finished)
        self.tts_worker.start()

        self._set_tts_buttons_state("running")
        extra_info = ""
        if subtitle_enabled:
            extra_info += " (含字幕)"
        if product_time_enabled:
            extra_info += " (含时间段识别)"
        if self.tts_subtitle_correction_checkbox.isChecked():
            extra_info += " (含字幕校正)"
        self._tts_log(
            f"开始语音生成任务{extra_info}: {len(selected_folders)} 个文件夹, "
            f"最大生成数: {max_count}, 并发数: {max_concurrent}",
            "info"
        )

    def _get_random_liuliang_files(self, count: int) -> list:
        """从流量文案文件夹随机抽取指定数量的txt文件"""
        if count <= 0:
            return []
        if not os.path.exists(self.liuliang_copywriting_dir):
            return []
        txt_files = [
            f for f in os.listdir(self.liuliang_copywriting_dir)
            if f.endswith('.txt')
        ]
        if not txt_files:
            return []
        # 抽取数量不超过可用文件数
        sample_count = min(count, len(txt_files))
        selected = random.sample(txt_files, sample_count)
        return [os.path.join(self.liuliang_copywriting_dir, f) for f in selected]

    def _get_random_yindao_files(self, count: int) -> list:
        """从引导文案文件夹随机抽取指定数量的txt文件"""
        if count <= 0:
            return []
        if not os.path.exists(self.yindao_copywriting_dir):
            return []
        txt_files = [
            f for f in os.listdir(self.yindao_copywriting_dir)
            if f.endswith('.txt')
        ]
        if not txt_files:
            return []
        sample_count = min(count, len(txt_files))
        selected = random.sample(txt_files, sample_count)
        return [os.path.join(self.yindao_copywriting_dir, f) for f in selected]

    def _on_tts_pause(self):
        if self.tts_task_manager:
            self.tts_task_manager.pause()
            self._set_tts_buttons_state("paused")
            self._tts_log("任务已暂停", "warning")

    def _on_tts_resume(self):
        if self.tts_task_manager:
            self.tts_task_manager.resume()
            self._set_tts_buttons_state("running")
            self._tts_log("任务已继续", "info")

    def _on_tts_stop(self):
        if self.tts_task_manager:
            self.tts_task_manager.stop()
            self._tts_log("正在停止任务...", "warning")

    def _on_fix_subtitle_batch(self):
        """Scan output and input/视频配音 directories for SRT files and batch fix."""
        from ..core.subtitle_batch_fix import batch_fix_srt_files

        dirs_to_scan = [
            os.path.join(self.project_dir, "output"),
            os.path.join(self.project_dir, "input", "视频配音"),
        ]
        dirs_to_scan = [d for d in dirs_to_scan if os.path.isdir(d)]

        if not dirs_to_scan:
            self._tts_log("未找到可扫描的目录", "warning")
            return

        self.tts_fix_subtitle_btn.setEnabled(False)
        self._tts_log("开始批量修复字幕断句...", "info")

        try:
            stats = batch_fix_srt_files(dirs_to_scan, max_chars=12)
            self._tts_log(
                f"字幕修复完成: 共扫描 {stats['total']} 个文件, "
                f"修复 {stats['modified']} 个, 失败 {stats['failed']} 个",
                "success" if stats["failed"] == 0 else "warning",
            )
        except Exception as e:
            self._tts_log(f"批量修复出错: {e}", "error")
        finally:
            self.tts_fix_subtitle_btn.setEnabled(True)

    def _on_tts_task_finished(self, progress: TTSTaskProgress):
        self._set_tts_buttons_state("idle")

        if progress:
            msg = f"任务完成! 已保存: {progress.saved_files} 个文件, 失败: {progress.failed_tasks}"
            if self.tts_subtitle_checkbox.isChecked():
                expected_subtitles = progress.saved_files
                actual_subtitles = progress.subtitle_completed
                missing = expected_subtitles - actual_subtitles - progress.subtitle_failed
                if missing < 0:
                    missing = 0
                msg += f", 字幕: {progress.subtitle_completed}成功/{progress.subtitle_failed}失败"
                if missing > 0:
                    msg += f"/{missing}未生成"
            elif progress.subtitle_completed > 0 or progress.subtitle_failed > 0:
                msg += f", 字幕: {progress.subtitle_completed}成功/{progress.subtitle_failed}失败"
            if progress.product_time_completed > 0 or progress.product_time_failed > 0:
                msg += f", 时间段: {progress.product_time_completed}成功/{progress.product_time_failed}失败"
            self._tts_log(msg, "success")
        else:
            self._tts_log("任务异常结束", "error")

        self.tts_task_manager = None
        self.tts_worker = None

    # Video Compose methods
    def _create_video_compose_tab(self) -> QWidget:
        """Create video compose tab with left-right split layout"""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(6)

        # Top area: left-right split
        top_splitter = QSplitter(Qt.Horizontal)

        # Left panel: folder selection
        left_panel = self._create_video_compose_folder_panel()
        top_splitter.addWidget(left_panel)

        # Right panel: settings + buttons
        right_panel = self._create_video_compose_settings_panel()
        top_splitter.addWidget(right_panel)

        # Set split ratio 1:2
        top_splitter.setSizes([300, 600])
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 2)

        main_layout.addWidget(top_splitter, 1)

        # Bottom: progress area
        progress_frame = self._create_video_compose_progress_area()
        main_layout.addWidget(progress_frame)

        # Status bar
        status_bar = self._create_video_compose_status_bar()
        main_layout.addWidget(status_bar)

        # Log area
        log_frame = self._create_video_compose_log_area()
        main_layout.addWidget(log_frame)

        # Initialize folder list
        self._refresh_video_compose_folders()

        return widget

    def _create_video_compose_folder_panel(self) -> QFrame:
        """Create left panel for folder selection"""
        frame = QFrame()
        frame.setObjectName("video_compose_folder_panel")
        frame.setStyleSheet("""
            QFrame#video_compose_folder_panel {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
            }
        """)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        # Title
        title = QLabel("配音子文件夹选择")
        title.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        title.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(title)

        # Folder list
        self.video_compose_folder_list = QListWidget()
        self.video_compose_folder_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.video_compose_folder_list.setFont(QFont("Microsoft YaHei", 10))
        self.video_compose_folder_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #d0d0d0;
                background-color: #fafafa;
            }
            QListWidget::item {
                padding: 3px;
            }
            QListWidget::item:selected {
                background-color: #e8f4fc;
                color: #333333;
            }
        """)
        layout.addWidget(self.video_compose_folder_list, 1)

        return frame

    def _create_video_compose_settings_panel(self) -> QFrame:
        """Create right panel for settings and buttons"""
        frame = QFrame()
        frame.setObjectName("video_compose_settings_panel")
        frame.setStyleSheet("""
            QFrame#video_compose_settings_panel {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
            }
        """)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Styles
        spin_style = """
            QSpinBox, QDoubleSpinBox {
                border: 1px solid #d0d0d0;
                padding: 1px 4px;
                background: #ffffff;
                min-width: 65px;
                min-height: 28px;
            }
        """
        combo_style = """
            QComboBox {
                border: 1px solid #d0d0d0;
                padding: 1px 4px;
                background: #ffffff;
                min-width: 100px;
                min-height: 28px;
            }
        """

        # --- GroupBox: 基础参数 ---
        basic_group = QGroupBox("基础参数")
        basic_group.setStyleSheet(Styles.SETTINGS_GROUPBOX)
        basic_grid = QGridLayout(basic_group)
        basic_grid.setSpacing(8)
        basic_grid.setColumnStretch(0, 1)
        basic_grid.setColumnStretch(1, 1)
        basic_grid.setColumnStretch(2, 1)
        basic_grid.setColumnStretch(3, 1)
        basic_grid.addWidget(self._create_spin_param("生成数量:", "video_compose_count_spin",
                             1, 1000, 10, spin_style), 0, 0)
        basic_grid.addWidget(self._create_spin_param("并发数:", "video_compose_concurrent_spin",
                             1, 5, 2, spin_style), 0, 1)
        basic_grid.addWidget(self._create_double_spin_range_param("片段时长:", "video_compose_clip_duration_min_spin",
                             "video_compose_clip_duration_max_spin",
                             1.0, 60.0, 5.0, 10.0, spin_style, "秒"), 0, 2)
        basic_grid.addWidget(self._create_combo_param("分辨率:", "video_compose_resolution_combo",
                             [("1080p竖屏", (1080, 1920)), ("1080p横屏", (1920, 1080)),
                              ("720p竖屏", (720, 1280)), ("720p横屏", (1280, 720))], combo_style), 0, 3)
        layout.addWidget(basic_group)

        # --- GroupBox: 商品素材 ---
        product_group = QGroupBox("商品素材")
        product_group.setStyleSheet(Styles.SETTINGS_GROUPBOX)
        product_grid = QGridLayout(product_group)
        product_grid.setSpacing(8)
        product_grid.setColumnStretch(0, 1)
        product_grid.setColumnStretch(1, 1)
        product_grid.setColumnStretch(2, 1)
        product_grid.setColumnStretch(3, 1)
        product_grid.addWidget(self._create_spin_param("商品视频数量:", "video_compose_product_video_count_spin",
                               0, 10, 2, spin_style), 0, 0)
        product_grid.addWidget(self._create_spin_param("商品图片数量:", "video_compose_product_image_count_spin",
                               0, 10, 2, spin_style), 0, 1)
        product_grid.addWidget(self._create_double_spin_range_param("商品图片时长:", "video_compose_product_image_duration_min_spin",
                               "video_compose_product_image_duration_max_spin",
                               1.0, 30.0, 2.0, 5.0, spin_style, "秒"), 0, 2)

        self.video_compose_priority_video_checkbox = QCheckBox("优先视频")
        self.video_compose_priority_video_checkbox.setFont(QFont("Microsoft YaHei", 9))
        self.video_compose_priority_video_checkbox.setChecked(True)
        product_grid.addWidget(self.video_compose_priority_video_checkbox, 0, 3)
        layout.addWidget(product_group)

        # --- GroupBox: 音频设置 ---
        audio_group = QGroupBox("音频设置")
        audio_group.setStyleSheet(Styles.SETTINGS_GROUPBOX)
        audio_grid = QGridLayout(audio_group)
        audio_grid.setSpacing(8)
        audio_grid.setColumnStretch(0, 1)
        audio_grid.setColumnStretch(1, 1)
        audio_grid.setColumnStretch(2, 1)
        audio_grid.setColumnStretch(3, 1)
        audio_grid.addWidget(self._create_slider_param("背景音量:", "video_compose_bgm_slider",
                             0, 100, 20), 0, 0)
        audio_grid.addWidget(self._create_slider_param("配音音量:", "video_compose_voice_slider",
                             0, 500, 100), 0, 1)
        layout.addWidget(audio_group)

        # --- GroupBox: 效果设置 ---
        effect_group = QGroupBox("效果设置")
        effect_group.setStyleSheet(Styles.SETTINGS_GROUPBOX)
        effect_grid = QGridLayout(effect_group)
        effect_grid.setSpacing(8)
        effect_grid.setColumnStretch(0, 1)
        effect_grid.setColumnStretch(1, 1)
        effect_grid.setColumnStretch(2, 1)
        effect_grid.setColumnStretch(3, 1)
        # Row 0: 字幕设置, 模糊边框, 叠加素材, 画中画
        effect_grid.addWidget(self._create_subtitle_param(), 0, 0)
        effect_grid.addWidget(self._create_compose_blurred_border_param(), 0, 1)
        effect_grid.addWidget(self._create_compose_overlay_material_param(), 0, 2)
        effect_grid.addWidget(self._create_compose_pip_param(), 0, 3)
        # Row 1: 叠加模式, 叠加效果, 效果强度
        self.video_compose_overlay_mode_checkbox = QCheckBox("叠加模式")
        self.video_compose_overlay_mode_checkbox.setFont(QFont("Microsoft YaHei", 9))
        self.video_compose_overlay_mode_checkbox.setChecked(True)
        self.video_compose_overlay_mode_checkbox.setToolTip("勾选后商品视频叠加在主视频上方，不勾选则替换主视频")
        self.video_compose_overlay_mode_checkbox.stateChanged.connect(
            self._on_overlay_mode_changed
        )
        effect_grid.addWidget(self.video_compose_overlay_mode_checkbox, 1, 0)
        effect_type_widget = self._create_combo_param("叠加效果:", "video_compose_effect_combo",
                             [("无效果", "none"), ("背景模糊", "blur"), ("黑色蒙版", "mask")], combo_style)
        self.video_compose_effect_combo.setToolTip("叠加模式下商品视频显示时的背景效果")
        self.video_compose_effect_combo.currentIndexChanged.connect(self._on_effect_type_changed)
        effect_grid.addWidget(effect_type_widget, 1, 1)
        slider_widget = self._create_slider_param("效果强度:", "video_compose_effect_slider", 0, 100, 20)
        self.video_compose_effect_slider.setToolTip("背景模糊强度或蒙版透明度")
        self.video_compose_effect_slider.setEnabled(False)
        effect_grid.addWidget(slider_widget, 1, 2)
        layout.addWidget(effect_group)

        layout.addStretch()

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)

        btn_style = """
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 4px 12px;
                min-height: 32px;
            }
            QPushButton:hover { background-color: #e8f4fc; }
            QPushButton:disabled { color: #999999; background-color: #f0f0f0; }
        """
        primary_btn_style = """
            QPushButton {
                color: #ffffff;
                background-color: #0066cc;
                border: 1px solid #0055aa;
                padding: 4px 15px;
                min-height: 32px;
            }
            QPushButton:hover { background-color: #0055aa; }
            QPushButton:disabled { background-color: #cccccc; }
        """
        stop_btn_style = """
            QPushButton {
                color: #cc0000;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 4px 12px;
                min-height: 32px;
            }
            QPushButton:hover { background-color: #ffeeee; }
            QPushButton:disabled { color: #999999; background-color: #f0f0f0; }
        """

        self.video_compose_refresh_btn = QPushButton("刷新")
        self.video_compose_refresh_btn.setFont(QFont("Microsoft YaHei", 9))
        self.video_compose_refresh_btn.setStyleSheet(btn_style)
        self.video_compose_refresh_btn.clicked.connect(self._refresh_video_compose_folders)

        self.video_compose_start_btn = QPushButton("开始合成")
        self.video_compose_start_btn.setFont(QFont("Microsoft YaHei", 9))
        self.video_compose_start_btn.setStyleSheet(primary_btn_style)
        self.video_compose_start_btn.clicked.connect(self._on_video_compose_start)

        self.video_compose_pause_btn = QPushButton("暂停")
        self.video_compose_pause_btn.setFont(QFont("Microsoft YaHei", 9))
        self.video_compose_pause_btn.setStyleSheet(btn_style)
        self.video_compose_pause_btn.setEnabled(False)
        self.video_compose_pause_btn.clicked.connect(self._on_video_compose_pause)

        self.video_compose_resume_btn = QPushButton("继续")
        self.video_compose_resume_btn.setFont(QFont("Microsoft YaHei", 9))
        self.video_compose_resume_btn.setStyleSheet(btn_style)
        self.video_compose_resume_btn.setEnabled(False)
        self.video_compose_resume_btn.clicked.connect(self._on_video_compose_resume)

        self.video_compose_stop_btn = QPushButton("停止")
        self.video_compose_stop_btn.setFont(QFont("Microsoft YaHei", 9))
        self.video_compose_stop_btn.setStyleSheet(stop_btn_style)
        self.video_compose_stop_btn.setEnabled(False)
        self.video_compose_stop_btn.clicked.connect(self._on_video_compose_stop)

        # 打开输出文件夹按钮
        open_folder_btn_style = """
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                min-height: 28px;
            }
            QPushButton:hover { background-color: #138496; }
        """
        self.video_compose_open_folder_btn = QPushButton("打开输出文件夹")
        self.video_compose_open_folder_btn.setFont(QFont("Microsoft YaHei", 9))
        self.video_compose_open_folder_btn.setStyleSheet(open_folder_btn_style)
        self.video_compose_open_folder_btn.clicked.connect(self._on_video_compose_open_folder)

        btn_layout.addWidget(self.video_compose_refresh_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.video_compose_start_btn)
        btn_layout.addWidget(self.video_compose_pause_btn)
        btn_layout.addWidget(self.video_compose_resume_btn)
        btn_layout.addWidget(self.video_compose_stop_btn)
        btn_layout.addWidget(self.video_compose_open_folder_btn)

        layout.addLayout(btn_layout)

        return frame

    def _create_spin_param(self, label_text, attr_name, min_val, max_val, default, style):
        """Create a labeled spin box parameter widget"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel(label_text)
        label.setFont(QFont("Microsoft YaHei", 9))
        label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(label)

        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setStyleSheet(style)
        setattr(self, attr_name, spin)
        layout.addWidget(spin)

        return container

    def _create_double_spin_param(self, label_text, attr_name, min_val, max_val, default, style, suffix=None):
        """Create a labeled double spin box parameter widget"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel(label_text)
        label.setFont(QFont("Microsoft YaHei", 9))
        label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(label)

        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setStyleSheet(style)
        if suffix:
            spin.setSuffix(suffix)
        setattr(self, attr_name, spin)
        layout.addWidget(spin)

        return container

    def _create_double_spin_range_param(self, label_text, attr_name_min, attr_name_max,
                                         min_val, max_val, default_min, default_max, style, suffix=None):
        """Create a labeled min~max double spin box range parameter widget"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel(label_text)
        label.setFont(QFont("Microsoft YaHei", 9))
        label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(label)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        spin_min = QDoubleSpinBox()
        spin_min.setRange(min_val, max_val)
        spin_min.setValue(default_min)
        spin_min.setStyleSheet(style)
        if suffix:
            spin_min.setSuffix(suffix)
        setattr(self, attr_name_min, spin_min)
        row.addWidget(spin_min)

        tilde = QLabel("~")
        tilde.setFont(QFont("Microsoft YaHei", 9))
        tilde.setStyleSheet("color: #333333; border: none;")
        tilde.setFixedWidth(12)
        row.addWidget(tilde)

        spin_max = QDoubleSpinBox()
        spin_max.setRange(min_val, max_val)
        spin_max.setValue(default_max)
        spin_max.setStyleSheet(style)
        if suffix:
            spin_max.setSuffix(suffix)
        setattr(self, attr_name_max, spin_max)
        row.addWidget(spin_max)

        layout.addLayout(row)

        # Ensure min <= max
        def on_min_changed(val):
            if val > spin_max.value():
                spin_max.setValue(val)

        def on_max_changed(val):
            if val < spin_min.value():
                spin_min.setValue(val)

        spin_min.valueChanged.connect(on_min_changed)
        spin_max.valueChanged.connect(on_max_changed)

        return container

    def _create_combo_param(self, label_text, attr_name, items, style):
        """Create a labeled combo box parameter widget"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel(label_text)
        label.setFont(QFont("Microsoft YaHei", 9))
        label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(label)

        combo = QComboBox()
        combo.setFont(QFont("Microsoft YaHei", 9))
        combo.setStyleSheet(style)
        for text, data in items:
            combo.addItem(text, data)
        setattr(self, attr_name, combo)
        layout.addWidget(combo)

        return container

    def _create_slider_param(self, label_text, attr_name, min_val, max_val, default):
        """Create a labeled slider parameter widget"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel(label_text)
        label.setFont(QFont("Microsoft YaHei", 9))
        label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(label)

        slider_layout = QHBoxLayout()
        slider_layout.setSpacing(3)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default)
        slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #d0d0d0;
                height: 6px;
                background: #f0f0f0;
            }
            QSlider::handle:horizontal {
                background: #0066cc;
                width: 12px;
                margin: -3px 0;
            }
        """)
        setattr(self, attr_name, slider)

        value_label = QLabel(f"{default}%")
        value_label.setFont(QFont("Microsoft YaHei", 9))
        value_label.setFixedWidth(40)
        value_label.setStyleSheet("color: #333333; border: none;")
        setattr(self, f"{attr_name}_label", value_label)

        slider.valueChanged.connect(lambda v: value_label.setText(f"{v}%"))

        slider_layout.addWidget(slider)
        slider_layout.addWidget(value_label)
        layout.addLayout(slider_layout)

        return container

    def _create_subtitle_param(self):
        """Create subtitle settings button widget"""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel("字幕:")
        label.setFont(QFont("Microsoft YaHei", 9))
        label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(label)

        self.video_compose_subtitle_btn = QPushButton("字幕设置")
        self.video_compose_subtitle_btn.setFont(QFont("Microsoft YaHei", 9))
        self.video_compose_subtitle_btn.setStyleSheet("""
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 6px 12px;
                min-height: 28px;
            }
            QPushButton:hover { background-color: #e8f4fc; }
        """)
        self.video_compose_subtitle_btn.clicked.connect(self._on_video_compose_subtitle_settings)
        layout.addWidget(self.video_compose_subtitle_btn)

        return container

    def _create_compose_blurred_border_param(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel("模糊边框:")
        label.setFont(QFont("Microsoft YaHei", 9))
        label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(label)

        self.compose_blurred_border_btn = QPushButton("模糊边框设置")
        self.compose_blurred_border_btn.setFont(QFont("Microsoft YaHei", 9))
        self.compose_blurred_border_btn.setStyleSheet("""
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 6px 12px;
                min-height: 28px;
            }
            QPushButton:hover { background-color: #e8f4fc; }
        """)
        self.compose_blurred_border_btn.clicked.connect(self._on_compose_blurred_border_settings)
        layout.addWidget(self.compose_blurred_border_btn)

        return container

    def _create_compose_overlay_material_param(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel("叠加素材:")
        label.setFont(QFont("Microsoft YaHei", 9))
        label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(label)

        self.compose_overlay_material_btn = QPushButton("叠加素材设置")
        self.compose_overlay_material_btn.setFont(QFont("Microsoft YaHei", 9))
        self.compose_overlay_material_btn.setStyleSheet("""
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 6px 12px;
                min-height: 28px;
            }
            QPushButton:hover { background-color: #e8f4fc; }
        """)
        self.compose_overlay_material_btn.clicked.connect(self._on_compose_overlay_material_settings)
        layout.addWidget(self.compose_overlay_material_btn)

        return container

    def _create_compose_pip_param(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel("画中画:")
        label.setFont(QFont("Microsoft YaHei", 9))
        label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(label)

        self.compose_pip_btn = QPushButton("画中画设置")
        self.compose_pip_btn.setFont(QFont("Microsoft YaHei", 9))
        self.compose_pip_btn.setStyleSheet("""
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 6px 12px;
                min-height: 28px;
            }
            QPushButton:hover { background-color: #e8f4fc; }
        """)
        self.compose_pip_btn.clicked.connect(self._on_compose_pip_settings)
        layout.addWidget(self.compose_pip_btn)

        return container

    def _create_video_compose_progress_area(self) -> QFrame:
        """Create progress bar area"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
            }
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)

        # Progress bar
        self.video_compose_progress_bar = QProgressBar()
        self.video_compose_progress_bar.setRange(0, 100)
        self.video_compose_progress_bar.setValue(0)
        self.video_compose_progress_bar.setFixedHeight(12)
        self.video_compose_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                text-align: center;
                background-color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #0066cc;
            }
        """)
        layout.addWidget(self.video_compose_progress_bar, 1)

        # Stats label
        self.video_compose_stats_label = QLabel("已完成: 0/0  失败: 0")
        self.video_compose_stats_label.setFont(QFont("Microsoft YaHei", 9))
        self.video_compose_stats_label.setStyleSheet("color: #666666; border: none;")
        self.video_compose_stats_label.setMinimumWidth(150)
        layout.addWidget(self.video_compose_stats_label)

        return frame

    def _create_video_compose_status_bar(self) -> QFrame:
        frame = QFrame()
        frame.setFixedHeight(18)
        frame.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border: 1px solid #d0d0d0;
            }
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(6, 1, 6, 1)

        self.video_compose_status_text = QLabel("没有运行项目...")
        self.video_compose_status_text.setFont(QFont("Microsoft YaHei", 9))
        self.video_compose_status_text.setStyleSheet(
            "color: #0066cc; border: none; background: transparent;"
        )
        layout.addWidget(self.video_compose_status_text)

        layout.addStretch()

        return frame

    def _create_video_compose_log_area(self) -> QFrame:
        frame = QFrame()
        frame.setMinimumHeight(120)
        frame.setMaximumHeight(200)
        frame.setStyleSheet("""
            QFrame#video_compose_log_frame {
                background-color: #1e1e1e;
                border: 1px solid #333333;
            }
        """)
        frame.setObjectName("video_compose_log_frame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel(" 日志")
        header.setFixedHeight(14)
        header.setFont(QFont("Microsoft YaHei", 9))
        header.setStyleSheet(
            "color: #888888; background-color: #2d2d2d; border: none; padding-left: 8px;"
        )
        layout.addWidget(header)

        self.video_compose_log_area = QTextEdit()
        self.video_compose_log_area.setReadOnly(True)
        self.video_compose_log_area.setFont(QFont("Consolas", 10))
        self.video_compose_log_area.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #00ff00;
                border: none;
                padding: 3px;
            }
        """)
        layout.addWidget(self.video_compose_log_area)

        return frame

    def _refresh_video_compose_folders(self):
        """Refresh the video compose folder list"""
        self.video_compose_folder_list.clear()

        if not os.path.exists(self.tts_output_dir):
            os.makedirs(self.tts_output_dir, exist_ok=True)
            return

        folders = []
        for name in sorted(os.listdir(self.tts_output_dir)):
            folder_path = os.path.join(self.tts_output_dir, name)
            if os.path.isdir(folder_path):
                # Count audio files in folder
                audio_count = 0
                for f in os.listdir(folder_path):
                    ext = os.path.splitext(f)[1].lower()
                    if ext in {'.mp3', '.wav', '.aac', '.m4a', '.flac'}:
                        audio_count += 1
                folders.append((name, audio_count))

        for folder, count in folders:
            item = QListWidgetItem(f"{folder} ({count}个配音)")
            item.setData(Qt.UserRole, folder)
            self.video_compose_folder_list.addItem(item)

    def _get_video_compose_selected_folders(self) -> list:
        """Get list of selected folder names for video compose"""
        selected = []
        for item in self.video_compose_folder_list.selectedItems():
            folder_name = item.data(Qt.UserRole)
            selected.append(folder_name)
        return selected

    def _video_compose_log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")

        color_map = {
            "info": "#00ff00",
            "warning": "#ffff00",
            "error": "#ff0000",
            "success": "#00ff00",
        }
        color = color_map.get(level, "#00ff00")

        html = f'<span style="color: #888888;">[{timestamp}]</span> '
        html += f'<span style="color: {color};">{message}</span>'
        self.video_compose_log_area.append(html)

        cursor = self.video_compose_log_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.video_compose_log_area.setTextCursor(cursor)

    def _update_video_compose_progress(self, progress: VideoComposeTaskProgress):
        if progress.total_tasks > 0:
            percent = int(progress.completed_tasks / progress.total_tasks * 100)
            self.video_compose_progress_bar.setValue(percent)

        self.video_compose_stats_label.setText(
            f"已完成: {progress.completed_tasks}/{progress.total_tasks}  "
            f"失败: {progress.failed_tasks}"
        )

        if progress.current_task:
            self.video_compose_status_text.setText(
                f"正在处理: {progress.current_folder}/{progress.current_task}"
            )

    def _set_video_compose_buttons_state(self, state: str):
        if state == "idle":
            self.video_compose_start_btn.setEnabled(True)
            self.video_compose_pause_btn.setEnabled(False)
            self.video_compose_resume_btn.setEnabled(False)
            self.video_compose_stop_btn.setEnabled(False)
            self.video_compose_refresh_btn.setEnabled(True)
            self.video_compose_count_spin.setEnabled(True)
            self.video_compose_concurrent_spin.setEnabled(True)
            self.video_compose_clip_duration_min_spin.setEnabled(True)
            self.video_compose_clip_duration_max_spin.setEnabled(True)
            self.video_compose_bgm_slider.setEnabled(True)
            self.video_compose_voice_slider.setEnabled(True)
            self.video_compose_resolution_combo.setEnabled(True)
            self.video_compose_subtitle_btn.setEnabled(True)
            self.video_compose_folder_list.setEnabled(True)
            self.video_compose_status_text.setText("没有运行项目...")
        elif state == "running":
            self.video_compose_start_btn.setEnabled(False)
            self.video_compose_pause_btn.setEnabled(True)
            self.video_compose_resume_btn.setEnabled(False)
            self.video_compose_stop_btn.setEnabled(True)
            self.video_compose_refresh_btn.setEnabled(False)
            self.video_compose_count_spin.setEnabled(False)
            self.video_compose_concurrent_spin.setEnabled(False)
            self.video_compose_clip_duration_min_spin.setEnabled(False)
            self.video_compose_clip_duration_max_spin.setEnabled(False)
            self.video_compose_bgm_slider.setEnabled(False)
            self.video_compose_voice_slider.setEnabled(False)
            self.video_compose_resolution_combo.setEnabled(False)
            self.video_compose_subtitle_btn.setEnabled(False)
            self.video_compose_folder_list.setEnabled(False)
        elif state == "paused":
            self.video_compose_start_btn.setEnabled(False)
            self.video_compose_pause_btn.setEnabled(False)
            self.video_compose_resume_btn.setEnabled(True)
            self.video_compose_stop_btn.setEnabled(True)
            self.video_compose_status_text.setText("已暂停")

    def _on_video_compose_subtitle_settings(self):
        """Open subtitle settings dialog"""
        from .subtitle_settings_dialog import SubtitleSettingsDialog
        from PyQt5.QtWidgets import QDialog

        dialog = SubtitleSettingsDialog(
            self.config.subtitle_style,
            self.config.subtitle_style_templates,
            self.save_dir,
            self
        )

        if dialog.exec_() == QDialog.Accepted:
            self.config.subtitle_style = dialog.get_style()
            self.config.subtitle_style_templates = dialog.get_templates()
            self.config.save()

    def _on_compose_blurred_border_settings(self):
        from .blurred_border_settings_dialog import BlurredBorderSettingsDialog
        from PyQt5.QtWidgets import QDialog

        dialog = BlurredBorderSettingsDialog(self.config.blurred_border, self)
        if dialog.exec_() == QDialog.Accepted:
            self.config.blurred_border = dialog.get_config()
            self.config.save()

    def _on_compose_overlay_material_settings(self):
        from .overlay_material_settings_dialog import OverlayMaterialSettingsDialog
        from PyQt5.QtWidgets import QDialog

        dialog = OverlayMaterialSettingsDialog(
            self.config.overlay_material, self.overlay_material_dir, self
        )
        if dialog.exec_() == QDialog.Accepted:
            self.config.overlay_material = dialog.get_config()
            self.config.save()

    def _on_compose_pip_settings(self):
        from .pip_settings_dialog import PipSettingsDialog
        from PyQt5.QtWidgets import QDialog

        dialog = PipSettingsDialog(self.config.pip, self)
        if dialog.exec_() == QDialog.Accepted:
            self.config.pip = dialog.get_config()
            self.config.save()

    def _on_missing_subtitle(self, audio_path: str) -> str:
        """Handle missing subtitle file situation"""
        audio_name = os.path.basename(audio_path)

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("缺少字幕文件")
        msg_box.setText(f"配音文件 '{audio_name}' 没有对应的字幕文件")
        msg_box.setInformativeText("请选择处理方式:")

        continue_btn = msg_box.addButton("继续合成(无字幕)", QMessageBox.AcceptRole)
        skip_btn = msg_box.addButton("跳过此文件", QMessageBox.RejectRole)
        cancel_btn = msg_box.addButton("取消全部", QMessageBox.DestructiveRole)

        msg_box.exec_()

        if msg_box.clickedButton() == continue_btn:
            return "continue"
        elif msg_box.clickedButton() == skip_btn:
            return "skip"
        else:
            return "cancel"

    def _on_overlay_mode_changed(self, state):
        """Enable/disable effect controls based on overlay mode checkbox state"""
        from PyQt5.QtCore import Qt
        enabled = state == Qt.Checked
        self.video_compose_effect_combo.setEnabled(enabled)
        effect_type = self.video_compose_effect_combo.currentData()
        self.video_compose_effect_slider.setEnabled(enabled and effect_type != "none")

    def _on_effect_type_changed(self, index):
        """Update effect slider enabled state based on selected effect type"""
        effect_type = self.video_compose_effect_combo.currentData()
        overlay_enabled = self.video_compose_overlay_mode_checkbox.isChecked()
        self.video_compose_effect_slider.setEnabled(overlay_enabled and effect_type != "none")

    def _on_video_compose_start(self):
        selected_folders = self._get_video_compose_selected_folders()
        if not selected_folders:
            QMessageBox.warning(self, "提示", "请选择至少一个配音子文件夹")
            return

        max_count = self.video_compose_count_spin.value()
        max_concurrent = self.video_compose_concurrent_spin.value()
        clip_duration_min = self.video_compose_clip_duration_min_spin.value()
        clip_duration_max = self.video_compose_clip_duration_max_spin.value()
        bgm_volume = self.video_compose_bgm_slider.value() / 100.0
        voice_volume = self.video_compose_voice_slider.value() / 100.0
        resolution = self.video_compose_resolution_combo.currentData()

        # Product video settings
        product_video_count = self.video_compose_product_video_count_spin.value()
        product_image_count = self.video_compose_product_image_count_spin.value()
        product_image_duration_min = self.video_compose_product_image_duration_min_spin.value()
        product_image_duration_max = self.video_compose_product_image_duration_max_spin.value()
        priority_video = self.video_compose_priority_video_checkbox.isChecked()
        overlay_mode = self.video_compose_overlay_mode_checkbox.isChecked()

        # Get overlay effect settings
        overlay_effect_type = self.video_compose_effect_combo.currentData() if overlay_mode else "none"
        effect_value = self.video_compose_effect_slider.value() if overlay_mode else 0

        if overlay_effect_type == "blur":
            overlay_blur_strength = effect_value
            overlay_mask_opacity = 0
        elif overlay_effect_type == "mask":
            overlay_blur_strength = 0
            overlay_mask_opacity = effect_value
        else:
            overlay_blur_strength = 0
            overlay_mask_opacity = 0

        self.video_compose_log_area.clear()
        self.video_compose_progress_bar.setValue(0)
        self.video_compose_stats_label.setText("已完成: 0/0  失败: 0")

        self.video_compose_task_manager = VideoComposeTaskManager(
            audio_dir=self.tts_output_dir,
            bgm_dir=self.bgm_dir,
            output_dir=self.video_compose_output_dir,
            clip_duration_min=clip_duration_min,
            clip_duration_max=clip_duration_max,
            bgm_volume=bgm_volume,
            voice_volume=voice_volume,
            resolution=resolution,
            max_concurrent=max_concurrent,
            subtitle_config=self.config.subtitle_style,
            product_image_dir=self.product_image_dir,
            product_video_count=product_video_count,
            product_image_count=product_image_count,
            product_image_duration_min=product_image_duration_min,
            product_image_duration_max=product_image_duration_max,
            priority_video=priority_video,
            overlay_mode=overlay_mode,
            overlay_blur_strength=overlay_blur_strength,
            overlay_effect_type=overlay_effect_type,
            overlay_mask_opacity=overlay_mask_opacity,
            blurred_border_config=self.config.blurred_border,
            border_video_dir=self.normal_video_source_dir,
            overlay_material_config=self.config.overlay_material,
            overlay_material_dir=self.overlay_material_dir,
            pip_config=self.config.pip,
            title_config=self.config.title_style,
        )

        self.video_compose_task_manager.set_missing_subtitle_callback(
            self._on_missing_subtitle
        )

        self.video_compose_start_time = time.time()

        self.video_compose_worker = VideoComposeAsyncWorker(
            self.video_compose_task_manager,
            selected_folders,
            max_count,
        )
        self.video_compose_worker.log_signal.connect(self._video_compose_log)
        self.video_compose_worker.progress_signal.connect(self._update_video_compose_progress)
        self.video_compose_worker.finished_signal.connect(self._on_video_compose_task_finished)
        self.video_compose_worker.start()

        self._set_video_compose_buttons_state("running")
        subtitle_status = "启用" if self.config.subtitle_style.enabled else "禁用"
        self._video_compose_log(
            f"开始视频合成任务: {len(selected_folders)} 个文件夹, "
            f"最大生成数: {max_count}, 并发数: {max_concurrent}, "
            f"片段时长: {clip_duration_min}s~{clip_duration_max}s, "
            f"分辨率: {resolution[0]}x{resolution[1]}, 字幕: {subtitle_status}",
            "info"
        )

    def _on_video_compose_pause(self):
        if self.video_compose_task_manager:
            self.video_compose_task_manager.pause()
            self._set_video_compose_buttons_state("paused")
            self._video_compose_log("任务已暂停", "warning")

    def _on_video_compose_resume(self):
        if self.video_compose_task_manager:
            self.video_compose_task_manager.resume()
            self._set_video_compose_buttons_state("running")
            self._video_compose_log("任务已继续", "info")

    def _on_video_compose_stop(self):
        if self.video_compose_task_manager:
            self.video_compose_task_manager.stop()
            self._video_compose_log("正在停止任务...", "warning")

    def _on_video_compose_task_finished(self, progress: VideoComposeTaskProgress):
        self._set_video_compose_buttons_state("idle")

        if progress:
            duration = time.time() - self.video_compose_start_time
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            success_count = progress.completed_tasks - progress.failed_tasks
            self._video_compose_log(
                f"任务完成! 成功: {success_count}, "
                f"失败: {progress.failed_tasks}, "
                f"耗时: {minutes:02d}:{seconds:02d}",
                "success"
            )

            # 弹窗提醒
            from PyQt5.QtWidgets import QMessageBox
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("视频合成完成")
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setText(f"视频合成任务已完成！\n\n成功: {success_count} 个\n失败: {progress.failed_tasks} 个\n耗时: {minutes:02d}:{seconds:02d}")
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec_()
        else:
            self._video_compose_log("任务异常结束", "error")

        self.video_compose_task_manager = None
        self.video_compose_worker = None

    def _on_video_compose_open_folder(self):
        """打开视频合成输出文件夹"""
        if os.path.exists(self.video_compose_output_dir):
            subprocess.Popen(['explorer', self.video_compose_output_dir])
        else:
            QMessageBox.warning(self, "提示", f"输出文件夹不存在: {self.video_compose_output_dir}")

    # ==================== Normal Video Tab ====================

    def _create_normal_video_tab(self) -> QWidget:
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(6)

        # Settings panel
        settings_panel = self._create_normal_video_settings_panel()
        main_layout.addWidget(settings_panel)

        # Progress area
        progress_frame = self._create_normal_video_progress_area()
        main_layout.addWidget(progress_frame)

        # Status bar
        status_bar = self._create_normal_video_status_bar()
        main_layout.addWidget(status_bar)

        # Log area
        log_frame = self._create_normal_video_log_area()
        main_layout.addWidget(log_frame, 1)

        return widget

    def _create_normal_video_settings_panel(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("normal_video_settings_panel")
        frame.setStyleSheet("""
            QFrame#normal_video_settings_panel {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
            }
        """)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Styles
        spin_style = """
            QSpinBox, QDoubleSpinBox {
                border: 1px solid #d0d0d0;
                padding: 1px 4px;
                background: #ffffff;
                min-width: 65px;
                min-height: 28px;
            }
        """
        combo_style = """
            QComboBox {
                border: 1px solid #d0d0d0;
                padding: 1px 4px;
                background: #ffffff;
                min-width: 100px;
                min-height: 28px;
            }
        """

        # --- GroupBox: 生成类型 ---
        type_group = QGroupBox("生成类型")
        type_group.setStyleSheet(Styles.SETTINGS_GROUPBOX)
        type_layout = QHBoxLayout(type_group)

        self.normal_video_liuliang_check = QCheckBox("流量视频")
        self.normal_video_liuliang_check.setFont(QFont("Microsoft YaHei", 9))
        self.normal_video_liuliang_check.setChecked(True)
        self.normal_video_liuliang_check.stateChanged.connect(self._on_normal_video_type_changed)

        self.normal_video_yindao_check = QCheckBox("引导视频")
        self.normal_video_yindao_check.setFont(QFont("Microsoft YaHei", 9))
        self.normal_video_yindao_check.setChecked(False)
        self.normal_video_yindao_check.stateChanged.connect(self._on_normal_video_type_changed)

        self.normal_video_chuchuang_check = QCheckBox("橱窗视频")
        self.normal_video_chuchuang_check.setFont(QFont("Microsoft YaHei", 9))
        self.normal_video_chuchuang_check.setChecked(False)
        self.normal_video_chuchuang_check.stateChanged.connect(self._on_normal_video_type_changed)

        type_layout.addWidget(self.normal_video_liuliang_check)
        type_layout.addSpacing(16)
        type_layout.addWidget(self.normal_video_yindao_check)
        type_layout.addSpacing(16)
        type_layout.addWidget(self.normal_video_chuchuang_check)

        # 橱窗素材显示时长
        type_layout.addSpacing(24)
        chuchuang_duration_label = QLabel("橱窗素材时长:")
        chuchuang_duration_label.setFont(QFont("Microsoft YaHei", 9))
        type_layout.addWidget(chuchuang_duration_label)

        self.normal_video_chuchuang_duration_spin = QSpinBox()
        self.normal_video_chuchuang_duration_spin.setRange(1, 300)
        self.normal_video_chuchuang_duration_spin.setValue(60)
        self.normal_video_chuchuang_duration_spin.setSuffix(" 秒")
        self.normal_video_chuchuang_duration_spin.setStyleSheet(spin_style)
        self.normal_video_chuchuang_duration_spin.setEnabled(False)
        type_layout.addWidget(self.normal_video_chuchuang_duration_spin)

        # 橱窗素材类型
        type_layout.addSpacing(16)
        chuchuang_type_label = QLabel("素材类型:")
        chuchuang_type_label.setFont(QFont("Microsoft YaHei", 9))
        type_layout.addWidget(chuchuang_type_label)

        self.normal_video_chuchuang_material_combo = QComboBox()
        self.normal_video_chuchuang_material_combo.addItems(["图片", "视频"])
        self.normal_video_chuchuang_material_combo.setCurrentText("图片")
        self.normal_video_chuchuang_material_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #d0d0d0;
                padding: 1px 4px;
                background: #ffffff;
                min-width: 80px;
                min-height: 28px;
            }
        """)
        self.normal_video_chuchuang_material_combo.setEnabled(False)
        type_layout.addWidget(self.normal_video_chuchuang_material_combo)

        # 橱窗关键词
        type_layout.addSpacing(16)
        chuchuang_keyword_label = QLabel("检测关键词:")
        chuchuang_keyword_label.setFont(QFont("Microsoft YaHei", 9))
        type_layout.addWidget(chuchuang_keyword_label)

        self.normal_video_chuchuang_keyword_combo = QComboBox()
        self.normal_video_chuchuang_keyword_combo.setEditable(True)  # 可编辑
        self.normal_video_chuchuang_keyword_combo.addItems(["橱窗", "置顶"])
        self.normal_video_chuchuang_keyword_combo.setCurrentText("橱窗")
        self.normal_video_chuchuang_keyword_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #d0d0d0;
                padding: 1px 4px;
                background: #ffffff;
                min-width: 100px;
                min-height: 28px;
            }
        """)
        self.normal_video_chuchuang_keyword_combo.setEnabled(False)
        type_layout.addWidget(self.normal_video_chuchuang_keyword_combo)

        type_layout.addStretch()
        layout.addWidget(type_group)

        # --- GroupBox: 基础参数 ---
        basic_group = QGroupBox("基础参数")
        basic_group.setStyleSheet(Styles.SETTINGS_GROUPBOX)
        basic_grid = QGridLayout(basic_group)
        basic_grid.setSpacing(8)
        basic_grid.setColumnStretch(0, 1)
        basic_grid.setColumnStretch(1, 1)
        basic_grid.setColumnStretch(2, 1)
        basic_grid.setColumnStretch(3, 1)
        basic_grid.addWidget(self._create_spin_param("生成数量:", "normal_video_count_spin",
                             1, 1000, 10, spin_style), 0, 0)
        basic_grid.addWidget(self._create_spin_param("并发数:", "normal_video_concurrent_spin",
                             1, 5, 2, spin_style), 0, 1)
        basic_grid.addWidget(self._create_double_spin_range_param("片段时长:", "normal_video_clip_duration_min_spin",
                             "normal_video_clip_duration_max_spin",
                             1.0, 60.0, 5.0, 10.0, spin_style, "秒"), 0, 2)
        basic_grid.addWidget(self._create_combo_param("分辨率:", "normal_video_resolution_combo",
                             [("16:9", (1920, 1080)), ("1:1", (1080, 1080))], combo_style), 0, 3)
        layout.addWidget(basic_group)

        # --- GroupBox: 音频设置 ---
        audio_group = QGroupBox("音频设置")
        audio_group.setStyleSheet(Styles.SETTINGS_GROUPBOX)
        audio_grid = QGridLayout(audio_group)
        audio_grid.setSpacing(8)
        audio_grid.setColumnStretch(0, 1)
        audio_grid.setColumnStretch(1, 1)
        audio_grid.setColumnStretch(2, 1)
        audio_grid.setColumnStretch(3, 1)
        audio_grid.addWidget(self._create_slider_param("背景音量:", "normal_video_bgm_slider",
                             0, 100, 20), 0, 0)
        audio_grid.addWidget(self._create_slider_param("配音音量:", "normal_video_voice_slider",
                             0, 500, 100), 0, 1)
        layout.addWidget(audio_group)

        # --- GroupBox: 效果设置 ---
        effect_group = QGroupBox("效果设置")
        effect_group.setStyleSheet(Styles.SETTINGS_GROUPBOX)
        effect_grid = QGridLayout(effect_group)
        effect_grid.setSpacing(8)
        effect_grid.setColumnStretch(0, 1)
        effect_grid.setColumnStretch(1, 1)
        effect_grid.setColumnStretch(2, 1)
        effect_grid.setColumnStretch(3, 1)
        # Row 0: 字幕设置, 标题设置, 模糊边框, 叠加素材
        effect_grid.addWidget(self._create_normal_video_subtitle_param(), 0, 0)
        effect_grid.addWidget(self._create_normal_video_title_param(), 0, 1)
        effect_grid.addWidget(self._create_normal_video_blurred_border_param(), 0, 2)
        effect_grid.addWidget(self._create_normal_video_overlay_material_param(), 0, 3)
        # Row 1: 画中画
        effect_grid.addWidget(self._create_normal_video_pip_param(), 1, 0)
        layout.addWidget(effect_group)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)
        btn_layout.addStretch()

        btn_style = """
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 4px 12px;
                min-height: 32px;
            }
            QPushButton:hover { background-color: #e8f4fc; }
            QPushButton:disabled { color: #999999; background-color: #f0f0f0; }
        """
        primary_btn_style = """
            QPushButton {
                color: #ffffff;
                background-color: #0066cc;
                border: 1px solid #0055aa;
                padding: 4px 15px;
                min-height: 32px;
            }
            QPushButton:hover { background-color: #0055aa; }
            QPushButton:disabled { background-color: #cccccc; }
        """
        stop_btn_style = """
            QPushButton {
                color: #cc0000;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 4px 12px;
                min-height: 32px;
            }
            QPushButton:hover { background-color: #ffeeee; }
            QPushButton:disabled { color: #999999; background-color: #f0f0f0; }
        """

        self.normal_video_start_btn = QPushButton("开始生成")
        self.normal_video_start_btn.setFont(QFont("Microsoft YaHei", 9))
        self.normal_video_start_btn.setStyleSheet(primary_btn_style)
        self.normal_video_start_btn.clicked.connect(self._on_normal_video_start)

        self.normal_video_pause_btn = QPushButton("暂停")
        self.normal_video_pause_btn.setFont(QFont("Microsoft YaHei", 9))
        self.normal_video_pause_btn.setStyleSheet(btn_style)
        self.normal_video_pause_btn.setEnabled(False)
        self.normal_video_pause_btn.clicked.connect(self._on_normal_video_pause)

        self.normal_video_resume_btn = QPushButton("继续")
        self.normal_video_resume_btn.setFont(QFont("Microsoft YaHei", 9))
        self.normal_video_resume_btn.setStyleSheet(btn_style)
        self.normal_video_resume_btn.setEnabled(False)
        self.normal_video_resume_btn.clicked.connect(self._on_normal_video_resume)

        self.normal_video_stop_btn = QPushButton("停止")
        self.normal_video_stop_btn.setFont(QFont("Microsoft YaHei", 9))
        self.normal_video_stop_btn.setStyleSheet(stop_btn_style)
        self.normal_video_stop_btn.setEnabled(False)
        self.normal_video_stop_btn.clicked.connect(self._on_normal_video_stop)

        # 打开输出文件夹按钮
        open_folder_btn_style = """
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                min-height: 28px;
            }
            QPushButton:hover { background-color: #138496; }
        """
        self.normal_video_open_folder_btn = QPushButton("打开输出文件夹")
        self.normal_video_open_folder_btn.setFont(QFont("Microsoft YaHei", 9))
        self.normal_video_open_folder_btn.setStyleSheet(open_folder_btn_style)
        self.normal_video_open_folder_btn.clicked.connect(self._on_normal_video_open_folder)

        btn_layout.addWidget(self.normal_video_start_btn)
        btn_layout.addWidget(self.normal_video_pause_btn)
        btn_layout.addWidget(self.normal_video_resume_btn)
        btn_layout.addWidget(self.normal_video_stop_btn)
        btn_layout.addWidget(self.normal_video_open_folder_btn)

        layout.addLayout(btn_layout)

        return frame

    def _create_normal_video_subtitle_param(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel("字幕:")
        label.setFont(QFont("Microsoft YaHei", 9))
        label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(label)

        self.normal_video_subtitle_btn = QPushButton("字幕设置")
        self.normal_video_subtitle_btn.setFont(QFont("Microsoft YaHei", 9))
        self.normal_video_subtitle_btn.setStyleSheet("""
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 6px 12px;
                min-height: 28px;
            }
            QPushButton:hover { background-color: #e8f4fc; }
        """)
        self.normal_video_subtitle_btn.clicked.connect(self._on_normal_video_subtitle_settings)
        layout.addWidget(self.normal_video_subtitle_btn)

        return container

    def _create_normal_video_title_param(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel("标题:")
        label.setFont(QFont("Microsoft YaHei", 9))
        label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(label)

        self.normal_video_title_btn = QPushButton("标题设置")
        self.normal_video_title_btn.setFont(QFont("Microsoft YaHei", 9))
        self.normal_video_title_btn.setStyleSheet("""
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 6px 12px;
                min-height: 28px;
            }
            QPushButton:hover { background-color: #e8f4fc; }
        """)
        self.normal_video_title_btn.clicked.connect(self._on_normal_video_title_settings)
        layout.addWidget(self.normal_video_title_btn)

        return container

    def _create_normal_video_blurred_border_param(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel("模糊边框:")
        label.setFont(QFont("Microsoft YaHei", 9))
        label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(label)

        self.normal_video_blurred_border_btn = QPushButton("模糊边框设置")
        self.normal_video_blurred_border_btn.setFont(QFont("Microsoft YaHei", 9))
        self.normal_video_blurred_border_btn.setStyleSheet("""
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 6px 12px;
                min-height: 28px;
            }
            QPushButton:hover { background-color: #e8f4fc; }
        """)
        self.normal_video_blurred_border_btn.clicked.connect(self._on_normal_video_blurred_border_settings)
        layout.addWidget(self.normal_video_blurred_border_btn)

        return container

    def _create_normal_video_overlay_material_param(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel("叠加素材:")
        label.setFont(QFont("Microsoft YaHei", 9))
        label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(label)

        self.normal_video_overlay_material_btn = QPushButton("叠加素材设置")
        self.normal_video_overlay_material_btn.setFont(QFont("Microsoft YaHei", 9))
        self.normal_video_overlay_material_btn.setStyleSheet("""
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 6px 12px;
                min-height: 28px;
            }
            QPushButton:hover { background-color: #e8f4fc; }
        """)
        self.normal_video_overlay_material_btn.clicked.connect(self._on_normal_video_overlay_material_settings)
        layout.addWidget(self.normal_video_overlay_material_btn)

        return container

    def _create_normal_video_pip_param(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = QLabel("画中画:")
        label.setFont(QFont("Microsoft YaHei", 9))
        label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(label)

        self.normal_video_pip_btn = QPushButton("画中画设置")
        self.normal_video_pip_btn.setFont(QFont("Microsoft YaHei", 9))
        self.normal_video_pip_btn.setStyleSheet("""
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 6px 12px;
                min-height: 28px;
            }
            QPushButton:hover { background-color: #e8f4fc; }
        """)
        self.normal_video_pip_btn.clicked.connect(self._on_normal_video_pip_settings)
        layout.addWidget(self.normal_video_pip_btn)

        return container

    def _create_normal_video_progress_area(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
            }
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)

        self.normal_video_progress_bar = QProgressBar()
        self.normal_video_progress_bar.setRange(0, 100)
        self.normal_video_progress_bar.setValue(0)
        self.normal_video_progress_bar.setFixedHeight(12)
        self.normal_video_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                text-align: center;
                background-color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #0066cc;
            }
        """)
        layout.addWidget(self.normal_video_progress_bar, 1)

        self.normal_video_stats_label = QLabel("已完成: 0/0  失败: 0")
        self.normal_video_stats_label.setFont(QFont("Microsoft YaHei", 9))
        self.normal_video_stats_label.setStyleSheet("color: #666666; border: none;")
        self.normal_video_stats_label.setMinimumWidth(150)
        layout.addWidget(self.normal_video_stats_label)

        return frame

    def _create_normal_video_status_bar(self) -> QFrame:
        frame = QFrame()
        frame.setFixedHeight(18)
        frame.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border: 1px solid #d0d0d0;
            }
        """)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(6, 1, 6, 1)

        self.normal_video_status_text = QLabel("没有运行项目...")
        self.normal_video_status_text.setFont(QFont("Microsoft YaHei", 9))
        self.normal_video_status_text.setStyleSheet(
            "color: #0066cc; border: none; background: transparent;"
        )
        layout.addWidget(self.normal_video_status_text)
        layout.addStretch()

        return frame

    def _create_normal_video_log_area(self) -> QFrame:
        frame = QFrame()
        frame.setMinimumHeight(120)
        frame.setMaximumHeight(200)
        frame.setStyleSheet("""
            QFrame#normal_video_log_frame {
                background-color: #1e1e1e;
                border: 1px solid #333333;
            }
        """)
        frame.setObjectName("normal_video_log_frame")

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel(" 日志")
        header.setFixedHeight(14)
        header.setFont(QFont("Microsoft YaHei", 9))
        header.setStyleSheet(
            "color: #888888; background-color: #2d2d2d; border: none; padding-left: 8px;"
        )
        layout.addWidget(header)

        self.normal_video_log_area = QTextEdit()
        self.normal_video_log_area.setReadOnly(True)
        self.normal_video_log_area.setFont(QFont("Consolas", 10))
        self.normal_video_log_area.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #00ff00;
                border: none;
                padding: 3px;
            }
        """)
        layout.addWidget(self.normal_video_log_area)

        return frame

    def _normal_video_log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        color_map = {
            "info": "#00ff00",
            "warning": "#ffff00",
            "error": "#ff0000",
            "success": "#00ff00",
        }
        color = color_map.get(level, "#00ff00")
        html = f'<span style="color: #888888;">[{timestamp}]</span> '
        html += f'<span style="color: {color};">{message}</span>'
        self.normal_video_log_area.append(html)
        cursor = self.normal_video_log_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.normal_video_log_area.setTextCursor(cursor)

    def _update_normal_video_progress(self, progress: NormalVideoTaskProgress):
        if progress.total_tasks > 0:
            percent = int(progress.completed_tasks / progress.total_tasks * 100)
            self.normal_video_progress_bar.setValue(percent)
        self.normal_video_stats_label.setText(
            f"已完成: {progress.completed_tasks}/{progress.total_tasks}  "
            f"失败: {progress.failed_tasks}"
        )
        if progress.current_task:
            self.normal_video_status_text.setText(
                f"正在处理: {progress.current_task}"
            )

    def _set_normal_video_buttons_state(self, state: str):
        if state == "idle":
            self.normal_video_start_btn.setEnabled(True)
            self.normal_video_pause_btn.setEnabled(False)
            self.normal_video_resume_btn.setEnabled(False)
            self.normal_video_stop_btn.setEnabled(False)
            self.normal_video_count_spin.setEnabled(True)
            self.normal_video_concurrent_spin.setEnabled(True)
            self.normal_video_clip_duration_min_spin.setEnabled(True)
            self.normal_video_clip_duration_max_spin.setEnabled(True)
            self.normal_video_bgm_slider.setEnabled(True)
            self.normal_video_voice_slider.setEnabled(True)
            self.normal_video_resolution_combo.setEnabled(True)
            self.normal_video_subtitle_btn.setEnabled(True)
            self.normal_video_title_btn.setEnabled(True)
            self.normal_video_liuliang_check.setEnabled(True)
            self.normal_video_yindao_check.setEnabled(True)
            self.normal_video_status_text.setText("没有运行项目...")
        elif state == "running":
            self.normal_video_start_btn.setEnabled(False)
            self.normal_video_pause_btn.setEnabled(True)
            self.normal_video_resume_btn.setEnabled(False)
            self.normal_video_stop_btn.setEnabled(True)
            self.normal_video_count_spin.setEnabled(False)
            self.normal_video_concurrent_spin.setEnabled(False)
            self.normal_video_clip_duration_min_spin.setEnabled(False)
            self.normal_video_clip_duration_max_spin.setEnabled(False)
            self.normal_video_bgm_slider.setEnabled(False)
            self.normal_video_voice_slider.setEnabled(False)
            self.normal_video_resolution_combo.setEnabled(False)
            self.normal_video_subtitle_btn.setEnabled(False)
            self.normal_video_title_btn.setEnabled(False)
            self.normal_video_liuliang_check.setEnabled(False)
            self.normal_video_yindao_check.setEnabled(False)
        elif state == "paused":
            self.normal_video_start_btn.setEnabled(False)
            self.normal_video_pause_btn.setEnabled(False)
            self.normal_video_resume_btn.setEnabled(True)
            self.normal_video_stop_btn.setEnabled(True)
            self.normal_video_status_text.setText("已暂停")

    def _on_normal_video_subtitle_settings(self):
        from .subtitle_settings_dialog import SubtitleSettingsDialog
        from PyQt5.QtWidgets import QDialog

        dialog = SubtitleSettingsDialog(
            self.config.subtitle_style,
            self.config.subtitle_style_templates,
            self.save_dir,
            self
        )
        if dialog.exec_() == QDialog.Accepted:
            self.config.subtitle_style = dialog.get_style()
            self.config.subtitle_style_templates = dialog.get_templates()
            self.config.save()

    def _on_normal_video_title_settings(self):
        from .title_settings_dialog import TitleSettingsDialog
        from PyQt5.QtWidgets import QDialog

        dialog = TitleSettingsDialog(
            self.config.title_style,
            self.config.title_style_templates,
            self.save_dir,
            self
        )
        if dialog.exec_() == QDialog.Accepted:
            self.config.title_style = dialog.get_style()
            self.config.title_style_templates = dialog.get_templates()
            self.config.save()

    def _on_normal_video_blurred_border_settings(self):
        from .blurred_border_settings_dialog import BlurredBorderSettingsDialog
        from PyQt5.QtWidgets import QDialog

        dialog = BlurredBorderSettingsDialog(self.config.blurred_border, self)
        if dialog.exec_() == QDialog.Accepted:
            self.config.blurred_border = dialog.get_config()
            self.config.save()

    def _on_normal_video_overlay_material_settings(self):
        from .overlay_material_settings_dialog import OverlayMaterialSettingsDialog
        from PyQt5.QtWidgets import QDialog

        dialog = OverlayMaterialSettingsDialog(
            self.config.overlay_material, self.overlay_material_dir, self
        )
        if dialog.exec_() == QDialog.Accepted:
            self.config.overlay_material = dialog.get_config()
            self.config.save()

    def _on_normal_video_pip_settings(self):
        from .pip_settings_dialog import PipSettingsDialog
        from PyQt5.QtWidgets import QDialog

        dialog = PipSettingsDialog(self.config.pip, self)
        if dialog.exec_() == QDialog.Accepted:
            self.config.pip = dialog.get_config()
            self.config.save()

    def _on_normal_video_type_changed(self, state):
        """流量视频、引导视频、橱窗视频互斥选择"""
        sender = self.sender()
        if state == Qt.Checked:
            # 勾选一个时，取消另外两个
            if sender == self.normal_video_liuliang_check:
                self.normal_video_yindao_check.blockSignals(True)
                self.normal_video_yindao_check.setChecked(False)
                self.normal_video_yindao_check.blockSignals(False)
                self.normal_video_chuchuang_check.blockSignals(True)
                self.normal_video_chuchuang_check.setChecked(False)
                self.normal_video_chuchuang_check.blockSignals(False)
                self.normal_video_chuchuang_duration_spin.setEnabled(False)
                self.normal_video_chuchuang_material_combo.setEnabled(False)
                self.normal_video_chuchuang_keyword_combo.setEnabled(False)
            elif sender == self.normal_video_yindao_check:
                self.normal_video_liuliang_check.blockSignals(True)
                self.normal_video_liuliang_check.setChecked(False)
                self.normal_video_liuliang_check.blockSignals(False)
                self.normal_video_chuchuang_check.blockSignals(True)
                self.normal_video_chuchuang_check.setChecked(False)
                self.normal_video_chuchuang_check.blockSignals(False)
                self.normal_video_chuchuang_duration_spin.setEnabled(False)
                self.normal_video_chuchuang_material_combo.setEnabled(False)
                self.normal_video_chuchuang_keyword_combo.setEnabled(False)
            elif sender == self.normal_video_chuchuang_check:
                self.normal_video_liuliang_check.blockSignals(True)
                self.normal_video_liuliang_check.setChecked(False)
                self.normal_video_liuliang_check.blockSignals(False)
                self.normal_video_yindao_check.blockSignals(True)
                self.normal_video_yindao_check.setChecked(False)
                self.normal_video_yindao_check.blockSignals(False)
                self.normal_video_chuchuang_duration_spin.setEnabled(True)
                self.normal_video_chuchuang_material_combo.setEnabled(True)
                self.normal_video_chuchuang_keyword_combo.setEnabled(True)

    def _on_normal_video_start(self):
        do_liuliang = self.normal_video_liuliang_check.isChecked()
        do_yindao = self.normal_video_yindao_check.isChecked()
        do_chuchuang = self.normal_video_chuchuang_check.isChecked()

        if not do_liuliang and not do_yindao and not do_chuchuang:
            QMessageBox.warning(self, "提示", "请至少勾选【流量视频】、【引导视频】或【橱窗视频】中的一个")
            return

        # Validate source videos
        if not os.path.exists(self.normal_video_source_dir):
            os.makedirs(self.normal_video_source_dir, exist_ok=True)
        source_videos = [
            f for f in os.listdir(self.normal_video_source_dir)
            if os.path.splitext(f)[1].lower() in {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv'}
        ] if os.path.exists(self.normal_video_source_dir) else []
        if not source_videos:
            QMessageBox.warning(self, "提示", "input/真实视频素材/ 文件夹中没有视频文件")
            return

        # Build pending configs (顺序：流量 → 引导 → 橱窗)
        configs = []
        if do_liuliang:
            audio_files = [
                f for f in os.listdir(self.liuliang_output_dir)
                if os.path.splitext(f)[1].lower() in {'.mp3', '.wav', '.aac', '.m4a', '.flac'}
            ] if os.path.exists(self.liuliang_output_dir) else []
            if not audio_files:
                QMessageBox.warning(self, "提示", "input/视频配音/流量语音/ 文件夹中没有音频文件")
                return
            configs.append((self.liuliang_output_dir, self.liuliang_video_output_dir, "流量语音", "流量视频", False, 0, "图片", ""))

        if do_yindao:
            audio_files = [
                f for f in os.listdir(self.yindao_output_dir)
                if os.path.splitext(f)[1].lower() in {'.mp3', '.wav', '.aac', '.m4a', '.flac'}
            ] if os.path.exists(self.yindao_output_dir) else []
            if not audio_files:
                QMessageBox.warning(self, "提示", "input/视频配音/引导语音/ 文件夹中没有音频文件")
                return
            configs.append((self.yindao_output_dir, self.yindao_video_output_dir, "引导语音", "引导视频", False, 0, "图片", ""))

        if do_chuchuang:
            audio_files = [
                f for f in os.listdir(self.chuchuang_output_dir)
                if os.path.splitext(f)[1].lower() in {'.mp3', '.wav', '.aac', '.m4a', '.flac'}
            ] if os.path.exists(self.chuchuang_output_dir) else []
            if not audio_files:
                QMessageBox.warning(self, "提示", "input/视频配音/橱窗语音/ 文件夹中没有音频文件")
                return
            # 检查橱窗素材
            material_type = self.normal_video_chuchuang_material_combo.currentText()
            chuchuang_keyword = self.normal_video_chuchuang_keyword_combo.currentText().strip()
            if not chuchuang_keyword:
                QMessageBox.warning(self, "提示", "请输入检测关键词")
                return

            chuchuang_materials = []
            # 素材路径：input/橱窗素材/{关键词}/{图片或视频}/
            keyword_dir = os.path.join(self.chuchuang_material_dir, chuchuang_keyword)
            material_dir = os.path.join(keyword_dir, material_type)
            if os.path.exists(material_dir):
                if material_type == "图片":
                    chuchuang_materials = [
                        os.path.join(material_dir, f) for f in os.listdir(material_dir)
                        if os.path.splitext(f)[1].lower() in {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
                    ]
                else:
                    chuchuang_materials = [
                        os.path.join(material_dir, f) for f in os.listdir(material_dir)
                        if os.path.splitext(f)[1].lower() in {'.mp4', '.avi', '.mov', '.mkv'}
                    ]
            if not chuchuang_materials:
                QMessageBox.warning(self, "提示", f"input/橱窗素材/{chuchuang_keyword}/{material_type}/ 文件夹中没有素材文件")
                return
            chuchuang_duration = self.normal_video_chuchuang_duration_spin.value()
            configs.append((self.chuchuang_output_dir, self.chuchuang_video_output_dir, "橱窗语音", "橱窗视频", True, chuchuang_duration, material_type, chuchuang_keyword))

        self._normal_video_pending_configs = configs
        self._normal_video_max_count = self.normal_video_count_spin.value()

        self.normal_video_log_area.clear()
        self.normal_video_progress_bar.setValue(0)
        self.normal_video_stats_label.setText("已完成: 0/0  失败: 0")

        self._set_normal_video_buttons_state("running")
        self._start_next_normal_video_config()

    def _start_next_normal_video_config(self):
        if not self._normal_video_pending_configs:
            self._set_normal_video_buttons_state("idle")
            return

        audio_dir, output_dir, recycle_subdir, label, is_chuchuang, chuchuang_duration, chuchuang_material_type, chuchuang_keyword = self._normal_video_pending_configs.pop(0) if len(self._normal_video_pending_configs[0]) == 8 else (*self._normal_video_pending_configs.pop(0), "")
        os.makedirs(output_dir, exist_ok=True)

        max_concurrent = self.normal_video_concurrent_spin.value()
        clip_duration_min = self.normal_video_clip_duration_min_spin.value()
        clip_duration_max = self.normal_video_clip_duration_max_spin.value()
        bgm_volume = self.normal_video_bgm_slider.value() / 100.0
        voice_volume = self.normal_video_voice_slider.value() / 100.0
        resolution = self.normal_video_resolution_combo.currentData()

        subtitle_status = "启用" if self.config.subtitle_style.enabled else "禁用"
        title_status = "启用" if self.config.title_style.enabled else "禁用"

        if is_chuchuang:
            self._normal_video_log(
                f"开始生成【{label}】: 最大生成数: {self._normal_video_max_count}, 并发数: {max_concurrent}, "
                f"片段时长: {clip_duration_min}s~{clip_duration_max}s, 分辨率: {resolution[0]}x{resolution[1]}, "
                f"字幕: {subtitle_status}, 标题: {title_status}, 橱窗素材时长: {chuchuang_duration}秒, 素材类型: {chuchuang_material_type}",
                "info"
            )
        else:
            self._normal_video_log(
                f"开始生成【{label}】: 最大生成数: {self._normal_video_max_count}, 并发数: {max_concurrent}, "
                f"片段时长: {clip_duration_min}s~{clip_duration_max}s, 分辨率: {resolution[0]}x{resolution[1]}, "
                f"字幕: {subtitle_status}, 标题: {title_status}",
                "info"
            )

        self.normal_video_task_manager = NormalVideoTaskManager(
            video_source_dir=self.normal_video_source_dir,
            audio_source_dir=audio_dir,
            bgm_dir=self.bgm_dir,
            output_dir=output_dir,
            recycle_dir=self.recycle_dir,
            recycle_subdir=recycle_subdir,
            clip_duration_min=clip_duration_min,
            clip_duration_max=clip_duration_max,
            bgm_volume=bgm_volume,
            voice_volume=voice_volume,
            resolution=resolution,
            max_concurrent=max_concurrent,
            subtitle_config=self.config.subtitle_style,
            title_config=self.config.title_style,
            blurred_border_config=self.config.blurred_border,
            border_video_dir=self.normal_video_source_dir,
            overlay_material_config=self.config.overlay_material,
            overlay_material_dir=self.overlay_material_dir,
            pip_config=self.config.pip,
            chuchuang_mode=is_chuchuang,
            chuchuang_material_dir=self.chuchuang_material_dir if is_chuchuang else "",
            chuchuang_duration=chuchuang_duration if is_chuchuang else 60,
            chuchuang_material_type=chuchuang_material_type if is_chuchuang else "图片",
            chuchuang_keyword=chuchuang_keyword if is_chuchuang else "",
        )
        self.normal_video_start_time = time.time()

        self.normal_video_worker = NormalVideoAsyncWorker(
            self.normal_video_task_manager,
            self._normal_video_max_count,
        )
        self.normal_video_worker.log_signal.connect(self._normal_video_log)
        self.normal_video_worker.progress_signal.connect(self._update_normal_video_progress)
        self.normal_video_worker.finished_signal.connect(self._on_normal_video_task_finished)
        self.normal_video_worker.start()


    def _on_normal_video_pause(self):
        if self.normal_video_task_manager:
            self.normal_video_task_manager.pause()
            self._set_normal_video_buttons_state("paused")
            self._normal_video_log("任务已暂停", "warning")

    def _on_normal_video_resume(self):
        if self.normal_video_task_manager:
            self.normal_video_task_manager.resume()
            self._set_normal_video_buttons_state("running")
            self._normal_video_log("任务已继续", "info")

    def _on_normal_video_stop(self):
        if self.normal_video_task_manager:
            self.normal_video_task_manager.stop()
            self._normal_video_log("正在停止任务...", "warning")

    def _on_normal_video_task_finished(self, progress: NormalVideoTaskProgress):
        if progress:
            duration = time.time() - self.normal_video_start_time
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            success_count = progress.completed_tasks - progress.failed_tasks
            self._normal_video_log(
                f"任务完成! 成功: {success_count}, "
                f"失败: {progress.failed_tasks}, "
                f"耗时: {minutes:02d}:{seconds:02d}",
                "success"
            )

            # 弹窗提醒
            from PyQt5.QtWidgets import QMessageBox
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("视频生成完成")
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setText(f"视频生成任务已完成！\n\n成功: {success_count} 个\n失败: {progress.failed_tasks} 个\n耗时: {minutes:02d}:{seconds:02d}")
            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec_()
        else:
            self._normal_video_log("任务异常结束", "error")

        self.normal_video_task_manager = None
        self.normal_video_worker = None
        self._start_next_normal_video_config()

        self.normal_video_task_manager = None
        self.normal_video_worker = None

    def _on_normal_video_open_folder(self):
        """打开普通视频输出文件夹"""
        # 打开output目录，因为普通视频可能输出到流量视频或引导视频子目录
        output_base = os.path.dirname(self.normal_video_output_dir)
        if os.path.exists(output_base):
            subprocess.Popen(['explorer', output_base])
        else:
            QMessageBox.warning(self, "提示", f"输出文件夹不存在: {output_base}")

    # ==================== 新提取文案Tab ====================

    def _create_new_extract_tab(self) -> QWidget:
        """Create new extract copywriting tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(6)

        # Top area - compact layout
        top_frame = QFrame()
        top_layout = QVBoxLayout(top_frame)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)

        # File input and settings in one row
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(6)

        # File input
        input_panel = self._create_new_extract_input_panel()
        controls_layout.addWidget(input_panel, 3)

        # Settings
        settings_panel = self._create_new_extract_settings_panel()
        controls_layout.addWidget(settings_panel, 2)

        top_layout.addLayout(controls_layout)
        layout.addWidget(top_frame)

        # Log area
        log_frame = self._create_new_extract_log_area()
        layout.addWidget(log_frame, 1)

        return widget

    def _create_new_extract_input_panel(self) -> QFrame:
        """Create URL input panel"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        label = QLabel("文件")
        label.setFont(QFont("Microsoft YaHei", 9, QFont.Bold))
        label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(label)

        # File selection
        file_layout = QHBoxLayout()
        self.new_extract_file_input = QLineEdit()
        self.new_extract_file_input.setPlaceholderText("选择txt或excel文件...")
        self.new_extract_file_input.setFont(QFont("Microsoft YaHei", 9))
        self.new_extract_file_input.setReadOnly(True)
        file_layout.addWidget(self.new_extract_file_input)

        select_file_btn = QPushButton("选择文件")
        select_file_btn.setFont(QFont("Microsoft YaHei", 9))
        select_file_btn.setFixedWidth(80)
        select_file_btn.clicked.connect(self._on_new_extract_select_file)
        file_layout.addWidget(select_file_btn)
        layout.addLayout(file_layout)

        return frame

    def _create_new_extract_settings_panel(self) -> QFrame:
        """Create settings panel"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        label = QLabel("参数设置")
        label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(label)

        # Model selection
        model_layout = QHBoxLayout()
        model_label = QLabel("Whisper模型:")
        model_label.setFont(QFont("Microsoft YaHei", 9))
        self.new_extract_model_combo = QComboBox()
        self.new_extract_model_combo.addItems(["small", "medium"])
        self.new_extract_model_combo.setCurrentText("medium")
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.new_extract_model_combo)
        model_layout.addStretch()
        layout.addLayout(model_layout)

        # Concurrent tasks
        concurrent_layout = QHBoxLayout()
        concurrent_label = QLabel("并发数:")
        concurrent_label.setFont(QFont("Microsoft YaHei", 9))
        self.new_extract_concurrent_spin = QSpinBox()
        self.new_extract_concurrent_spin.setRange(1, 4)
        self.new_extract_concurrent_spin.setValue(2)
        concurrent_layout.addWidget(concurrent_label)
        concurrent_layout.addWidget(self.new_extract_concurrent_spin)
        concurrent_layout.addStretch()
        layout.addLayout(concurrent_layout)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()

        self.new_extract_start_btn = QPushButton("开始提取")
        self.new_extract_start_btn.setFont(QFont("Microsoft YaHei", 10))
        self.new_extract_start_btn.setStyleSheet("""
            QPushButton {
                color: #ffffff;
                background-color: #0066cc;
                border: 1px solid #0055aa;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #0055aa;
            }
        """)
        self.new_extract_start_btn.clicked.connect(self._on_new_extract_start)
        btn_layout.addWidget(self.new_extract_start_btn)

        self.new_extract_open_folder_btn = QPushButton("打开文件夹")
        self.new_extract_open_folder_btn.setFont(QFont("Microsoft YaHei", 10))
        self.new_extract_open_folder_btn.clicked.connect(self._on_new_extract_open_folder)
        btn_layout.addWidget(self.new_extract_open_folder_btn)

        layout.addLayout(btn_layout)

        return frame

    def _create_new_extract_log_area(self) -> QFrame:
        """Create log area"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        label = QLabel("运行日志")
        label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        label.setStyleSheet("color: #333333; border: none;")
        layout.addWidget(label)

        self.new_extract_log = QTextEdit()
        self.new_extract_log.setReadOnly(True)
        self.new_extract_log.setFont(QFont("Consolas", 9))
        layout.addWidget(self.new_extract_log)

        return frame

    def _on_new_extract_select_file(self):
        """Select file with URLs"""
        from PyQt5.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文件",
            "",
            "文本文件 (*.txt);;Excel文件 (*.xlsx *.xls);;所有文件 (*.*)"
        )
        if file_path:
            self.new_extract_file_input.setText(file_path)

    def _on_new_extract_start(self):
        """Start extraction"""
        file_path = self.new_extract_file_input.text().strip()
        if not file_path:
            QMessageBox.warning(self, "提示", "请选择包含视频链接的文件")
            return

        if not os.path.exists(file_path):
            QMessageBox.warning(self, "提示", "文件不存在")
            return

        model = self.new_extract_model_combo.currentText()
        concurrent = self.new_extract_concurrent_spin.value()

        self.new_extract_start_btn.setEnabled(False)
        self.new_extract_log.clear()
        self._new_extract_log("开始提取文案...")

        # Run extract_batch.py in subprocess
        from PyQt5.QtCore import QThread, pyqtSignal
        import subprocess

        class ExtractWorker(QThread):
            log_signal = pyqtSignal(str)
            finished_signal = pyqtSignal(bool, str)

            def __init__(self, file_path, model, concurrent):
                super().__init__()
                self.file_path = file_path
                self.model = model
                self.concurrent = concurrent

            def run(self):
                try:
                    # Get extract_batch.py path
                    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "extract_batch.py")

                    if not os.path.exists(script_path):
                        self.finished_signal.emit(False, f"找不到脚本: {script_path}")
                        return

                    # Run subprocess
                    self.log_signal.emit(f"文件: {os.path.basename(self.file_path)}")
                    self.log_signal.emit(f"模型: {self.model}")
                    self.log_signal.emit(f"并发数: {self.concurrent}")
                    self.log_signal.emit("=" * 50)
                    self.log_signal.emit("正在启动子进程...")
                    self.log_signal.emit(f"加载Whisper {self.model} 模型中，首次需要1-3分钟，请耐心等待...")

                    process = subprocess.Popen(
                        [sys.executable, script_path, self.file_path, self.model, str(self.concurrent)],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding='utf-8',
                        errors='replace'
                    )

                    # Read output line by line
                    for line in process.stdout:
                        line = line.rstrip()
                        if line:
                            self.log_signal.emit(line)

                    process.wait()

                    if process.returncode == 0:
                        self.finished_signal.emit(True, "提取完成!")
                    else:
                        self.finished_signal.emit(False, f"提取失败，退出码: {process.returncode}")

                except Exception as e:
                    import traceback
                    error_msg = f"错误: {str(e)}\n{traceback.format_exc()}"
                    self.log_signal.emit(error_msg)
                    self.finished_signal.emit(False, error_msg)

        self.new_extract_worker = ExtractWorker(file_path, model, concurrent)
        self.new_extract_worker.log_signal.connect(self._new_extract_log)
        self.new_extract_worker.finished_signal.connect(self._on_new_extract_finished)
        self.new_extract_worker.start()

    def _new_extract_log(self, message: str):
        """Add log message"""
        self.new_extract_log.append(message)

    def _on_new_extract_finished(self, success: bool, message: str):
        """Handle extraction finished"""
        self._new_extract_log(message)
        self.new_extract_start_btn.setEnabled(True)

        if success:
            QMessageBox.information(self, "完成", message)

    def _on_new_extract_open_folder(self):
        """Open output folder"""
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "input", "提取的视频文案")
        if os.path.exists(output_dir):
            subprocess.Popen(['explorer', output_dir])
        else:
            QMessageBox.warning(self, "提示", f"输出文件夹不存在: {output_dir}")
