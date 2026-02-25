import os
import random
from typing import List, Optional

from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QDoubleSpinBox,
    QPushButton,
    QCheckBox,
    QComboBox,
    QFrame,
    QColorDialog,
    QInputDialog,
    QMessageBox,
    QGroupBox,
    QScrollArea,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor, QPainter, QPixmap, QPen, QFontMetrics

from ..models.config import SubtitleStyleConfig, SubtitleStyleTemplate


class SubtitleSettingsDialog(QDialog):
    SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}

    def __init__(
        self,
        style: SubtitleStyleConfig,
        templates: List[SubtitleStyleTemplate],
        image_dir: str,
        parent=None
    ):
        super().__init__(parent)
        self._style = SubtitleStyleConfig(
            enabled=style.enabled,
            font_name=style.font_name,
            font_size=style.font_size,
            primary_color=style.primary_color,
            outline_color=style.outline_color,
            outline_width=style.outline_width,
            margin_v_percent=style.margin_v_percent,
            margin_l=style.margin_l,
            margin_r=style.margin_r,
        )
        self._templates = [
            SubtitleStyleTemplate(
                name=t.name,
                style=SubtitleStyleConfig(
                    enabled=t.style.enabled,
                    font_name=t.style.font_name,
                    font_size=t.style.font_size,
                    primary_color=t.style.primary_color,
                    outline_color=t.style.outline_color,
                    outline_width=t.style.outline_width,
                    margin_v_percent=t.style.margin_v_percent,
                    margin_l=t.style.margin_l,
                    margin_r=t.style.margin_r,
                )
            )
            for t in templates
        ]
        self._image_dir = image_dir
        self._background_image: Optional[QPixmap] = None

        self._setup_ui()
        self._load_background_image()
        self._update_preview()

    def _setup_ui(self):
        self.setWindowTitle("字幕设置")
        self.setMinimumWidth(500)
        self.setMinimumHeight(750)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Enable checkbox
        self._enabled_checkbox = QCheckBox("启用字幕")
        self._enabled_checkbox.setFont(QFont("Microsoft YaHei", 10))
        self._enabled_checkbox.setChecked(self._style.enabled)
        self._enabled_checkbox.stateChanged.connect(self._on_enabled_changed)
        layout.addWidget(self._enabled_checkbox)

        # Settings group
        settings_group = QGroupBox("基础设置")
        settings_group.setFont(QFont("Microsoft YaHei", 10))
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setSpacing(10)

        # Font size
        font_size_layout = QHBoxLayout()
        font_size_label = QLabel("字体大小:")
        font_size_label.setFont(QFont("Microsoft YaHei", 9))
        font_size_label.setFixedWidth(80)
        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(16, 48)
        self._font_size_spin.setValue(self._style.font_size)
        self._font_size_spin.valueChanged.connect(self._on_style_changed)
        font_size_layout.addWidget(font_size_label)
        font_size_layout.addWidget(self._font_size_spin)
        font_size_layout.addStretch()
        settings_layout.addLayout(font_size_layout)

        # Primary color
        primary_color_layout = QHBoxLayout()
        primary_color_label = QLabel("字体颜色:")
        primary_color_label.setFont(QFont("Microsoft YaHei", 9))
        primary_color_label.setFixedWidth(80)
        self._primary_color_btn = QPushButton()
        self._primary_color_btn.setFixedSize(60, 25)
        self._primary_color_btn.clicked.connect(self._on_primary_color_click)
        self._update_color_button(self._primary_color_btn, self._style.primary_color)
        primary_color_layout.addWidget(primary_color_label)
        primary_color_layout.addWidget(self._primary_color_btn)
        primary_color_layout.addStretch()
        settings_layout.addLayout(primary_color_layout)

        # Outline color
        outline_color_layout = QHBoxLayout()
        outline_color_label = QLabel("描边颜色:")
        outline_color_label.setFont(QFont("Microsoft YaHei", 9))
        outline_color_label.setFixedWidth(80)
        self._outline_color_btn = QPushButton()
        self._outline_color_btn.setFixedSize(60, 25)
        self._outline_color_btn.clicked.connect(self._on_outline_color_click)
        self._update_color_button(self._outline_color_btn, self._style.outline_color)
        outline_color_layout.addWidget(outline_color_label)
        outline_color_layout.addWidget(self._outline_color_btn)
        outline_color_layout.addStretch()
        settings_layout.addLayout(outline_color_layout)

        # Outline width
        outline_width_layout = QHBoxLayout()
        outline_width_label = QLabel("描边宽度:")
        outline_width_label.setFont(QFont("Microsoft YaHei", 9))
        outline_width_label.setFixedWidth(80)
        self._outline_width_spin = QSpinBox()
        self._outline_width_spin.setRange(0, 4)
        self._outline_width_spin.setValue(self._style.outline_width)
        self._outline_width_spin.valueChanged.connect(self._on_style_changed)
        outline_width_layout.addWidget(outline_width_label)
        outline_width_layout.addWidget(self._outline_width_spin)
        outline_width_layout.addStretch()
        settings_layout.addLayout(outline_width_layout)

        # Vertical margin
        margin_layout = QHBoxLayout()
        margin_label = QLabel("垂直位置:")
        margin_label.setFont(QFont("Microsoft YaHei", 9))
        margin_label.setFixedWidth(80)
        self._margin_spin = QDoubleSpinBox()
        self._margin_spin.setRange(0.0, 30.0)
        self._margin_spin.setValue(self._style.margin_v_percent)
        self._margin_spin.setSuffix("%")
        self._margin_spin.setDecimals(1)
        self._margin_spin.valueChanged.connect(self._on_style_changed)
        margin_hint = QLabel("(距底部)")
        margin_hint.setFont(QFont("Microsoft YaHei", 8))
        margin_hint.setStyleSheet("color: #666666;")
        margin_layout.addWidget(margin_label)
        margin_layout.addWidget(self._margin_spin)
        margin_layout.addWidget(margin_hint)
        margin_layout.addStretch()
        settings_layout.addLayout(margin_layout)

        # Left/Right margin
        lr_margin_layout = QHBoxLayout()
        lr_margin_label = QLabel("左右边距:")
        lr_margin_label.setFont(QFont("Microsoft YaHei", 9))
        lr_margin_label.setFixedWidth(80)
        self._margin_l_spin = QSpinBox()
        self._margin_l_spin.setRange(0, 200)
        self._margin_l_spin.setValue(self._style.margin_l)
        self._margin_l_spin.setPrefix("左: ")
        self._margin_l_spin.valueChanged.connect(self._on_style_changed)
        self._margin_r_spin = QSpinBox()
        self._margin_r_spin.setRange(0, 200)
        self._margin_r_spin.setValue(self._style.margin_r)
        self._margin_r_spin.setPrefix("右: ")
        self._margin_r_spin.valueChanged.connect(self._on_style_changed)
        lr_margin_layout.addWidget(lr_margin_label)
        lr_margin_layout.addWidget(self._margin_l_spin)
        lr_margin_layout.addWidget(self._margin_r_spin)
        lr_margin_layout.addStretch()
        settings_layout.addLayout(lr_margin_layout)

        layout.addWidget(settings_group)

        # Preview group
        preview_group = QGroupBox("预览")
        preview_group.setFont(QFont("Microsoft YaHei", 10))
        preview_layout = QVBoxLayout(preview_group)

        # 创建滚动区域
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(False)
        self._scroll_area.setFixedHeight(400)
        self._scroll_area.setAlignment(Qt.AlignCenter)
        self._scroll_area.setStyleSheet("background-color: #333333; border: 1px solid #d0d0d0;")

        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._scroll_area.setWidget(self._preview_label)

        preview_layout.addWidget(self._scroll_area)

        layout.addWidget(preview_group)

        # Template group
        template_group = QGroupBox("模板")
        template_group.setFont(QFont("Microsoft YaHei", 10))
        template_layout = QHBoxLayout(template_group)

        template_label = QLabel("模板:")
        template_label.setFont(QFont("Microsoft YaHei", 9))
        self._template_combo = QComboBox()
        self._template_combo.setMinimumWidth(150)
        self._update_template_combo()
        self._template_combo.currentIndexChanged.connect(self._on_template_selected)

        self._save_template_btn = QPushButton("保存")
        self._save_template_btn.clicked.connect(self._on_save_template)

        self._delete_template_btn = QPushButton("删除")
        self._delete_template_btn.clicked.connect(self._on_delete_template)

        template_layout.addWidget(template_label)
        template_layout.addWidget(self._template_combo)
        template_layout.addWidget(self._save_template_btn)
        template_layout.addWidget(self._delete_template_btn)
        template_layout.addStretch()

        layout.addWidget(template_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._ok_btn = QPushButton("确定")
        self._ok_btn.setFixedWidth(80)
        self._ok_btn.clicked.connect(self.accept)

        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.setFixedWidth(80)
        self._cancel_btn.clicked.connect(self.reject)

        button_layout.addWidget(self._ok_btn)
        button_layout.addWidget(self._cancel_btn)

        layout.addLayout(button_layout)

        self._update_controls_enabled()

    def _update_color_button(self, button: QPushButton, color: str):
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border: 1px solid #999999;
            }}
            QPushButton:hover {{
                border: 2px solid #0066cc;
            }}
        """)

    def _load_background_image(self):
        if not os.path.exists(self._image_dir):
            return

        image_files = []
        for f in os.listdir(self._image_dir):
            ext = os.path.splitext(f)[1].lower()
            if ext in self.SUPPORTED_IMAGE_EXTENSIONS:
                image_files.append(os.path.join(self._image_dir, f))

        if image_files:
            selected = random.choice(image_files)
            self._background_image = QPixmap(selected)

    def _update_preview(self):
        scroll_width = self._scroll_area.viewport().width() or 400

        # 默认缩放比例为 1.0
        scale_ratio = 1.0

        if self._background_image and not self._background_image.isNull():
            # 计算缩放比例
            original_width = self._background_image.width()
            scale_ratio = scroll_width / original_width if original_width > 0 else 1.0

            # 按宽度缩放，保持原始比例
            scaled = self._background_image.scaledToWidth(
                scroll_width,
                Qt.SmoothTransformation
            )
            preview_width = scaled.width()
            preview_height = scaled.height()
        else:
            preview_width = scroll_width
            preview_height = 400

        pixmap = QPixmap(preview_width, preview_height)
        pixmap.fill(QColor("#333333"))

        # Track image display area for subtitle positioning
        img_x, img_y, img_width, img_height = 0, 0, preview_width, preview_height

        if self._background_image and not self._background_image.isNull():
            scaled = self._background_image.scaledToWidth(
                scroll_width,
                Qt.SmoothTransformation
            )
            img_x = 0
            img_y = 0
            img_width = scaled.width()
            img_height = scaled.height()

            painter = QPainter(pixmap)
            painter.drawPixmap(img_x, img_y, scaled)
            painter.end()

        if self._style.enabled:
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.TextAntialiasing)

            # 按缩放比例调整字体大小
            scaled_font_size = max(8, int(self._style.font_size * scale_ratio))
            font = QFont("Microsoft YaHei", scaled_font_size)
            painter.setFont(font)

            sample_text = "示例字幕文本"
            metrics = QFontMetrics(font)
            text_width = metrics.horizontalAdvance(sample_text)
            text_height = metrics.height()

            margin_v = int(img_height * self._style.margin_v_percent / 100)
            x = img_x + (img_width - text_width) // 2
            y = img_y + img_height - margin_v - text_height // 4

            # 按缩放比例调整描边宽度
            scaled_outline_width = max(1, int(self._style.outline_width * scale_ratio))

            # Draw outline
            if self._style.outline_width > 0:
                outline_color = QColor(self._style.outline_color)
                pen = QPen(outline_color)
                pen.setWidth(scaled_outline_width * 2)
                painter.setPen(pen)

                for dx in range(-scaled_outline_width, scaled_outline_width + 1):
                    for dy in range(-scaled_outline_width, scaled_outline_width + 1):
                        if dx != 0 or dy != 0:
                            painter.drawText(x + dx, y + dy, sample_text)

            # Draw text
            primary_color = QColor(self._style.primary_color)
            painter.setPen(primary_color)
            painter.drawText(x, y, sample_text)

            painter.end()

        self._preview_label.setPixmap(pixmap)
        self._preview_label.setFixedSize(preview_width, preview_height)

    def _update_template_combo(self):
        self._template_combo.blockSignals(True)
        self._template_combo.clear()
        self._template_combo.addItem("-- 选择模板 --")
        for template in self._templates:
            self._template_combo.addItem(template.name)
        self._template_combo.blockSignals(False)

    def _update_controls_enabled(self):
        enabled = self._style.enabled
        self._font_size_spin.setEnabled(enabled)
        self._primary_color_btn.setEnabled(enabled)
        self._outline_color_btn.setEnabled(enabled)
        self._outline_width_spin.setEnabled(enabled)
        self._margin_spin.setEnabled(enabled)
        self._margin_l_spin.setEnabled(enabled)
        self._margin_r_spin.setEnabled(enabled)

    def _on_enabled_changed(self, state):
        self._style.enabled = state == Qt.Checked
        self._update_controls_enabled()
        self._update_preview()

    def _on_style_changed(self):
        self._style.font_size = self._font_size_spin.value()
        self._style.outline_width = self._outline_width_spin.value()
        self._style.margin_v_percent = self._margin_spin.value()
        self._style.margin_l = self._margin_l_spin.value()
        self._style.margin_r = self._margin_r_spin.value()
        self._update_preview()

    def _on_primary_color_click(self):
        color = QColorDialog.getColor(
            QColor(self._style.primary_color),
            self,
            "选择字体颜色"
        )
        if color.isValid():
            self._style.primary_color = color.name().upper()
            self._update_color_button(self._primary_color_btn, self._style.primary_color)
            self._update_preview()

    def _on_outline_color_click(self):
        color = QColorDialog.getColor(
            QColor(self._style.outline_color),
            self,
            "选择描边颜色"
        )
        if color.isValid():
            self._style.outline_color = color.name().upper()
            self._update_color_button(self._outline_color_btn, self._style.outline_color)
            self._update_preview()

    def _on_template_selected(self, index):
        if index <= 0:
            return

        template = self._templates[index - 1]
        self._style.enabled = template.style.enabled
        self._style.font_name = template.style.font_name
        self._style.font_size = template.style.font_size
        self._style.primary_color = template.style.primary_color
        self._style.outline_color = template.style.outline_color
        self._style.outline_width = template.style.outline_width
        self._style.margin_v_percent = template.style.margin_v_percent
        self._style.margin_l = template.style.margin_l
        self._style.margin_r = template.style.margin_r

        self._enabled_checkbox.setChecked(self._style.enabled)
        self._font_size_spin.setValue(self._style.font_size)
        self._outline_width_spin.setValue(self._style.outline_width)
        self._margin_spin.setValue(self._style.margin_v_percent)
        self._margin_l_spin.setValue(self._style.margin_l)
        self._margin_r_spin.setValue(self._style.margin_r)
        self._update_color_button(self._primary_color_btn, self._style.primary_color)
        self._update_color_button(self._outline_color_btn, self._style.outline_color)
        self._update_controls_enabled()
        self._update_preview()

    def _on_save_template(self):
        name, ok = QInputDialog.getText(
            self,
            "保存模板",
            "请输入模板名称:",
        )
        if not ok or not name.strip():
            return

        name = name.strip()

        # Check if template exists
        for i, template in enumerate(self._templates):
            if template.name == name:
                reply = QMessageBox.question(
                    self,
                    "确认",
                    f"模板 '{name}' 已存在，是否覆盖？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self._templates[i] = SubtitleStyleTemplate(
                        name=name,
                        style=SubtitleStyleConfig(
                            enabled=self._style.enabled,
                            font_name=self._style.font_name,
                            font_size=self._style.font_size,
                            primary_color=self._style.primary_color,
                            outline_color=self._style.outline_color,
                            outline_width=self._style.outline_width,
                            margin_v_percent=self._style.margin_v_percent,
                            margin_l=self._style.margin_l,
                            margin_r=self._style.margin_r,
                        )
                    )
                    self._update_template_combo()
                    QMessageBox.information(self, "成功", f"模板 '{name}' 已更新")
                return

        # Add new template
        self._templates.append(SubtitleStyleTemplate(
            name=name,
            style=SubtitleStyleConfig(
                enabled=self._style.enabled,
                font_name=self._style.font_name,
                font_size=self._style.font_size,
                primary_color=self._style.primary_color,
                outline_color=self._style.outline_color,
                outline_width=self._style.outline_width,
                margin_v_percent=self._style.margin_v_percent,
                margin_l=self._style.margin_l,
                margin_r=self._style.margin_r,
            )
        ))
        self._update_template_combo()
        QMessageBox.information(self, "成功", f"模板 '{name}' 已保存")

    def _on_delete_template(self):
        index = self._template_combo.currentIndex()
        if index <= 0:
            QMessageBox.warning(self, "提示", "请先选择一个模板")
            return

        template = self._templates[index - 1]
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除模板 '{template.name}' 吗？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            del self._templates[index - 1]
            self._update_template_combo()
            QMessageBox.information(self, "成功", "模板已删除")

    def get_style(self) -> SubtitleStyleConfig:
        return self._style

    def get_templates(self) -> List[SubtitleStyleTemplate]:
        return self._templates

    def showEvent(self, event):
        """窗口首次显示时重新绘制预览"""
        super().showEvent(event)
        QTimer.singleShot(0, self._update_preview)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_preview()
