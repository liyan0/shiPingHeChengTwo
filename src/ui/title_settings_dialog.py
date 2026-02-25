import os
import random
from dataclasses import fields as dataclass_fields
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
    QColorDialog,
    QInputDialog,
    QMessageBox,
    QGroupBox,
    QScrollArea,
    QTabWidget,
    QWidget,
    QFormLayout,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor, QPainter, QPixmap, QPen, QFontMetrics

from ..models.config import TitleStyleConfig, TitleStyleTemplate


class TitleSettingsDialog(QDialog):
    SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}

    FONT_PRESETS = [
        ("思源黑体", "Source Han Sans CN"),
        ("微软雅黑", "Microsoft YaHei"),
        ("黑体", "SimHei"),
        ("宋体", "SimSun"),
        ("楷体", "KaiTi"),
        ("仿宋", "FangSong"),
        ("华文细黑", "STXihei"),
        ("华文楷体", "STKaiti"),
        ("华文宋体", "STSong"),
        ("隶书", "LiSu"),
        ("幼圆", "YouYuan"),
    ]

    ALIGNMENT_OPTIONS = [
        ("底部左对齐 (1)", 1),
        ("底部居中 (2)", 2),
        ("底部右对齐 (3)", 3),
        ("中部左对齐 (4)", 4),
        ("中部居中 (5)", 5),
        ("中部右对齐 (6)", 6),
        ("顶部左对齐 (7)", 7),
        ("顶部居中 (8)", 8),
        ("顶部右对齐 (9)", 9),
    ]

    BORDER_STYLE_OPTIONS = [
        ("描边+阴影", 1),
        ("不透明背景框", 3),
    ]

    EFFECT_TYPE_OPTIONS = [
        ("无", "none"),
        ("淡入淡出", "fade"),
    ]

    def __init__(
        self,
        style: TitleStyleConfig,
        templates: List[TitleStyleTemplate],
        image_dir: str,
        parent=None,
    ):
        super().__init__(parent)
        self._style = self._copy_style(style)
        self._templates = [
            TitleStyleTemplate(name=t.name, style=self._copy_style(t.style))
            for t in templates
        ]
        self._image_dir = image_dir
        self._background_image: Optional[QPixmap] = None

        self._setup_ui()
        self._load_background_image()
        self._update_preview()

    @staticmethod
    def _copy_style(src: TitleStyleConfig) -> TitleStyleConfig:
        kwargs = {f.name: getattr(src, f.name) for f in dataclass_fields(TitleStyleConfig)}
        return TitleStyleConfig(**kwargs)

    def _setup_ui(self):
        self.setWindowTitle("标题设置")
        self.setMinimumWidth(520)
        self.setMinimumHeight(800)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self._enabled_checkbox = QCheckBox("启用标题")
        self._enabled_checkbox.setFont(QFont("Microsoft YaHei", 10))
        self._enabled_checkbox.setChecked(self._style.enabled)
        self._enabled_checkbox.stateChanged.connect(self._on_enabled_changed)
        layout.addWidget(self._enabled_checkbox)

        self._tab_widget = QTabWidget()
        self._tab_widget.setFont(QFont("Microsoft YaHei", 9))
        self._tab_widget.addTab(self._create_basic_tab(), "基础样式")
        self._tab_widget.addTab(self._create_advanced_tab(), "高级样式")
        self._tab_widget.addTab(self._create_effects_tab(), "特效")
        layout.addWidget(self._tab_widget)

        # Preview
        preview_group = QGroupBox("预览")
        preview_group.setFont(QFont("Microsoft YaHei", 10))
        preview_layout = QVBoxLayout(preview_group)

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

        # OK / Cancel
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

    def _create_basic_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(8)

        self._font_combo = QComboBox()
        for display_name, font_name in self.FONT_PRESETS:
            self._font_combo.addItem(display_name, font_name)
        current_idx = next(
            (i for i, (_, fn) in enumerate(self.FONT_PRESETS) if fn == self._style.font_name),
            0,
        )
        self._font_combo.setCurrentIndex(current_idx)
        self._font_combo.currentIndexChanged.connect(self._on_style_changed)
        form.addRow("字体:", self._font_combo)

        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(1, 999)
        self._font_size_spin.setValue(self._style.font_size)
        self._font_size_spin.valueChanged.connect(self._on_style_changed)
        form.addRow("字体大小:", self._font_size_spin)

        self._primary_color_btn = QPushButton()
        self._primary_color_btn.setFixedSize(60, 25)
        self._primary_color_btn.clicked.connect(self._on_primary_color_click)
        self._update_color_button(self._primary_color_btn, self._style.primary_color)
        form.addRow("文字颜色:", self._primary_color_btn)

        self._outline_color_btn = QPushButton()
        self._outline_color_btn.setFixedSize(60, 25)
        self._outline_color_btn.clicked.connect(self._on_outline_color_click)
        self._update_color_button(self._outline_color_btn, self._style.outline_color)
        form.addRow("描边颜色:", self._outline_color_btn)

        self._outline_width_spin = QSpinBox()
        self._outline_width_spin.setRange(0, 10)
        self._outline_width_spin.setValue(self._style.outline_width)
        self._outline_width_spin.valueChanged.connect(self._on_style_changed)
        form.addRow("描边宽度:", self._outline_width_spin)

        self._margin_spin = QDoubleSpinBox()
        self._margin_spin.setRange(0.0, 50.0)
        self._margin_spin.setValue(self._style.margin_v_percent)
        self._margin_spin.setSuffix("% (距顶部)")
        self._margin_spin.setDecimals(1)
        self._margin_spin.valueChanged.connect(self._on_style_changed)
        form.addRow("垂直位置:", self._margin_spin)

        return tab

    def _create_advanced_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(8)

        format_layout = QHBoxLayout()
        self._bold_checkbox = QCheckBox("粗体")
        self._bold_checkbox.setChecked(self._style.bold)
        self._bold_checkbox.stateChanged.connect(self._on_style_changed)
        self._italic_checkbox = QCheckBox("斜体")
        self._italic_checkbox.setChecked(self._style.italic)
        self._italic_checkbox.stateChanged.connect(self._on_style_changed)
        format_layout.addWidget(self._bold_checkbox)
        format_layout.addWidget(self._italic_checkbox)
        format_layout.addStretch()
        form.addRow("文本格式:", format_layout)

        self._shadow_spin = QSpinBox()
        self._shadow_spin.setRange(0, 10)
        self._shadow_spin.setValue(self._style.shadow_depth)
        self._shadow_spin.valueChanged.connect(self._on_style_changed)
        form.addRow("阴影深度:", self._shadow_spin)

        self._border_style_combo = QComboBox()
        for display, val in self.BORDER_STYLE_OPTIONS:
            self._border_style_combo.addItem(display, val)
        current_bs = next(
            (i for i, (_, v) in enumerate(self.BORDER_STYLE_OPTIONS) if v == self._style.border_style),
            0,
        )
        self._border_style_combo.setCurrentIndex(current_bs)
        self._border_style_combo.currentIndexChanged.connect(self._on_style_changed)
        form.addRow("边框样式:", self._border_style_combo)

        back_layout = QHBoxLayout()
        self._back_color_btn = QPushButton()
        self._back_color_btn.setFixedSize(60, 25)
        self._back_color_btn.clicked.connect(self._on_back_color_click)
        self._update_color_button(self._back_color_btn, self._style.back_color)
        self._back_alpha_spin = QSpinBox()
        self._back_alpha_spin.setRange(0, 255)
        self._back_alpha_spin.setValue(self._style.back_color_alpha)
        self._back_alpha_spin.setPrefix("透明度: ")
        self._back_alpha_spin.valueChanged.connect(self._on_style_changed)
        back_layout.addWidget(self._back_color_btn)
        back_layout.addWidget(self._back_alpha_spin)
        back_layout.addStretch()
        form.addRow("背景颜色:", back_layout)

        self._spacing_spin = QDoubleSpinBox()
        self._spacing_spin.setRange(-5.0, 20.0)
        self._spacing_spin.setValue(self._style.letter_spacing)
        self._spacing_spin.setDecimals(1)
        self._spacing_spin.setSuffix(" px")
        self._spacing_spin.valueChanged.connect(self._on_style_changed)
        form.addRow("字间距:", self._spacing_spin)

        self._alignment_combo = QComboBox()
        for display, val in self.ALIGNMENT_OPTIONS:
            self._alignment_combo.addItem(display, val)
        current_align = next(
            (i for i, (_, v) in enumerate(self.ALIGNMENT_OPTIONS) if v == self._style.alignment),
            7,
        )
        self._alignment_combo.setCurrentIndex(current_align)
        self._alignment_combo.currentIndexChanged.connect(self._on_style_changed)
        form.addRow("对齐方式:", self._alignment_combo)

        margin_lr_layout = QHBoxLayout()
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
        margin_lr_layout.addWidget(self._margin_l_spin)
        margin_lr_layout.addWidget(self._margin_r_spin)
        margin_lr_layout.addStretch()
        form.addRow("左右边距:", margin_lr_layout)

        scale_layout = QHBoxLayout()
        self._scale_x_spin = QSpinBox()
        self._scale_x_spin.setRange(50, 200)
        self._scale_x_spin.setValue(self._style.scale_x)
        self._scale_x_spin.setSuffix("%")
        self._scale_x_spin.setPrefix("水平: ")
        self._scale_x_spin.valueChanged.connect(self._on_style_changed)
        self._scale_y_spin = QSpinBox()
        self._scale_y_spin.setRange(50, 200)
        self._scale_y_spin.setValue(self._style.scale_y)
        self._scale_y_spin.setSuffix("%")
        self._scale_y_spin.setPrefix("垂直: ")
        self._scale_y_spin.valueChanged.connect(self._on_style_changed)
        scale_layout.addWidget(self._scale_x_spin)
        scale_layout.addWidget(self._scale_y_spin)
        scale_layout.addStretch()
        form.addRow("缩放:", scale_layout)

        self._max_width_spin = QDoubleSpinBox()
        self._max_width_spin.setRange(50.0, 100.0)
        self._max_width_spin.setSingleStep(5.0)
        self._max_width_spin.setDecimals(1)
        self._max_width_spin.setSuffix("%")
        self._max_width_spin.setValue(self._style.max_width_percent)
        self._max_width_spin.valueChanged.connect(self._on_style_changed)
        form.addRow("最大宽度:", self._max_width_spin)

        self._line_spacing_spin = QSpinBox()
        self._line_spacing_spin.setRange(-20, 100)
        self._line_spacing_spin.setSingleStep(1)
        self._line_spacing_spin.setSuffix(" px")
        self._line_spacing_spin.setValue(self._style.line_spacing)
        self._line_spacing_spin.valueChanged.connect(self._on_style_changed)
        form.addRow("行间距:", self._line_spacing_spin)

        return tab

    def _create_effects_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)
        form.setSpacing(8)

        self._effect_combo = QComboBox()
        for display, val in self.EFFECT_TYPE_OPTIONS:
            self._effect_combo.addItem(display, val)
        current_eff = next(
            (i for i, (_, v) in enumerate(self.EFFECT_TYPE_OPTIONS) if v == self._style.effect_type),
            0,
        )
        self._effect_combo.setCurrentIndex(current_eff)
        self._effect_combo.currentIndexChanged.connect(self._on_effect_type_changed)
        form.addRow("特效类型:", self._effect_combo)

        self._fade_group = QGroupBox("淡入淡出设置")
        fade_form = QFormLayout(self._fade_group)
        self._fade_in_spin = QSpinBox()
        self._fade_in_spin.setRange(0, 5000)
        self._fade_in_spin.setValue(self._style.fade_in_ms)
        self._fade_in_spin.setSuffix(" ms")
        self._fade_in_spin.valueChanged.connect(self._on_style_changed)
        fade_form.addRow("淡入时长:", self._fade_in_spin)
        self._fade_out_spin = QSpinBox()
        self._fade_out_spin.setRange(0, 5000)
        self._fade_out_spin.setValue(self._style.fade_out_ms)
        self._fade_out_spin.setSuffix(" ms")
        self._fade_out_spin.valueChanged.connect(self._on_style_changed)
        fade_form.addRow("淡出时长:", self._fade_out_spin)
        form.addRow(self._fade_group)

        hint = QLabel("(特效仅在最终视频中可见)")
        hint.setFont(QFont("Microsoft YaHei", 8))
        hint.setStyleSheet("color: #888888;")
        form.addRow(hint)

        self._update_effect_visibility()
        return tab

    def _update_effect_visibility(self):
        effect = self._effect_combo.currentData()
        self._fade_group.setVisible(effect == "fade")

    def _on_effect_type_changed(self):
        self._update_effect_visibility()
        self._on_style_changed()

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
            self._background_image = QPixmap(random.choice(image_files))

    def _update_preview(self):
        scroll_width = self._scroll_area.viewport().width() or 400
        scale_ratio = 1.0

        if self._background_image and not self._background_image.isNull():
            original_width = self._background_image.width()
            scale_ratio = scroll_width / original_width if original_width > 0 else 1.0
            scaled = self._background_image.scaledToWidth(scroll_width, Qt.SmoothTransformation)
            preview_width = scaled.width()
            preview_height = scaled.height()
        else:
            preview_width = scroll_width
            preview_height = 400

        pixmap = QPixmap(preview_width, preview_height)
        pixmap.fill(QColor("#333333"))

        img_x, img_y, img_width, img_height = 0, 0, preview_width, preview_height

        if self._background_image and not self._background_image.isNull():
            scaled = self._background_image.scaledToWidth(scroll_width, Qt.SmoothTransformation)
            img_width = scaled.width()
            img_height = scaled.height()
            painter = QPainter(pixmap)
            painter.drawPixmap(0, 0, scaled)
            painter.end()

        if self._style.enabled:
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.TextAntialiasing)

            scaled_font_size = max(8, int(self._style.font_size * scale_ratio))
            font = QFont(self._style.font_name, scaled_font_size)
            font.setBold(self._style.bold)
            font.setItalic(self._style.italic)
            if self._style.letter_spacing != 0:
                font.setLetterSpacing(QFont.AbsoluteSpacing, self._style.letter_spacing * scale_ratio)
            painter.setFont(font)

            sample_text = "示例标题文本"
            metrics = QFontMetrics(font)

            # Simulate wrapping based on max_width_percent
            available_px = img_width * self._style.max_width_percent / 100
            full_sample = "示例标题文本这是一段较长的标题用于测试换行效果"
            wrapped_lines = []
            current = ""
            for ch in full_sample:
                test = current + ch
                if metrics.horizontalAdvance(test) > available_px and current:
                    wrapped_lines.append(current)
                    current = ch
                else:
                    current = test
            if current:
                wrapped_lines.append(current)
            if not wrapped_lines:
                wrapped_lines = [sample_text]
            sample_text = "\n".join(wrapped_lines)

            line_h = metrics.height() + int(self._style.line_spacing * scale_ratio)
            text_width = max(metrics.horizontalAdvance(l) for l in wrapped_lines)
            text_height = line_h * len(wrapped_lines)

            margin_v = int(img_height * self._style.margin_v_percent / 100)

            align = self._style.alignment
            if align in (1, 4, 7):
                x = img_x + int(self._style.margin_l * scale_ratio)
            elif align in (3, 6, 9):
                x = img_x + img_width - text_width - int(self._style.margin_r * scale_ratio)
            else:
                x = img_x + (img_width - text_width) // 2
            if align in (7, 8, 9):
                y = img_y + margin_v + text_height
            elif align in (4, 5, 6):
                y = img_y + img_height // 2 + text_height // 4
            else:
                y = img_y + img_height - margin_v - text_height // 4

            scaled_outline_width = max(1, int(self._style.outline_width * scale_ratio))

            if self._style.border_style == 3:
                box_alpha = max(0, 255 - self._style.back_color_alpha)
                box_color = QColor(self._style.back_color)
                box_color.setAlpha(box_alpha)
                pad = int(4 * scale_ratio)
                painter.fillRect(
                    x - pad,
                    y - text_height + pad,
                    text_width + pad * 2,
                    text_height + pad,
                    box_color,
                )

            if self._style.shadow_depth > 0:
                shadow_offset = int(self._style.shadow_depth * scale_ratio)
                shadow_color = QColor(self._style.back_color)
                shadow_color.setAlpha(128)
                painter.setPen(shadow_color)
                for li, line in enumerate(wrapped_lines):
                    painter.drawText(x + shadow_offset, y + li * line_h + shadow_offset, line)

            if self._style.outline_width > 0:
                outline_color = QColor(self._style.outline_color)
                pen = QPen(outline_color)
                pen.setWidth(scaled_outline_width * 2)
                painter.setPen(pen)
                for dx in range(-scaled_outline_width, scaled_outline_width + 1):
                    for dy in range(-scaled_outline_width, scaled_outline_width + 1):
                        if dx != 0 or dy != 0:
                            for li, line in enumerate(wrapped_lines):
                                painter.drawText(x + dx, y + li * line_h + dy, line)

            painter.setPen(QColor(self._style.primary_color))
            for li, line in enumerate(wrapped_lines):
                painter.drawText(x, y + li * line_h, line)
            painter.end()

        self._preview_label.setPixmap(pixmap)
        self._preview_label.setFixedSize(preview_width, preview_height)

    def _update_controls_enabled(self):
        enabled = self._style.enabled
        self._tab_widget.setEnabled(enabled)

    def _on_enabled_changed(self, state):
        self._style.enabled = state == Qt.Checked
        self._update_controls_enabled()
        self._update_preview()

    def _on_style_changed(self):
        self._style.font_name = self._font_combo.currentData()
        self._style.font_size = self._font_size_spin.value()
        self._style.outline_width = self._outline_width_spin.value()
        self._style.margin_v_percent = self._margin_spin.value()
        self._style.bold = self._bold_checkbox.isChecked()
        self._style.italic = self._italic_checkbox.isChecked()
        self._style.shadow_depth = self._shadow_spin.value()
        self._style.border_style = self._border_style_combo.currentData()
        self._style.back_color_alpha = self._back_alpha_spin.value()
        self._style.letter_spacing = self._spacing_spin.value()
        self._style.alignment = self._alignment_combo.currentData()
        self._style.margin_l = self._margin_l_spin.value()
        self._style.margin_r = self._margin_r_spin.value()
        self._style.scale_x = self._scale_x_spin.value()
        self._style.scale_y = self._scale_y_spin.value()
        self._style.max_width_percent = self._max_width_spin.value()
        self._style.line_spacing = self._line_spacing_spin.value()
        self._style.effect_type = self._effect_combo.currentData()
        self._style.fade_in_ms = self._fade_in_spin.value()
        self._style.fade_out_ms = self._fade_out_spin.value()
        self._update_preview()

    def _on_primary_color_click(self):
        color = QColorDialog.getColor(QColor(self._style.primary_color), self, "选择文字颜色")
        if color.isValid():
            self._style.primary_color = color.name().upper()
            self._update_color_button(self._primary_color_btn, self._style.primary_color)
            self._update_preview()

    def _on_outline_color_click(self):
        color = QColorDialog.getColor(QColor(self._style.outline_color), self, "选择描边颜色")
        if color.isValid():
            self._style.outline_color = color.name().upper()
            self._update_color_button(self._outline_color_btn, self._style.outline_color)
            self._update_preview()

    def _on_back_color_click(self):
        color = QColorDialog.getColor(QColor(self._style.back_color), self, "选择背景颜色")
        if color.isValid():
            self._style.back_color = color.name().upper()
            self._update_color_button(self._back_color_btn, self._style.back_color)
            self._update_preview()

    def _update_template_combo(self):
        self._template_combo.blockSignals(True)
        self._template_combo.clear()
        self._template_combo.addItem("-- 选择模板 --")
        for template in self._templates:
            self._template_combo.addItem(template.name)
        self._template_combo.blockSignals(False)

    def _apply_style_to_ui(self, style: TitleStyleConfig):
        self._enabled_checkbox.setChecked(style.enabled)

        font_idx = next(
            (i for i, (_, fn) in enumerate(self.FONT_PRESETS) if fn == style.font_name),
            0,
        )
        self._font_combo.setCurrentIndex(font_idx)
        self._font_size_spin.setValue(style.font_size)
        self._update_color_button(self._primary_color_btn, style.primary_color)
        self._update_color_button(self._outline_color_btn, style.outline_color)
        self._outline_width_spin.setValue(style.outline_width)
        self._margin_spin.setValue(style.margin_v_percent)

        self._bold_checkbox.setChecked(style.bold)
        self._italic_checkbox.setChecked(style.italic)
        self._shadow_spin.setValue(style.shadow_depth)
        bs_idx = next(
            (i for i, (_, v) in enumerate(self.BORDER_STYLE_OPTIONS) if v == style.border_style),
            0,
        )
        self._border_style_combo.setCurrentIndex(bs_idx)
        self._update_color_button(self._back_color_btn, style.back_color)
        self._back_alpha_spin.setValue(style.back_color_alpha)
        self._spacing_spin.setValue(style.letter_spacing)
        align_idx = next(
            (i for i, (_, v) in enumerate(self.ALIGNMENT_OPTIONS) if v == style.alignment),
            7,
        )
        self._alignment_combo.setCurrentIndex(align_idx)
        self._margin_l_spin.setValue(style.margin_l)
        self._margin_r_spin.setValue(style.margin_r)
        self._scale_x_spin.setValue(style.scale_x)
        self._scale_y_spin.setValue(style.scale_y)
        self._max_width_spin.setValue(style.max_width_percent)
        self._line_spacing_spin.setValue(style.line_spacing)

        eff_idx = next(
            (i for i, (_, v) in enumerate(self.EFFECT_TYPE_OPTIONS) if v == style.effect_type),
            0,
        )
        self._effect_combo.setCurrentIndex(eff_idx)
        self._fade_in_spin.setValue(style.fade_in_ms)
        self._fade_out_spin.setValue(style.fade_out_ms)

        self._update_effect_visibility()
        self._update_controls_enabled()
        self._update_preview()

    def _on_template_selected(self, index):
        if index <= 0:
            return
        template = self._templates[index - 1]
        self._style = self._copy_style(template.style)
        self._apply_style_to_ui(self._style)

    def _on_save_template(self):
        name, ok = QInputDialog.getText(self, "保存模板", "请输入模板名称:")
        if not ok or not name.strip():
            return
        name = name.strip()

        for i, template in enumerate(self._templates):
            if template.name == name:
                reply = QMessageBox.question(
                    self, "确认", f"模板 '{name}' 已存在，是否覆盖？",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply == QMessageBox.Yes:
                    self._templates[i] = TitleStyleTemplate(
                        name=name, style=self._copy_style(self._style)
                    )
                    self._update_template_combo()
                    QMessageBox.information(self, "成功", f"模板 '{name}' 已更新")
                return

        self._templates.append(
            TitleStyleTemplate(name=name, style=self._copy_style(self._style))
        )
        self._update_template_combo()
        QMessageBox.information(self, "成功", f"模板 '{name}' 已保存")

    def _on_delete_template(self):
        index = self._template_combo.currentIndex()
        if index <= 0:
            QMessageBox.warning(self, "提示", "请先选择一个模板")
            return
        template = self._templates[index - 1]
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除模板 '{template.name}' 吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            del self._templates[index - 1]
            self._update_template_combo()
            QMessageBox.information(self, "成功", "模板已删除")

    def get_style(self) -> TitleStyleConfig:
        return self._style

    def get_templates(self) -> List[TitleStyleTemplate]:
        return self._templates

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._update_preview)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_preview()
