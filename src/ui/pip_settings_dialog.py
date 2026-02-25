from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QDoubleSpinBox,
    QSpinBox,
    QPushButton,
    QCheckBox,
    QGroupBox,
    QFormLayout,
    QLineEdit,
)
from PyQt5.QtGui import QFont

from ..models.config import PipConfig


class PipSettingsDialog(QDialog):
    def __init__(self, config: PipConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("画中画设置")
        self.setMinimumWidth(360)
        self._config = config
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.enabled_checkbox = QCheckBox("启用画中画")
        self.enabled_checkbox.setFont(QFont("Microsoft YaHei", 10))
        self.enabled_checkbox.setChecked(self._config.enabled)
        self.enabled_checkbox.toggled.connect(self._on_enabled_toggled)
        layout.addWidget(self.enabled_checkbox)

        self.params_group = QGroupBox("参数设置")
        params_layout = QFormLayout()
        params_layout.setSpacing(8)

        self.size_spin = QDoubleSpinBox()
        self.size_spin.setRange(10.0, 60.0)
        self.size_spin.setSingleStep(1.0)
        self.size_spin.setDecimals(1)
        self.size_spin.setValue(self._config.size_percent)
        self.size_spin.setSuffix(" %")
        params_layout.addRow("圆形大小:", self.size_spin)

        self.h_spin = QDoubleSpinBox()
        self.h_spin.setRange(0.0, 100.0)
        self.h_spin.setSingleStep(1.0)
        self.h_spin.setDecimals(1)
        self.h_spin.setValue(self._config.h_percent)
        self.h_spin.setSuffix(" %")
        params_layout.addRow("水平位置:", self.h_spin)

        self.v_spin = QDoubleSpinBox()
        self.v_spin.setRange(0.0, 100.0)
        self.v_spin.setSingleStep(1.0)
        self.v_spin.setDecimals(1)
        self.v_spin.setValue(self._config.v_percent)
        self.v_spin.setSuffix(" %")
        params_layout.addRow("垂直位置:", self.v_spin)

        self.border_width_spin = QSpinBox()
        self.border_width_spin.setRange(0, 10)
        self.border_width_spin.setValue(self._config.border_width)
        self.border_width_spin.setSuffix(" px")
        params_layout.addRow("边框粗细:", self.border_width_spin)

        self.border_color_edit = QLineEdit(self._config.border_color)
        self.border_color_edit.setMaximumWidth(100)
        params_layout.addRow("边框颜色:", self.border_color_edit)

        self.params_group.setLayout(params_layout)
        layout.addWidget(self.params_group)

        hint = QLabel(
            "启用后，视频将显示圆形画中画窗口。"
            "画中画视频从 真实视频素材 文件夹随机选取（不与主视频重复）。"
            "大小为圆形直径占视频短边的百分比。"
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

    def get_config(self) -> PipConfig:
        return PipConfig(
            enabled=self.enabled_checkbox.isChecked(),
            size_percent=self.size_spin.value(),
            h_percent=self.h_spin.value(),
            v_percent=self.v_spin.value(),
            border_width=self.border_width_spin.value(),
            border_color=self.border_color_edit.text().strip(),
        )
