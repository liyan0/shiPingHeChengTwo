from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QDoubleSpinBox,
    QPushButton,
    QCheckBox,
    QGroupBox,
    QFormLayout,
)
from PyQt5.QtGui import QFont

from ..models.config import BlurredBorderConfig


class BlurredBorderSettingsDialog(QDialog):
    def __init__(self, config: BlurredBorderConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("模糊边框设置")
        self.setMinimumWidth(360)
        self._config = config
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.enabled_checkbox = QCheckBox("启用模糊视频边框")
        self.enabled_checkbox.setFont(QFont("Microsoft YaHei", 10))
        self.enabled_checkbox.setChecked(self._config.enabled)
        self.enabled_checkbox.toggled.connect(self._on_enabled_toggled)
        layout.addWidget(self.enabled_checkbox)

        self.params_group = QGroupBox("参数设置")
        params_layout = QFormLayout()
        params_layout.setSpacing(8)

        self.border_width_spin = QDoubleSpinBox()
        self.border_width_spin.setRange(1.0, 20.0)
        self.border_width_spin.setSingleStep(0.5)
        self.border_width_spin.setDecimals(1)
        self.border_width_spin.setValue(self._config.border_width)
        self.border_width_spin.setSuffix(" %")
        params_layout.addRow("边框宽度:", self.border_width_spin)

        self.blur_strength_spin = QDoubleSpinBox()
        self.blur_strength_spin.setRange(5.0, 100.0)
        self.blur_strength_spin.setSingleStep(1.0)
        self.blur_strength_spin.setDecimals(1)
        self.blur_strength_spin.setValue(self._config.blur_strength)
        params_layout.addRow("模糊强度:", self.blur_strength_spin)

        self.params_group.setLayout(params_layout)
        layout.addWidget(self.params_group)

        hint = QLabel(
            "启用后，视频四周将显示模糊的视频边框。"
            "边框视频从 真实视频素材 文件夹随机选取。"
            "主视频保持原始分辨率不变。"
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

    def _on_enabled_toggled(self, checked: bool):
        self.params_group.setEnabled(checked)

    def get_config(self) -> BlurredBorderConfig:
        return BlurredBorderConfig(
            enabled=self.enabled_checkbox.isChecked(),
            border_width=self.border_width_spin.value(),
            blur_strength=self.blur_strength_spin.value(),
        )
