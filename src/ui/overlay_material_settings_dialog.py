import os

from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QPushButton,
    QCheckBox,
    QGroupBox,
    QRadioButton,
    QButtonGroup,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from ..models.config import OverlayMaterialConfig

SUPPORTED_VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv'}


class OverlayMaterialSettingsDialog(QDialog):
    def __init__(self, config: OverlayMaterialConfig, overlay_base_dir: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("叠加素材设置")
        self.setMinimumWidth(420)
        self._config = config
        self._overlay_base_dir = overlay_base_dir
        self._folder_widgets = {}  # name -> (QCheckBox, QSlider)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.enabled_checkbox = QCheckBox("启用叠加素材")
        self.enabled_checkbox.setFont(QFont("Microsoft YaHei", 10))
        self.enabled_checkbox.setChecked(self._config.enabled)
        self.enabled_checkbox.toggled.connect(self._on_enabled_toggled)
        layout.addWidget(self.enabled_checkbox)

        # 选择模式：随机 或 手动选择
        mode_group = QGroupBox("选择模式")
        mode_layout = QHBoxLayout()

        self._mode_button_group = QButtonGroup(self)
        self._random_radio = QRadioButton("随机选择")
        self._random_radio.setFont(QFont("Microsoft YaHei", 9))
        self._manual_radio = QRadioButton("手动选择")
        self._manual_radio.setFont(QFont("Microsoft YaHei", 9))

        self._mode_button_group.addButton(self._random_radio, 0)
        self._mode_button_group.addButton(self._manual_radio, 1)

        # 检查是否是随机模式（selections中有 "__random__" 键）
        is_random = "__random__" in self._config.selections
        self._random_radio.setChecked(is_random or not self._config.selections)
        self._manual_radio.setChecked(not is_random and bool(self._config.selections))

        self._random_radio.toggled.connect(self._on_mode_changed)

        mode_layout.addWidget(self._random_radio)
        mode_layout.addWidget(self._manual_radio)
        mode_layout.addStretch()
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # 随机模式的不透明度设置
        self._random_opacity_group = QGroupBox("随机模式设置")
        random_layout = QHBoxLayout()
        random_layout.addWidget(QLabel("不透明度:"))

        self._random_opacity_slider = QSlider(Qt.Horizontal)
        self._random_opacity_slider.setRange(0, 100)
        self._random_opacity_slider.setMinimumWidth(150)
        random_opacity = self._config.selections.get("__random__", 70)
        self._random_opacity_slider.setValue(random_opacity)

        self._random_opacity_label = QLabel(f"{random_opacity}%")
        self._random_opacity_label.setMinimumWidth(35)
        self._random_opacity_slider.valueChanged.connect(
            lambda v: self._random_opacity_label.setText(f"{v}%")
        )

        random_layout.addWidget(self._random_opacity_slider)
        random_layout.addWidget(self._random_opacity_label)
        random_layout.addStretch()
        self._random_opacity_group.setLayout(random_layout)
        layout.addWidget(self._random_opacity_group)

        # 手动选择的素材列表
        self.params_group = QGroupBox("手动选择素材")
        params_layout = QVBoxLayout()
        params_layout.setSpacing(6)

        subfolders = self._scan_subfolders()
        if not subfolders:
            params_layout.addWidget(QLabel("未找到叠加素材子文件夹"))
        else:
            for folder_name in subfolders:
                video_count = self._count_videos(folder_name)
                row = QHBoxLayout()
                row.setSpacing(8)

                cb = QCheckBox(f"{folder_name} ({video_count}个视频)")
                cb.setFont(QFont("Microsoft YaHei", 9))

                slider = QSlider(Qt.Horizontal)
                slider.setRange(0, 100)
                slider.setMinimumWidth(120)

                opacity_label = QLabel("70%")
                opacity_label.setMinimumWidth(35)

                if folder_name in self._config.selections:
                    cb.setChecked(True)
                    slider.setValue(self._config.selections[folder_name])
                else:
                    cb.setChecked(False)
                    slider.setValue(70)

                slider.valueChanged.connect(
                    lambda v, lbl=opacity_label: lbl.setText(f"{v}%")
                )
                opacity_label.setText(f"{slider.value()}%")

                row.addWidget(cb)
                row.addStretch()
                row.addWidget(QLabel("不透明度:"))
                row.addWidget(slider)
                row.addWidget(opacity_label)
                params_layout.addLayout(row)
                self._folder_widgets[folder_name] = (cb, slider)

        self.params_group.setLayout(params_layout)
        layout.addWidget(self.params_group)

        hint = QLabel(
            "随机模式：每次生成视频时随机选择一个素材文件夹。\n"
            "手动模式：使用勾选的素材，每个文件夹随机选取一个视频。\n"
            "叠加使用滤色混合，黑色背景自动去除。"
        )
        hint.setStyleSheet("color: #888888; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        ok_btn = QPushButton("确定")
        ok_btn.setMinimumWidth(80)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumWidth(80)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

        self._on_enabled_toggled(self._config.enabled)
        self._on_mode_changed()

    def _scan_subfolders(self) -> list:
        if not os.path.isdir(self._overlay_base_dir):
            return []
        return sorted([
            name for name in os.listdir(self._overlay_base_dir)
            if os.path.isdir(os.path.join(self._overlay_base_dir, name))
        ])

    def _count_videos(self, folder_name: str) -> int:
        folder_path = os.path.join(self._overlay_base_dir, folder_name)
        if not os.path.isdir(folder_path):
            return 0
        return sum(
            1 for f in os.listdir(folder_path)
            if os.path.splitext(f)[1].lower() in SUPPORTED_VIDEO_EXTENSIONS
        )

    def _on_enabled_toggled(self, checked: bool):
        self._random_radio.setEnabled(checked)
        self._manual_radio.setEnabled(checked)
        self._random_opacity_group.setEnabled(checked and self._random_radio.isChecked())
        self.params_group.setEnabled(checked and self._manual_radio.isChecked())

    def _on_mode_changed(self):
        is_random = self._random_radio.isChecked()
        self._random_opacity_group.setEnabled(self.enabled_checkbox.isChecked() and is_random)
        self.params_group.setEnabled(self.enabled_checkbox.isChecked() and not is_random)

    def get_config(self) -> OverlayMaterialConfig:
        selections = {}
        if self._random_radio.isChecked():
            # 随机模式：用特殊键 "__random__" 标记
            selections["__random__"] = self._random_opacity_slider.value()
        else:
            # 手动模式
            for name, (cb, slider) in self._folder_widgets.items():
                if cb.isChecked():
                    selections[name] = slider.value()
        return OverlayMaterialConfig(
            enabled=self.enabled_checkbox.isChecked(),
            selections=selections,
        )
