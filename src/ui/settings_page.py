from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QPushButton,
    QFrame,
    QFormLayout,
    QMessageBox,
    QTabWidget,
    QTextEdit,
    QCheckBox,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

import aiohttp
import asyncio

from ..models.config import Config
from ..core.copywriting_api_client import CopywritingAPIClient
from ..core.merge_copywriting_api_client import MergeCopywritingAPIClient
from ..core.product_time_api_client import ProductTimeAPIClient
from .theme import get_input_style, get_spin_style, get_label_style
from .whisper_download_tab import WhisperDownloadTab


class ModelQueryWorker(QThread):
    finished_signal = pyqtSignal(bool, list, str)  # success, models, error

    def __init__(self, base_url: str, api_key: str):
        super().__init__()
        self.base_url = base_url
        self.api_key = api_key

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(self._query_models())
            self.finished_signal.emit(*result)
        except Exception as e:
            self.finished_signal.emit(False, [], str(e))
        finally:
            loop.close()

    async def _query_models(self):
        client = CopywritingAPIClient(self.base_url, self.api_key, "")
        async with aiohttp.ClientSession() as session:
            return await client.list_models(session)


class MergeModelQueryWorker(QThread):
    finished_signal = pyqtSignal(bool, list, str)  # success, models, error

    def __init__(self, base_url: str, api_key: str):
        super().__init__()
        self.base_url = base_url
        self.api_key = api_key

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(self._query_models())
            self.finished_signal.emit(*result)
        except Exception as e:
            self.finished_signal.emit(False, [], str(e))
        finally:
            loop.close()

    async def _query_models(self):
        client = MergeCopywritingAPIClient(self.base_url, self.api_key, "")
        async with aiohttp.ClientSession() as session:
            return await client.list_models(session)


class RewriteModelQueryWorker(QThread):
    finished_signal = pyqtSignal(bool, list, str)  # success, models, error

    def __init__(self, base_url: str, api_key: str):
        super().__init__()
        self.base_url = base_url
        self.api_key = api_key

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(self._query_models())
            self.finished_signal.emit(*result)
        except Exception as e:
            self.finished_signal.emit(False, [], str(e))
        finally:
            loop.close()

    async def _query_models(self):
        client = CopywritingAPIClient(self.base_url, self.api_key, "")
        async with aiohttp.ClientSession() as session:
            return await client.list_models(session)


class ProductTimeModelQueryWorker(QThread):
    finished_signal = pyqtSignal(bool, list, str)  # success, models, error

    def __init__(self, base_url: str, api_key: str):
        super().__init__()
        self.base_url = base_url
        self.api_key = api_key

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(self._query_models())
            self.finished_signal.emit(*result)
        except Exception as e:
            self.finished_signal.emit(False, [], str(e))
        finally:
            loop.close()

    async def _query_models(self):
        client = ProductTimeAPIClient(self.base_url, self.api_key, "", "")
        async with aiohttp.ClientSession() as session:
            return await client.list_models(session)


class SettingsPage(QWidget):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        content_frame = QFrame()
        content_frame.setStyleSheet("""
            QFrame#settings_content {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
            }
        """)
        content_frame.setObjectName("settings_content")

        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(8)

        # Create QTabWidget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #d0d0d0;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background-color: #f0f0f0;
                border: 1px solid #d0d0d0;
                border-bottom: none;
                padding: 4px 10px;
                margin-right: 1px;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                border-bottom: 1px solid #ffffff;
            }
            QTabBar::tab:hover:!selected {
                background-color: #e8e8e8;
            }
        """)
        self.tab_widget.addTab(self._create_copywriting_api_tab(), "视频文案API")
        self.tab_widget.addTab(self._create_rewrite_copywriting_api_tab(), "文案改写API")
        self.tab_widget.addTab(self._create_image_recognition_api_tab(), "识图API")
        self.tab_widget.addTab(self._create_merge_copywriting_api_tab(), "合并文案API")
        self.tab_widget.addTab(self._create_tts_api_tab(), "语音生成API")
        self.tab_widget.addTab(self._create_subtitle_api_tab(), "字幕生成API")
        self.tab_widget.addTab(self._create_product_time_api_tab(), "时间段识别API")
        self.tab_widget.addTab(self._create_image_api_tab(), "图片API配置")
        self.tab_widget.addTab(self._create_video_api_tab(), "视频API配置")
        self._whisper_tab = WhisperDownloadTab()
        self.tab_widget.addTab(self._whisper_tab, "Whisper下载")
        content_layout.addWidget(self.tab_widget)

        # Save button (outside tabs)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        save_btn = QPushButton("保存设置")
        save_btn.setFont(QFont("Microsoft YaHei", 10))
        save_btn.setStyleSheet("""
            QPushButton {
                color: #ffffff;
                background-color: #0066cc;
                border: 1px solid #0055aa;
                padding: 8px 24px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #0055aa;
            }
        """)
        save_btn.clicked.connect(self._save_config)
        btn_layout.addWidget(save_btn)

        content_layout.addLayout(btn_layout)
        content_layout.addStretch()

        layout.addWidget(content_frame)

    def _create_section_header(self, title: str) -> QLabel:
        label = QLabel(title)
        label.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        label.setStyleSheet("color: #333333; border: none; padding-bottom: 5px;")
        return label

    def _get_input_style(self) -> str:
        return get_input_style()

    def _get_spin_style(self) -> str:
        return get_spin_style()

    def _get_label_style(self) -> str:
        return get_label_style()

    def _create_separator(self) -> QFrame:
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #e0e0e0; border: none; max-height: 1px;")
        return separator

    def _create_image_api_tab(self) -> QWidget:
        """Image API configuration tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(4)

        # API configuration section
        layout.addWidget(self._create_image_api_section())
        layout.addWidget(self._create_separator())

        # Image parameters section
        layout.addWidget(self._create_image_params_section())
        layout.addWidget(self._create_separator())

        # Advanced settings section (for image)
        layout.addWidget(self._create_image_advanced_section())

        layout.addStretch()
        return widget

    def _create_video_api_tab(self) -> QWidget:
        """Video API configuration tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(4)

        # API configuration section
        layout.addWidget(self._create_video_api_section())
        layout.addWidget(self._create_separator())

        # Video parameters section
        layout.addWidget(self._create_video_params_section())
        layout.addWidget(self._create_separator())

        # Advanced settings section (for video)
        layout.addWidget(self._create_video_advanced_section())

        layout.addStretch()
        return widget

    def _create_image_api_section(self) -> QWidget:
        """Image API configuration section"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(self._create_section_header("API 配置"))

        form = QFormLayout()
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignRight)

        input_style = self._get_input_style()
        label_style = self._get_label_style()

        self.api_url_input = QLineEdit()
        self.api_url_input.setPlaceholderText("https://jimengly.zeabur.app")
        self.api_url_input.setStyleSheet(input_style)
        url_label = QLabel("API 地址:")
        url_label.setStyleSheet(label_style)
        form.addRow(url_label, self.api_url_input)

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("输入 API Key (支持多个，用逗号分隔)")
        self.api_key_input.setStyleSheet(input_style)
        key_label = QLabel("API Key:")
        key_label.setStyleSheet(label_style)
        form.addRow(key_label, self.api_key_input)

        self.model_combo = QComboBox()
        self.model_combo.addItems(Config.MODELS)
        self.model_combo.setStyleSheet(input_style)
        model_label = QLabel("模型:")
        model_label.setStyleSheet(label_style)
        form.addRow(model_label, self.model_combo)

        layout.addLayout(form)
        return widget

    def _create_image_params_section(self) -> QWidget:
        """Image generation parameters section"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(self._create_section_header("生图参数"))

        form = QFormLayout()
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignRight)

        input_style = self._get_input_style()
        label_style = self._get_label_style()

        self.ratio_combo = QComboBox()
        self.ratio_combo.addItems(Config.RATIOS)
        self.ratio_combo.setStyleSheet(input_style)
        ratio_label = QLabel("宽高比:")
        ratio_label.setStyleSheet(label_style)
        form.addRow(ratio_label, self.ratio_combo)

        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(Config.RESOLUTIONS)
        self.resolution_combo.setStyleSheet(input_style)
        res_label = QLabel("分辨率:")
        res_label.setStyleSheet(label_style)
        form.addRow(res_label, self.resolution_combo)

        layout.addLayout(form)
        return widget

    def _create_image_advanced_section(self) -> QWidget:
        """Image advanced settings section"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(self._create_section_header("高级设置"))

        form = QFormLayout()
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignRight)

        spin_style = self._get_spin_style()
        label_style = self._get_label_style()

        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(0, 10)
        self.retries_spin.setValue(3)
        self.retries_spin.setStyleSheet(spin_style)
        retries_label = QLabel("重试次数:")
        retries_label.setStyleSheet(label_style)
        form.addRow(retries_label, self.retries_spin)

        layout.addLayout(form)
        return widget

    def _create_video_api_section(self) -> QWidget:
        """Video API configuration section"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(self._create_section_header("API 配置"))

        form = QFormLayout()
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignRight)

        input_style = self._get_input_style()
        label_style = self._get_label_style()

        self.video_api_url_input = QLineEdit()
        self.video_api_url_input.setPlaceholderText("https://yunwu.ai")
        self.video_api_url_input.setStyleSheet(input_style)
        url_label = QLabel("API 地址:")
        url_label.setStyleSheet(label_style)
        form.addRow(url_label, self.video_api_url_input)

        self.video_api_key_input = QLineEdit()
        self.video_api_key_input.setEchoMode(QLineEdit.Password)
        self.video_api_key_input.setPlaceholderText("输入视频 API Key")
        self.video_api_key_input.setStyleSheet(input_style)
        key_label = QLabel("API Key:")
        key_label.setStyleSheet(label_style)
        form.addRow(key_label, self.video_api_key_input)

        self.video_model_input = QLineEdit()
        self.video_model_input.setPlaceholderText("输入视频模型名称，如 sora-2")
        self.video_model_input.setStyleSheet(input_style)
        model_label = QLabel("模型:")
        model_label.setStyleSheet(label_style)
        form.addRow(model_label, self.video_model_input)

        layout.addLayout(form)
        return widget

    def _create_video_params_section(self) -> QWidget:
        """Video generation parameters section"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(self._create_section_header("视频参数"))

        form = QFormLayout()
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignRight)

        input_style = self._get_input_style()
        label_style = self._get_label_style()

        self.video_seconds_combo = QComboBox()
        self.video_seconds_combo.addItems(Config.VIDEO_SECONDS)
        self.video_seconds_combo.setStyleSheet(input_style)
        seconds_label = QLabel("视频时长:")
        seconds_label.setStyleSheet(label_style)
        form.addRow(seconds_label, self.video_seconds_combo)

        self.video_size_combo = QComboBox()
        self.video_size_combo.addItems(Config.VIDEO_SIZES)
        self.video_size_combo.setStyleSheet(input_style)
        size_label = QLabel("视频尺寸:")
        size_label.setStyleSheet(label_style)
        form.addRow(size_label, self.video_size_combo)

        layout.addLayout(form)
        return widget

    def _create_video_advanced_section(self) -> QWidget:
        """Video advanced settings section"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(self._create_section_header("高级设置"))

        form = QFormLayout()
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignRight)

        spin_style = self._get_spin_style()
        label_style = self._get_label_style()

        self.video_retries_spin = QSpinBox()
        self.video_retries_spin.setRange(0, 10)
        self.video_retries_spin.setValue(3)
        self.video_retries_spin.setStyleSheet(spin_style)
        retries_label = QLabel("重试次数:")
        retries_label.setStyleSheet(label_style)
        form.addRow(retries_label, self.video_retries_spin)

        layout.addLayout(form)
        return widget

    def _create_copywriting_api_tab(self) -> QWidget:
        """Copywriting API configuration tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(4)

        # API configuration section
        layout.addWidget(self._create_copywriting_api_section())

        layout.addStretch()
        return widget

    def _create_copywriting_api_section(self) -> QWidget:
        """Copywriting API configuration section"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(self._create_section_header("API 配置"))

        form = QFormLayout()
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignRight)

        input_style = self._get_input_style()
        label_style = self._get_label_style()

        self.copywriting_api_url_input = QLineEdit()
        self.copywriting_api_url_input.setPlaceholderText("https://api.openai.com")
        self.copywriting_api_url_input.setStyleSheet(input_style)
        url_label = QLabel("API 地址:")
        url_label.setStyleSheet(label_style)
        form.addRow(url_label, self.copywriting_api_url_input)

        self.copywriting_api_key_input = QLineEdit()
        self.copywriting_api_key_input.setEchoMode(QLineEdit.Password)
        self.copywriting_api_key_input.setPlaceholderText("输入 API Key")
        self.copywriting_api_key_input.setStyleSheet(input_style)
        key_label = QLabel("API Key:")
        key_label.setStyleSheet(label_style)
        form.addRow(key_label, self.copywriting_api_key_input)

        # Model selection with query button
        model_layout = QHBoxLayout()
        model_layout.setSpacing(3)

        self.copywriting_model_combo = QComboBox()
        self.copywriting_model_combo.setEditable(True)
        self.copywriting_model_combo.setMinimumWidth(200)
        self.copywriting_model_combo.addItems(["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"])
        self.copywriting_model_combo.setStyleSheet(input_style)
        model_layout.addWidget(self.copywriting_model_combo)

        btn_style = """
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 6px 12px;
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

        self.query_models_btn = QPushButton("查询模型")
        self.query_models_btn.setFont(QFont("Microsoft YaHei", 9))
        self.query_models_btn.setStyleSheet(btn_style)
        self.query_models_btn.clicked.connect(self._on_query_models)
        model_layout.addWidget(self.query_models_btn)

        model_layout.addStretch()

        model_label = QLabel("模型ID:")
        model_label.setStyleSheet(label_style)
        form.addRow(model_label, model_layout)

        layout.addLayout(form)
        return widget

    def _create_rewrite_copywriting_api_tab(self) -> QWidget:
        """Rewrite Copywriting API configuration tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(4)

        layout.addWidget(self._create_rewrite_copywriting_api_section())

        layout.addStretch()
        return widget

    def _create_rewrite_copywriting_api_section(self) -> QWidget:
        """Rewrite Copywriting API configuration section"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(self._create_section_header("API 配置"))

        form = QFormLayout()
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignRight)

        input_style = self._get_input_style()
        label_style = self._get_label_style()

        self.rewrite_copywriting_api_url_input = QLineEdit()
        self.rewrite_copywriting_api_url_input.setPlaceholderText("https://api.openai.com")
        self.rewrite_copywriting_api_url_input.setStyleSheet(input_style)
        url_label = QLabel("API 地址:")
        url_label.setStyleSheet(label_style)
        form.addRow(url_label, self.rewrite_copywriting_api_url_input)

        self.rewrite_copywriting_api_key_input = QLineEdit()
        self.rewrite_copywriting_api_key_input.setEchoMode(QLineEdit.Password)
        self.rewrite_copywriting_api_key_input.setPlaceholderText("输入 API Key")
        self.rewrite_copywriting_api_key_input.setStyleSheet(input_style)
        key_label = QLabel("API Key:")
        key_label.setStyleSheet(label_style)
        form.addRow(key_label, self.rewrite_copywriting_api_key_input)

        # Model selection with query button
        model_layout = QHBoxLayout()
        model_layout.setSpacing(3)

        self.rewrite_copywriting_model_combo = QComboBox()
        self.rewrite_copywriting_model_combo.setEditable(True)
        self.rewrite_copywriting_model_combo.setMinimumWidth(200)
        self.rewrite_copywriting_model_combo.addItems(["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"])
        self.rewrite_copywriting_model_combo.setStyleSheet(input_style)
        model_layout.addWidget(self.rewrite_copywriting_model_combo)

        btn_style = """
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 6px 12px;
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

        self.rewrite_query_models_btn = QPushButton("查询模型")
        self.rewrite_query_models_btn.setFont(QFont("Microsoft YaHei", 9))
        self.rewrite_query_models_btn.setStyleSheet(btn_style)
        self.rewrite_query_models_btn.clicked.connect(self._on_rewrite_query_models)
        model_layout.addWidget(self.rewrite_query_models_btn)

        model_layout.addStretch()

        model_label = QLabel("模型ID:")
        model_label.setStyleSheet(label_style)
        form.addRow(model_label, model_layout)

        layout.addLayout(form)
        return widget

    def _on_rewrite_query_models(self):
        """Query available models from Rewrite Copywriting API"""
        base_url = self.rewrite_copywriting_api_url_input.text().strip()
        api_key = self.rewrite_copywriting_api_key_input.text().strip()

        if not base_url:
            QMessageBox.warning(self, "提示", "请先输入 API 地址")
            return

        if not api_key:
            QMessageBox.warning(self, "提示", "请先输入 API Key")
            return

        self.rewrite_query_models_btn.setEnabled(False)
        self.rewrite_query_models_btn.setText("查询中...")

        self._rewrite_model_query_worker = RewriteModelQueryWorker(base_url, api_key)
        self._rewrite_model_query_worker.finished_signal.connect(self._on_rewrite_models_queried)
        self._rewrite_model_query_worker.start()

    def _on_rewrite_models_queried(self, success: bool, models: list, error: str):
        """Handle rewrite model query result"""
        self.rewrite_query_models_btn.setEnabled(True)
        self.rewrite_query_models_btn.setText("查询模型")

        if success:
            current_model = self.rewrite_copywriting_model_combo.currentText()
            self.rewrite_copywriting_model_combo.clear()
            self.rewrite_copywriting_model_combo.addItems(models)

            # Restore previous selection if exists
            index = self.rewrite_copywriting_model_combo.findText(current_model)
            if index >= 0:
                self.rewrite_copywriting_model_combo.setCurrentIndex(index)

            QMessageBox.information(self, "成功", f"查询到 {len(models)} 个模型")
        else:
            QMessageBox.warning(self, "查询失败", error)

    def _create_image_recognition_api_tab(self) -> QWidget:
        """Image Recognition API configuration tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(4)

        layout.addWidget(self._create_image_recognition_api_section())

        layout.addStretch()
        return widget

    def _create_image_recognition_api_section(self) -> QWidget:
        """Image Recognition API configuration section"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(self._create_section_header("API 配置"))

        form = QFormLayout()
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignRight)

        input_style = self._get_input_style()
        label_style = self._get_label_style()

        self.image_recognition_api_url_input = QLineEdit()
        self.image_recognition_api_url_input.setPlaceholderText("https://yunwu.ai")
        self.image_recognition_api_url_input.setStyleSheet(input_style)
        url_label = QLabel("API 地址:")
        url_label.setStyleSheet(label_style)
        form.addRow(url_label, self.image_recognition_api_url_input)

        self.image_recognition_api_key_input = QLineEdit()
        self.image_recognition_api_key_input.setEchoMode(QLineEdit.Password)
        self.image_recognition_api_key_input.setPlaceholderText("输入 API Key")
        self.image_recognition_api_key_input.setStyleSheet(input_style)
        key_label = QLabel("API Key:")
        key_label.setStyleSheet(label_style)
        form.addRow(key_label, self.image_recognition_api_key_input)

        self.image_recognition_model_input = QLineEdit()
        self.image_recognition_model_input.setPlaceholderText("gemini-2.0-flash")
        self.image_recognition_model_input.setStyleSheet(input_style)
        model_label = QLabel("模型:")
        model_label.setStyleSheet(label_style)
        form.addRow(model_label, self.image_recognition_model_input)

        layout.addLayout(form)
        return widget

    def _create_merge_copywriting_api_tab(self) -> QWidget:
        """Merge Copywriting API configuration tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(4)

        layout.addWidget(self._create_merge_copywriting_api_section())

        layout.addStretch()
        return widget

    def _create_merge_copywriting_api_section(self) -> QWidget:
        """Merge Copywriting API configuration section"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(self._create_section_header("API 配置"))

        form = QFormLayout()
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignRight)

        input_style = self._get_input_style()
        label_style = self._get_label_style()

        self.merge_copywriting_api_url_input = QLineEdit()
        self.merge_copywriting_api_url_input.setPlaceholderText("https://api.openai.com")
        self.merge_copywriting_api_url_input.setStyleSheet(input_style)
        url_label = QLabel("API 地址:")
        url_label.setStyleSheet(label_style)
        form.addRow(url_label, self.merge_copywriting_api_url_input)

        self.merge_copywriting_api_key_input = QLineEdit()
        self.merge_copywriting_api_key_input.setEchoMode(QLineEdit.Password)
        self.merge_copywriting_api_key_input.setPlaceholderText("输入 API Key")
        self.merge_copywriting_api_key_input.setStyleSheet(input_style)
        key_label = QLabel("API Key:")
        key_label.setStyleSheet(label_style)
        form.addRow(key_label, self.merge_copywriting_api_key_input)

        # Model selection with query button
        model_layout = QHBoxLayout()
        model_layout.setSpacing(3)

        self.merge_copywriting_model_combo = QComboBox()
        self.merge_copywriting_model_combo.setEditable(True)
        self.merge_copywriting_model_combo.setMinimumWidth(200)
        self.merge_copywriting_model_combo.addItems(["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"])
        self.merge_copywriting_model_combo.setStyleSheet(input_style)
        model_layout.addWidget(self.merge_copywriting_model_combo)

        btn_style = """
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 6px 12px;
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

        self.merge_query_models_btn = QPushButton("查询模型")
        self.merge_query_models_btn.setFont(QFont("Microsoft YaHei", 9))
        self.merge_query_models_btn.setStyleSheet(btn_style)
        self.merge_query_models_btn.clicked.connect(self._on_merge_query_models)
        model_layout.addWidget(self.merge_query_models_btn)

        model_layout.addStretch()

        model_label = QLabel("模型ID:")
        model_label.setStyleSheet(label_style)
        form.addRow(model_label, model_layout)

        layout.addLayout(form)
        return widget

    def _create_tts_api_tab(self) -> QWidget:
        """TTS API configuration tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(4)

        layout.addWidget(self._create_tts_api_section())

        layout.addStretch()
        return widget

    def _create_tts_api_section(self) -> QWidget:
        """TTS API configuration section"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(self._create_section_header("API 配置"))

        form = QFormLayout()
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignRight)

        input_style = self._get_input_style()
        label_style = self._get_label_style()
        spin_style = self._get_spin_style()

        self.tts_api_url_input = QLineEdit()
        self.tts_api_url_input.setPlaceholderText("https://yunwu.ai")
        self.tts_api_url_input.setStyleSheet(input_style)
        url_label = QLabel("API 地址:")
        url_label.setStyleSheet(label_style)
        form.addRow(url_label, self.tts_api_url_input)

        self.tts_api_key_input = QLineEdit()
        self.tts_api_key_input.setEchoMode(QLineEdit.Password)
        self.tts_api_key_input.setPlaceholderText("输入 API Key")
        self.tts_api_key_input.setStyleSheet(input_style)
        key_label = QLabel("API Key:")
        key_label.setStyleSheet(label_style)
        form.addRow(key_label, self.tts_api_key_input)

        self.tts_model_combo = QComboBox()
        self.tts_model_combo.setEditable(True)
        self.tts_model_combo.setMinimumWidth(200)
        self.tts_model_combo.addItems(["gpt-4o-mini-tts", "tts-1", "tts-1-hd"])
        self.tts_model_combo.setStyleSheet(input_style)
        model_label = QLabel("模型:")
        model_label.setStyleSheet(label_style)
        form.addRow(model_label, self.tts_model_combo)

        self.tts_voice_combo = QComboBox()
        self.tts_voice_combo.addItems(["alloy", "echo", "fable", "onyx", "nova", "shimmer"])
        self.tts_voice_combo.setStyleSheet(input_style)
        voice_label = QLabel("音色:")
        voice_label.setStyleSheet(label_style)
        form.addRow(voice_label, self.tts_voice_combo)

        self.tts_speed_spin = QDoubleSpinBox()
        self.tts_speed_spin.setRange(0.25, 4.0)
        self.tts_speed_spin.setSingleStep(0.25)
        self.tts_speed_spin.setValue(1.0)
        self.tts_speed_spin.setStyleSheet(spin_style)
        speed_label = QLabel("语速:")
        speed_label.setStyleSheet(label_style)
        form.addRow(speed_label, self.tts_speed_spin)

        self.tts_concurrent_spin = QSpinBox()
        self.tts_concurrent_spin.setRange(1, 10)
        self.tts_concurrent_spin.setValue(3)
        self.tts_concurrent_spin.setStyleSheet(spin_style)
        concurrent_label = QLabel("并发数:")
        concurrent_label.setStyleSheet(label_style)
        form.addRow(concurrent_label, self.tts_concurrent_spin)

        self.tts_retries_spin = QSpinBox()
        self.tts_retries_spin.setRange(0, 10)
        self.tts_retries_spin.setValue(3)
        self.tts_retries_spin.setStyleSheet(spin_style)
        retries_label = QLabel("重试次数:")
        retries_label.setStyleSheet(label_style)
        form.addRow(retries_label, self.tts_retries_spin)

        layout.addLayout(form)
        return widget

    def _create_subtitle_api_tab(self) -> QWidget:
        """Subtitle API configuration tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(4)

        layout.addWidget(self._create_subtitle_api_section())

        layout.addStretch()
        return widget

    def _create_subtitle_api_section(self) -> QWidget:
        """Subtitle API configuration section"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(self._create_section_header("API 配置"))

        form = QFormLayout()
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignRight)

        input_style = self._get_input_style()
        label_style = self._get_label_style()

        self.subtitle_api_url_input = QLineEdit()
        self.subtitle_api_url_input.setPlaceholderText("https://yunwu.ai")
        self.subtitle_api_url_input.setStyleSheet(input_style)
        url_label = QLabel("API 地址:")
        url_label.setStyleSheet(label_style)
        form.addRow(url_label, self.subtitle_api_url_input)

        self.subtitle_api_key_input = QLineEdit()
        self.subtitle_api_key_input.setEchoMode(QLineEdit.Password)
        self.subtitle_api_key_input.setPlaceholderText("输入 API Key")
        self.subtitle_api_key_input.setStyleSheet(input_style)
        key_label = QLabel("API Key:")
        key_label.setStyleSheet(label_style)
        form.addRow(key_label, self.subtitle_api_key_input)

        self.subtitle_model_combo = QComboBox()
        self.subtitle_model_combo.setEditable(True)
        self.subtitle_model_combo.setMinimumWidth(200)
        self.subtitle_model_combo.addItems(["whisper-1", "gpt-4o-mini-transcribe", "gpt-4o-transcribe"])
        self.subtitle_model_combo.setStyleSheet(input_style)
        model_label = QLabel("模型:")
        model_label.setStyleSheet(label_style)
        form.addRow(model_label, self.subtitle_model_combo)

        self.subtitle_language_combo = QComboBox()
        self.subtitle_language_combo.addItems(["zh", "en", "ja", "ko", "auto"])
        self.subtitle_language_combo.setStyleSheet(input_style)
        language_label = QLabel("语言:")
        language_label.setStyleSheet(label_style)
        form.addRow(language_label, self.subtitle_language_combo)

        # 添加"强制简体中文"复选框
        self.force_simplified_checkbox = QCheckBox("强制转换为简体中文")
        self.force_simplified_checkbox.setStyleSheet("""
            QCheckBox {
                color: #333333;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #b0b0b0;
                border-radius: 3px;
                background-color: #ffffff;
            }
            QCheckBox::indicator:checked {
                background-color: #0066cc;
                border-color: #0066cc;
            }
        """)
        form.addRow("", self.force_simplified_checkbox)

        # 每段字幕最大字数
        self.max_chars_spinbox = QSpinBox()
        self.max_chars_spinbox.setRange(0, 50)
        self.max_chars_spinbox.setValue(0)
        self.max_chars_spinbox.setSpecialValueText("不拆分")
        self.max_chars_spinbox.setSuffix(" 字")
        self.max_chars_spinbox.setStyleSheet("""
            QSpinBox {
                padding: 4px 8px;
                border: 1px solid #b0b0b0;
                border-radius: 4px;
                font-size: 13px;
                min-width: 100px;
            }
        """)
        form.addRow("每段字幕最大字数", self.max_chars_spinbox)

        layout.addLayout(form)
        return widget

    def _create_product_time_api_tab(self) -> QWidget:
        """Product Time API configuration tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 6, 4, 4)
        layout.setSpacing(4)

        layout.addWidget(self._create_product_time_api_section())

        layout.addStretch()
        return widget

    def _create_product_time_api_section(self) -> QWidget:
        """Product Time API configuration section"""
        widget = QWidget()
        widget.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(self._create_section_header("API 配置"))

        form = QFormLayout()
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignRight)

        input_style = self._get_input_style()
        label_style = self._get_label_style()

        self.product_time_api_url_input = QLineEdit()
        self.product_time_api_url_input.setPlaceholderText("https://yunwu.ai")
        self.product_time_api_url_input.setStyleSheet(input_style)
        url_label = QLabel("API 地址:")
        url_label.setStyleSheet(label_style)
        form.addRow(url_label, self.product_time_api_url_input)

        self.product_time_api_key_input = QLineEdit()
        self.product_time_api_key_input.setEchoMode(QLineEdit.Password)
        self.product_time_api_key_input.setPlaceholderText("输入 API Key")
        self.product_time_api_key_input.setStyleSheet(input_style)
        key_label = QLabel("API Key:")
        key_label.setStyleSheet(label_style)
        form.addRow(key_label, self.product_time_api_key_input)

        # Model selection with query button
        model_layout = QHBoxLayout()
        model_layout.setSpacing(3)

        self.product_time_model_combo = QComboBox()
        self.product_time_model_combo.setEditable(True)
        self.product_time_model_combo.setMinimumWidth(200)
        self.product_time_model_combo.addItems(["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"])
        self.product_time_model_combo.setStyleSheet(input_style)
        model_layout.addWidget(self.product_time_model_combo)

        btn_style = """
            QPushButton {
                color: #0066cc;
                background-color: #f8f8f8;
                border: 1px solid #d0d0d0;
                padding: 6px 12px;
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

        self.product_time_query_models_btn = QPushButton("查询模型")
        self.product_time_query_models_btn.setFont(QFont("Microsoft YaHei", 9))
        self.product_time_query_models_btn.setStyleSheet(btn_style)
        self.product_time_query_models_btn.clicked.connect(self._on_product_time_query_models)
        model_layout.addWidget(self.product_time_query_models_btn)

        model_layout.addStretch()

        model_label = QLabel("模型ID:")
        model_label.setStyleSheet(label_style)
        form.addRow(model_label, model_layout)

        layout.addLayout(form)

        # Prompt section
        layout.addWidget(self._create_section_header("提示词"))

        self.product_time_prompt_edit = QTextEdit()
        self.product_time_prompt_edit.setMinimumHeight(200)
        self.product_time_prompt_edit.setStyleSheet("""
            QTextEdit {
                border: 1px solid #d0d0d0;
                padding: 8px;
                background-color: #ffffff;
                font-family: "Microsoft YaHei", monospace;
                font-size: 12px;
            }
            QTextEdit:focus {
                border-color: #0066cc;
            }
        """)
        layout.addWidget(self.product_time_prompt_edit)

        return widget

    def _on_product_time_query_models(self):
        """Query available models from Product Time API"""
        base_url = self.product_time_api_url_input.text().strip()
        api_key = self.product_time_api_key_input.text().strip()

        if not base_url:
            QMessageBox.warning(self, "提示", "请先输入 API 地址")
            return

        if not api_key:
            QMessageBox.warning(self, "提示", "请先输入 API Key")
            return

        self.product_time_query_models_btn.setEnabled(False)
        self.product_time_query_models_btn.setText("查询中...")

        self._product_time_model_query_worker = ProductTimeModelQueryWorker(base_url, api_key)
        self._product_time_model_query_worker.finished_signal.connect(self._on_product_time_models_queried)
        self._product_time_model_query_worker.start()

    def _on_product_time_models_queried(self, success: bool, models: list, error: str):
        """Handle product time model query result"""
        self.product_time_query_models_btn.setEnabled(True)
        self.product_time_query_models_btn.setText("查询模型")

        if success:
            current_model = self.product_time_model_combo.currentText()
            self.product_time_model_combo.clear()
            self.product_time_model_combo.addItems(models)

            # Restore previous selection if exists
            index = self.product_time_model_combo.findText(current_model)
            if index >= 0:
                self.product_time_model_combo.setCurrentIndex(index)

            QMessageBox.information(self, "成功", f"查询到 {len(models)} 个模型")
        else:
            QMessageBox.warning(self, "查询失败", error)

    def _on_merge_query_models(self):
        """Query available models from Merge Copywriting API"""
        base_url = self.merge_copywriting_api_url_input.text().strip()
        api_key = self.merge_copywriting_api_key_input.text().strip()

        if not base_url:
            QMessageBox.warning(self, "提示", "请先输入 API 地址")
            return

        if not api_key:
            QMessageBox.warning(self, "提示", "请先输入 API Key")
            return

        self.merge_query_models_btn.setEnabled(False)
        self.merge_query_models_btn.setText("查询中...")

        self._merge_model_query_worker = MergeModelQueryWorker(base_url, api_key)
        self._merge_model_query_worker.finished_signal.connect(self._on_merge_models_queried)
        self._merge_model_query_worker.start()

    def _on_merge_models_queried(self, success: bool, models: list, error: str):
        """Handle merge model query result"""
        self.merge_query_models_btn.setEnabled(True)
        self.merge_query_models_btn.setText("查询模型")

        if success:
            current_model = self.merge_copywriting_model_combo.currentText()
            self.merge_copywriting_model_combo.clear()
            self.merge_copywriting_model_combo.addItems(models)

            # Restore previous selection if exists
            index = self.merge_copywriting_model_combo.findText(current_model)
            if index >= 0:
                self.merge_copywriting_model_combo.setCurrentIndex(index)

            QMessageBox.information(self, "成功", f"查询到 {len(models)} 个模型")
        else:
            QMessageBox.warning(self, "查询失败", error)

    def _on_query_models(self):
        """Query available models from API"""
        base_url = self.copywriting_api_url_input.text().strip()
        api_key = self.copywriting_api_key_input.text().strip()

        if not base_url:
            QMessageBox.warning(self, "提示", "请先输入 API 地址")
            return

        if not api_key:
            QMessageBox.warning(self, "提示", "请先输入 API Key")
            return

        self.query_models_btn.setEnabled(False)
        self.query_models_btn.setText("查询中...")

        self._model_query_worker = ModelQueryWorker(base_url, api_key)
        self._model_query_worker.finished_signal.connect(self._on_models_queried)
        self._model_query_worker.start()

    def _on_models_queried(self, success: bool, models: list, error: str):
        """Handle model query result"""
        self.query_models_btn.setEnabled(True)
        self.query_models_btn.setText("查询模型")

        if success:
            current_model = self.copywriting_model_combo.currentText()
            self.copywriting_model_combo.clear()
            self.copywriting_model_combo.addItems(models)

            # Restore previous selection if exists
            index = self.copywriting_model_combo.findText(current_model)
            if index >= 0:
                self.copywriting_model_combo.setCurrentIndex(index)

            QMessageBox.information(self, "成功", f"查询到 {len(models)} 个模型")
        else:
            QMessageBox.warning(self, "查询失败", error)

    def _load_config(self):
        # Image API config
        self.api_url_input.setText(self.config.api.base_url)
        self.api_key_input.setText(self.config.api.api_key)

        model_index = self.model_combo.findText(self.config.api.model)
        if model_index >= 0:
            self.model_combo.setCurrentIndex(model_index)

        ratio_index = self.ratio_combo.findText(self.config.api.ratio)
        if ratio_index >= 0:
            self.ratio_combo.setCurrentIndex(ratio_index)

        resolution_index = self.resolution_combo.findText(self.config.api.resolution)
        if resolution_index >= 0:
            self.resolution_combo.setCurrentIndex(resolution_index)

        self.retries_spin.setValue(self.config.settings.max_retries)

        # Video API config
        self.video_api_url_input.setText(self.config.video_api.base_url)
        self.video_api_key_input.setText(self.config.video_api.api_key)

        self.video_model_input.setText(self.config.video_api.model)

        video_seconds_index = self.video_seconds_combo.findText(self.config.video_api.seconds)
        if video_seconds_index >= 0:
            self.video_seconds_combo.setCurrentIndex(video_seconds_index)

        video_size_index = self.video_size_combo.findText(self.config.video_api.size)
        if video_size_index >= 0:
            self.video_size_combo.setCurrentIndex(video_size_index)

        self.video_retries_spin.setValue(self.config.video_api.max_retries)

        # Copywriting API config
        self.copywriting_api_url_input.setText(self.config.copywriting_api.base_url)
        self.copywriting_api_key_input.setText(self.config.copywriting_api.api_key)

        model_index = self.copywriting_model_combo.findText(self.config.copywriting_api.model)
        if model_index >= 0:
            self.copywriting_model_combo.setCurrentIndex(model_index)
        else:
            self.copywriting_model_combo.setCurrentText(self.config.copywriting_api.model)

        # Image Recognition API config
        self.image_recognition_api_url_input.setText(self.config.image_recognition_api.base_url)
        self.image_recognition_api_key_input.setText(self.config.image_recognition_api.api_key)
        self.image_recognition_model_input.setText(self.config.image_recognition_api.model)

        # Merge Copywriting API config
        self.merge_copywriting_api_url_input.setText(self.config.merge_copywriting_api.base_url)
        self.merge_copywriting_api_key_input.setText(self.config.merge_copywriting_api.api_key)

        model_index = self.merge_copywriting_model_combo.findText(self.config.merge_copywriting_api.model)
        if model_index >= 0:
            self.merge_copywriting_model_combo.setCurrentIndex(model_index)
        else:
            self.merge_copywriting_model_combo.setCurrentText(self.config.merge_copywriting_api.model)

        # Rewrite Copywriting API config
        self.rewrite_copywriting_api_url_input.setText(self.config.rewrite_copywriting_api.base_url)
        self.rewrite_copywriting_api_key_input.setText(self.config.rewrite_copywriting_api.api_key)

        model_index = self.rewrite_copywriting_model_combo.findText(self.config.rewrite_copywriting_api.model)
        if model_index >= 0:
            self.rewrite_copywriting_model_combo.setCurrentIndex(model_index)
        else:
            self.rewrite_copywriting_model_combo.setCurrentText(self.config.rewrite_copywriting_api.model)

        # TTS API config
        self.tts_api_url_input.setText(self.config.tts_api.base_url)
        self.tts_api_key_input.setText(self.config.tts_api.api_key)

        model_index = self.tts_model_combo.findText(self.config.tts_api.model)
        if model_index >= 0:
            self.tts_model_combo.setCurrentIndex(model_index)
        else:
            self.tts_model_combo.setCurrentText(self.config.tts_api.model)

        voice_index = self.tts_voice_combo.findText(self.config.tts_api.voice)
        if voice_index >= 0:
            self.tts_voice_combo.setCurrentIndex(voice_index)

        self.tts_speed_spin.setValue(self.config.tts_api.speed)
        self.tts_concurrent_spin.setValue(self.config.tts_api.max_concurrent)
        self.tts_retries_spin.setValue(self.config.tts_api.max_retries)

        # Subtitle API config
        self.subtitle_api_url_input.setText(self.config.subtitle_api.base_url)
        self.subtitle_api_key_input.setText(self.config.subtitle_api.api_key)

        model_index = self.subtitle_model_combo.findText(self.config.subtitle_api.model)
        if model_index >= 0:
            self.subtitle_model_combo.setCurrentIndex(model_index)
        else:
            self.subtitle_model_combo.setCurrentText(self.config.subtitle_api.model)

        language_index = self.subtitle_language_combo.findText(self.config.subtitle_api.language)
        if language_index >= 0:
            self.subtitle_language_combo.setCurrentIndex(language_index)

        # 加载"强制简体中文"设置
        self.force_simplified_checkbox.setChecked(self.config.subtitle_api.force_simplified)

        # 加载"每段字幕最大字数"设置
        self.max_chars_spinbox.setValue(self.config.subtitle_api.max_chars_per_segment)

        # Product Time API config
        self.product_time_api_url_input.setText(self.config.product_time_api.base_url)
        self.product_time_api_key_input.setText(self.config.product_time_api.api_key)

        model_index = self.product_time_model_combo.findText(self.config.product_time_api.model)
        if model_index >= 0:
            self.product_time_model_combo.setCurrentIndex(model_index)
        else:
            self.product_time_model_combo.setCurrentText(self.config.product_time_api.model)

        self.product_time_prompt_edit.setPlainText(self.config.product_time_api.prompt)

    def _save_config(self):
        # Image API config
        self.config.api.base_url = self.api_url_input.text().strip() or "https://jimengly.zeabur.app"
        self.config.api.api_key = self.api_key_input.text().strip()
        self.config.api.model = self.model_combo.currentText()
        self.config.api.ratio = self.ratio_combo.currentText()
        self.config.api.resolution = self.resolution_combo.currentText()

        self.config.settings.max_retries = self.retries_spin.value()

        # Video API config
        self.config.video_api.base_url = self.video_api_url_input.text().strip() or "https://yunwu.ai"
        self.config.video_api.api_key = self.video_api_key_input.text().strip()
        self.config.video_api.model = self.video_model_input.text().strip() or "sora-2"
        self.config.video_api.seconds = self.video_seconds_combo.currentText()
        self.config.video_api.size = self.video_size_combo.currentText()
        self.config.video_api.max_retries = self.video_retries_spin.value()

        # Copywriting API config
        self.config.copywriting_api.base_url = self.copywriting_api_url_input.text().strip() or "https://api.openai.com"
        self.config.copywriting_api.api_key = self.copywriting_api_key_input.text().strip()
        self.config.copywriting_api.model = self.copywriting_model_combo.currentText().strip() or "gpt-4o"

        # Image Recognition API config
        self.config.image_recognition_api.base_url = self.image_recognition_api_url_input.text().strip() or "https://yunwu.ai"
        self.config.image_recognition_api.api_key = self.image_recognition_api_key_input.text().strip()
        self.config.image_recognition_api.model = self.image_recognition_model_input.text().strip() or "gemini-2.0-flash"

        # Merge Copywriting API config
        self.config.merge_copywriting_api.base_url = self.merge_copywriting_api_url_input.text().strip() or "https://api.openai.com"
        self.config.merge_copywriting_api.api_key = self.merge_copywriting_api_key_input.text().strip()
        self.config.merge_copywriting_api.model = self.merge_copywriting_model_combo.currentText().strip() or "gpt-4o"

        # Rewrite Copywriting API config
        self.config.rewrite_copywriting_api.base_url = self.rewrite_copywriting_api_url_input.text().strip() or "https://api.openai.com"
        self.config.rewrite_copywriting_api.api_key = self.rewrite_copywriting_api_key_input.text().strip()
        self.config.rewrite_copywriting_api.model = self.rewrite_copywriting_model_combo.currentText().strip() or "gpt-4o"

        # TTS API config
        self.config.tts_api.base_url = self.tts_api_url_input.text().strip() or "https://yunwu.ai"
        self.config.tts_api.api_key = self.tts_api_key_input.text().strip()
        self.config.tts_api.model = self.tts_model_combo.currentText().strip() or "gpt-4o-mini-tts"
        self.config.tts_api.voice = self.tts_voice_combo.currentText()
        self.config.tts_api.speed = self.tts_speed_spin.value()
        self.config.tts_api.max_concurrent = self.tts_concurrent_spin.value()
        self.config.tts_api.max_retries = self.tts_retries_spin.value()

        # Subtitle API config
        self.config.subtitle_api.base_url = self.subtitle_api_url_input.text().strip() or "https://yunwu.ai"
        self.config.subtitle_api.api_key = self.subtitle_api_key_input.text().strip()
        self.config.subtitle_api.model = self.subtitle_model_combo.currentText().strip() or "whisper-1"
        self.config.subtitle_api.language = self.subtitle_language_combo.currentText()
        # 保存"强制简体中文"设置
        self.config.subtitle_api.force_simplified = self.force_simplified_checkbox.isChecked()
        # 保存"每段字幕最大字数"设置
        self.config.subtitle_api.max_chars_per_segment = self.max_chars_spinbox.value()

        # Product Time API config
        self.config.product_time_api.base_url = self.product_time_api_url_input.text().strip() or "https://yunwu.ai"
        self.config.product_time_api.api_key = self.product_time_api_key_input.text().strip()
        self.config.product_time_api.model = self.product_time_model_combo.currentText().strip() or "gpt-4o-mini"
        self.config.product_time_api.prompt = self.product_time_prompt_edit.toPlainText()

        self.config.save()

        QMessageBox.information(self, "保存成功", "设置已保存")
