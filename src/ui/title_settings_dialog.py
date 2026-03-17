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
    QTabWidget,
    QWidget,
    QFormLayout,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor, QPainter, QPixmap, QFontMetrics, QFontDatabase

from ..models.config import TitleStyleConfig, TitleStyleTemplate
from ..core.subtitle_effects import normalize_font_name


class TitleSettingsDialog(QDialog):
    SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}

    FONT_PRESETS = [
        # 黑体类
        ("思源黑体", "Source Han Sans CN"),
        ("微软雅黑", "Microsoft YaHei"),
        ("黑体", "SimHei"),
        ("华文细黑", "STXihei"),
        ("华文中宋", "STZhongsong"),
        ("方正黑体", "FZHei-B01"),
        ("方正兰亭黑", "FZLanTingHei-R-GBK"),
        # 宋体类
        ("宋体", "SimSun"),
        ("新宋体", "NSimSun"),
        ("华文宋体", "STSong"),
        ("方正书宋", "FZShuSong-Z01"),
        ("方正小标宋", "FZXiaoBiaoSong-B05"),
        # 楷体类
        ("楷体", "KaiTi"),
        ("华文楷体", "STKaiti"),
        ("华文行楷", "STXingkai"),
        ("方正楷体", "FZKai-Z03"),
        # 仿宋类
        ("仿宋", "FangSong"),
        ("华文仿宋", "STFangsong"),
        ("方正仿宋", "FZFangSong-Z02"),
        # 艺术字体
        ("隶书", "LiSu"),
        ("华文隶书", "STLiti"),
        ("幼圆", "YouYuan"),
        ("华文彩云", "STCaiyun"),
        ("华文琥珀", "STHupo"),
        ("华文新魏", "STXinwei"),
        ("方正舒体", "FZShuTi"),
        ("方正姚体", "FZYaoti"),
        # 手写风格
        ("方正静蕾简体", "FZJingLeiS"),
        ("汉仪雪君体", "HYXueJunW"),
        # 圆体
        ("方正兰亭圆", "FZLanTingYuan"),
        ("苹方", "PingFang SC"),
        # 其他常用
        ("Arial", "Arial"),
        ("Times New Roman", "Times New Roman"),
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
        ("无特效", "none"),
        ("淡入淡出", "fade"),
    ]

    COVER_DURATION_OPTIONS = [
        ("1秒", 1.0),
        ("2秒", 2.0),
        ("3秒", 3.0),
        ("5秒", 5.0),
    ]

    PREVIEW_RATIO_OPTIONS = [
        ("横屏 16:9", "landscape"),
        ("竖屏 9:16", "portrait"),
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
        self._preview_ratio = "landscape"  # 默认横屏
        self._font_presets = self._build_available_font_presets()

        self._setup_ui()
        self._load_background_image()
        self._update_preview()

    @staticmethod
    def _copy_style(src: TitleStyleConfig) -> TitleStyleConfig:
        kwargs = {f.name: getattr(src, f.name) for f in dataclass_fields(TitleStyleConfig)}
        return TitleStyleConfig(**kwargs)

    def _build_available_font_presets(self) -> List[tuple]:
        families = set(QFontDatabase().families())
        fallback_map = {
            "STXingkai": "KaiTi",
            "STKaiti": "KaiTi",
            "STSong": "SimSun",
            "STFangsong": "FangSong",
            "STXihei": "SimHei",
            "Source Han Sans CN": "Microsoft YaHei",
        }
        presets = []
        for display_name, font_name in self.FONT_PRESETS:
            if font_name in families or display_name in families:
                presets.append((display_name, font_name))
                continue
            fallback = fallback_map.get(font_name)
            if fallback and (fallback in families):
                presets.append((display_name, fallback))
        if not presets:
            presets = [("微软雅黑", "Microsoft YaHei")]
        return presets

    def _setup_ui(self):
        self.setWindowTitle("标题设置")
        self.setMinimumWidth(550)
        self.setMinimumHeight(580)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

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
        self._tab_widget.setFixedHeight(300)
        layout.addWidget(self._tab_widget)

        # Preview
        preview_group = QGroupBox("预览")
        preview_group.setFont(QFont("Microsoft YaHei", 10))
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(5, 5, 5, 5)

        # 预览比例选择
        ratio_layout = QHBoxLayout()
        ratio_label = QLabel("预览比例:")
        self._ratio_combo = QComboBox()
        for display, val in self.PREVIEW_RATIO_OPTIONS:
            self._ratio_combo.addItem(display, val)
        self._ratio_combo.currentIndexChanged.connect(self._on_ratio_changed)
        ratio_layout.addWidget(ratio_label)
        ratio_layout.addWidget(self._ratio_combo)
        ratio_layout.addStretch()
        preview_layout.addLayout(ratio_layout)

        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._preview_label.setMinimumHeight(180)
        self._preview_label.setStyleSheet("background-color: #333333;")
        preview_layout.addWidget(self._preview_label)
        layout.addWidget(preview_group, 1)

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
        for display_name, font_name in self._font_presets:
            self._font_combo.addItem(display_name, font_name)
        current_idx = next(
            (i for i, (_, fn) in enumerate(self._font_presets) if fn == self._style.font_name),
            0,
        )
        self._font_combo.setCurrentIndex(current_idx)
        self._style.font_name = self._font_combo.currentData()
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
        form.setSpacing(6)
        form.setContentsMargins(8, 8, 8, 8)

        # 封面模式
        self._cover_mode_checkbox = QCheckBox("启用封面模式 (冻结第一帧0.04秒+标题，裁剪成1:1)")
        self._cover_mode_checkbox.setChecked(getattr(self._style, 'cover_mode', False))
        self._cover_mode_checkbox.stateChanged.connect(self._on_cover_mode_changed)
        form.addRow(self._cover_mode_checkbox)

        # 标题显示时长 - 下拉选择
        duration_layout = QHBoxLayout()
        self._display_duration_combo = QComboBox()
        self._display_duration_combo.addItem("全程显示", 0.0)
        self._display_duration_combo.addItem("0.1秒", 0.1)
        self._display_duration_combo.addItem("0.5秒", 0.5)
        self._display_duration_combo.addItem("1秒", 1.0)
        self._display_duration_combo.addItem("2秒", 2.0)
        self._display_duration_combo.addItem("3秒", 3.0)
        self._display_duration_combo.addItem("5秒", 5.0)
        current_disp = self._style.display_duration
        disp_idx = next((i for i, v in enumerate([0.0, 0.1, 0.5, 1.0, 2.0, 3.0, 5.0]) if v == current_disp), 0)
        self._display_duration_combo.setCurrentIndex(disp_idx)
        self._display_duration_combo.currentIndexChanged.connect(self._on_style_changed)
        duration_layout.addWidget(self._display_duration_combo)
        duration_layout.addStretch()
        form.addRow("标题显示时长:", duration_layout)

        # 动画特效
        effect_layout = QHBoxLayout()
        self._effect_combo = QComboBox()
        for display, val in self.EFFECT_TYPE_OPTIONS:
            self._effect_combo.addItem(display, val)
        current_eff = next(
            (i for i, (_, v) in enumerate(self.EFFECT_TYPE_OPTIONS) if v == self._style.effect_type),
            0,
        )
        self._effect_combo.setCurrentIndex(current_eff)
        self._effect_combo.currentIndexChanged.connect(self._on_effect_type_changed)
        effect_layout.addWidget(self._effect_combo)
        effect_layout.addStretch()
        form.addRow("动画特效:", effect_layout)

        # 淡入淡出参数
        fade_layout = QHBoxLayout()
        self._fade_in_combo = QComboBox()
        self._fade_in_combo.addItem("淡入:500ms", 500)
        self._fade_in_combo.addItem("淡入:300ms", 300)
        self._fade_in_combo.addItem("淡入:1000ms", 1000)
        fade_in_idx = 0 if self._style.fade_in_ms == 500 else (1 if self._style.fade_in_ms == 300 else 2)
        self._fade_in_combo.setCurrentIndex(fade_in_idx)
        self._fade_in_combo.currentIndexChanged.connect(self._on_style_changed)

        self._fade_out_combo = QComboBox()
        self._fade_out_combo.addItem("淡出:300ms", 300)
        self._fade_out_combo.addItem("淡出:500ms", 500)
        self._fade_out_combo.addItem("淡出:1000ms", 1000)
        fade_out_idx = 0 if self._style.fade_out_ms == 300 else (1 if self._style.fade_out_ms == 500 else 2)
        self._fade_out_combo.setCurrentIndex(fade_out_idx)
        self._fade_out_combo.currentIndexChanged.connect(self._on_style_changed)

        fade_layout.addWidget(self._fade_in_combo)
        fade_layout.addWidget(self._fade_out_combo)
        fade_layout.addStretch()
        self._fade_widget = QWidget()
        self._fade_widget.setLayout(fade_layout)
        form.addRow("淡入淡出:", self._fade_widget)

        self._update_effect_visibility()
        self._update_cover_mode_visibility()
        return tab

    def _update_effect_visibility(self):
        effect = self._effect_combo.currentData()
        self._fade_widget.setVisible(effect == "fade")

    def _update_cover_mode_visibility(self):
        cover_mode = self._cover_mode_checkbox.isChecked()
        self._display_duration_combo.setEnabled(not cover_mode)

    def _on_ratio_changed(self):
        self._preview_ratio = self._ratio_combo.currentData()
        self._update_preview()

    def _on_cover_mode_changed(self):
        self._update_cover_mode_visibility()
        self._on_style_changed()

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
        # 根据横屏/竖屏选择计算预览尺寸
        container_width = self._preview_label.parent().width() - 20 if self._preview_label.parent() else 500
        container_width = max(300, container_width)
        max_preview_height = 220

        if self._preview_ratio == "landscape":
            # 横屏 16:9
            preview_width = container_width
            preview_height = int(container_width * 9 / 16)
            if preview_height > max_preview_height:
                preview_height = max_preview_height
                preview_width = int(preview_height * 16 / 9)
            sim_width, sim_height = 1920, 1080
        else:
            # 竖屏 9:16
            preview_height = min(280, max_preview_height)
            preview_width = int(preview_height * 9 / 16)
            sim_width, sim_height = 1080, 1920

        scale_ratio = preview_width / sim_width

        pixmap = QPixmap(preview_width, preview_height)
        pixmap.fill(QColor("#333333"))

        if self._background_image and not self._background_image.isNull():
            scaled = self._background_image.scaled(
                preview_width, preview_height,
                Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            x_offset = (scaled.width() - preview_width) // 2
            y_offset = (scaled.height() - preview_height) // 2
            cropped = scaled.copy(x_offset, y_offset, preview_width, preview_height)
            painter = QPainter(pixmap)
            painter.drawPixmap(0, 0, cropped)
            painter.end()

        # 绘制示例标题文字
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        # 字体大小：确保最小14像素可见
        scaled_font_size = max(14, int(self._style.font_size * scale_ratio))
        font = QFont(normalize_font_name(self._style.font_name), scaled_font_size)
        font.setBold(self._style.bold)
        font.setItalic(self._style.italic)
        if self._style.letter_spacing != 0:
            font.setLetterSpacing(QFont.AbsoluteSpacing, self._style.letter_spacing * scale_ratio)
        painter.setFont(font)

        sample_text = "示例标题文本"
        metrics = QFontMetrics(font)
        text_width = metrics.horizontalAdvance(sample_text)
        text_height = metrics.height()

        # 根据对齐方式计算位置
        margin_v = int(preview_height * self._style.margin_v_percent / 100)
        margin_l = int(self._style.margin_l * scale_ratio)
        margin_r = int(self._style.margin_r * scale_ratio)

        align = self._style.alignment
        if align in (1, 4, 7):
            x = margin_l
        elif align in (3, 6, 9):
            x = preview_width - text_width - margin_r
        else:
            x = (preview_width - text_width) // 2

        if align in (7, 8, 9):
            y = margin_v + text_height
        elif align in (4, 5, 6):
            y = preview_height // 2 + text_height // 3
        else:
            y = preview_height - margin_v

        scaled_outline = max(1, int(self._style.outline_width * scale_ratio))

        # 绘制背景框
        if self._style.border_style == 3:
            box_color = QColor(self._style.back_color)
            box_color.setAlpha(max(0, 255 - self._style.back_color_alpha))
            pad = 4
            painter.fillRect(x - pad, y - text_height, text_width + pad * 2, text_height + pad, box_color)

        # 绘制阴影
        if self._style.shadow_depth > 0:
            shadow_offset = max(1, int(self._style.shadow_depth * scale_ratio))
            shadow_color = QColor(self._style.back_color)
            shadow_color.setAlpha(128)
            painter.setPen(shadow_color)
            painter.drawText(x + shadow_offset, y + shadow_offset, sample_text)

        # 绘制描边
        if self._style.outline_width > 0:
            painter.setPen(QColor(self._style.outline_color))
            for dx in range(-scaled_outline, scaled_outline + 1):
                for dy in range(-scaled_outline, scaled_outline + 1):
                    if dx != 0 or dy != 0:
                        painter.drawText(x + dx, y + dy, sample_text)

        # 绘制主文字
        painter.setPen(QColor(self._style.primary_color))
        painter.drawText(x, y, sample_text)
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
        self._style.fade_in_ms = self._fade_in_combo.currentData()
        self._style.fade_out_ms = self._fade_out_combo.currentData()
        self._style.display_duration = self._display_duration_combo.currentData()
        self._style.cover_mode = self._cover_mode_checkbox.isChecked()
        self._style.cover_duration = 0.04  # 固定为1帧
        self._style.cover_crop_to_square = True  # 固定裁剪成1:1
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
            (i for i, (_, fn) in enumerate(self._font_presets) if fn == style.font_name),
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
        # 淡入淡出
        fade_in_idx = next((i for i, (_, v) in enumerate([(500, 500), (300, 300), (1000, 1000)]) if v[0] == style.fade_in_ms), 0)
        self._fade_in_combo.setCurrentIndex(fade_in_idx)
        fade_out_idx = next((i for i, (_, v) in enumerate([(300, 300), (500, 500), (1000, 1000)]) if v[0] == style.fade_out_ms), 0)
        self._fade_out_combo.setCurrentIndex(fade_out_idx)
        # 显示时长
        disp_dur = getattr(style, 'display_duration', 0.0)
        disp_idx = next((i for i, v in enumerate([0.0, 0.1, 0.5, 1.0, 2.0, 3.0, 5.0]) if v == disp_dur), 0)
        self._display_duration_combo.setCurrentIndex(disp_idx)
        # 封面模式
        self._cover_mode_checkbox.setChecked(getattr(style, 'cover_mode', False))

        self._update_effect_visibility()
        self._update_cover_mode_visibility()
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
