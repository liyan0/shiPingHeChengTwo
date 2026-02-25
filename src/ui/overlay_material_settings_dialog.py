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

        self.params_group = QGroupBox("素材选择")
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
            "叠加素材使用滤色(Screen)混合模式，黑色背景自动去除。"
            "每个子文件夹随机选取一个视频，循环播放至主视频结束。"
            "不透明度控制叠加强度。"
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
        self.params_group.setEnabled(checked)

    def get_config(self) -> OverlayMaterialConfig:
        selections = {}
        for name, (cb, slider) in self._folder_widgets.items():
            if cb.isChecked():
                selections[name] = slider.value()
        return OverlayMaterialConfig(
            enabled=self.enabled_checkbox.isChecked(),
            selections=selections,
        )
