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

from ..models.config import WaterReflectionConfig


class WaterReflectionSettingsDialog(QDialog):
    def __init__(self, config: WaterReflectionConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("水面倒影特效设置")
        self.setMinimumWidth(360)
        self._config = config
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.enabled_checkbox = QCheckBox("启用水面倒影特效")
        self.enabled_checkbox.setFont(QFont("Microsoft YaHei", 10))
        self.enabled_checkbox.setChecked(self._config.enabled)
        self.enabled_checkbox.toggled.connect(self._on_enabled_toggled)
        layout.addWidget(self.enabled_checkbox)

        self.params_group = QGroupBox("参数设置")
        params_layout = QFormLayout()
        params_layout.setSpacing(8)

        self.reflection_ratio_spin = QDoubleSpinBox()
        self.reflection_ratio_spin.setRange(0.20, 0.50)
        self.reflection_ratio_spin.setSingleStep(0.05)
        self.reflection_ratio_spin.setDecimals(2)
        self.reflection_ratio_spin.setValue(self._config.reflection_ratio)
        params_layout.addRow("倒影比例:", self.reflection_ratio_spin)

        self.amplitude_spin = QDoubleSpinBox()
        self.amplitude_spin.setRange(0.0, 1.0)
        self.amplitude_spin.setSingleStep(0.05)
        self.amplitude_spin.setDecimals(2)
        self.amplitude_spin.setValue(self._config.amplitude)
        params_layout.addRow("波纹振幅:", self.amplitude_spin)

        self.frequency_spin = QDoubleSpinBox()
        self.frequency_spin.setRange(0.0, 1.0)
        self.frequency_spin.setSingleStep(0.05)
        self.frequency_spin.setDecimals(2)
        self.frequency_spin.setValue(self._config.frequency)
        params_layout.addRow("波纹频率:", self.frequency_spin)

        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.0, 1.0)
        self.speed_spin.setSingleStep(0.05)
        self.speed_spin.setDecimals(2)
        self.speed_spin.setValue(self._config.speed)
        params_layout.addRow("波纹速度:", self.speed_spin)

        self.opacity_spin = QDoubleSpinBox()
        self.opacity_spin.setRange(0.1, 1.0)
        self.opacity_spin.setSingleStep(0.05)
        self.opacity_spin.setDecimals(2)
        self.opacity_spin.setValue(self._config.opacity)
        params_layout.addRow("不透明度:", self.opacity_spin)

        self.tint_strength_spin = QDoubleSpinBox()
        self.tint_strength_spin.setRange(0.0, 1.0)
        self.tint_strength_spin.setSingleStep(0.05)
        self.tint_strength_spin.setDecimals(2)
        self.tint_strength_spin.setValue(self._config.tint_strength)
        params_layout.addRow("色调强度:", self.tint_strength_spin)

        self.params_group.setLayout(params_layout)
        layout.addWidget(self.params_group)

        hint = QLabel("倒影叠加在画面底部，字幕不受影响。比例越大倒影区域越高。")
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

    def get_config(self) -> WaterReflectionConfig:
        return WaterReflectionConfig(
            enabled=self.enabled_checkbox.isChecked(),
            reflection_ratio=self.reflection_ratio_spin.value(),
            amplitude=self.amplitude_spin.value(),
            frequency=self.frequency_spin.value(),
            speed=self.speed_spin.value(),
            opacity=self.opacity_spin.value(),
            tint_strength=self.tint_strength_spin.value(),
        )
