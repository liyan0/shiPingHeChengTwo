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
    QFontComboBox,
)
from PyQt5.QtCore import Qt, QTimer, QRect
from PyQt5.QtGui import QFont, QColor, QPainter, QPixmap, QPen, QFontMetrics, QLinearGradient, QFontDatabase

from ..models.config import SubtitleStyleConfig, SubtitleStyleTemplate
from ..core.subtitle_effects import normalize_font_name


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
        self._preview_ratio = "landscape"  # 默认横屏

        self._setup_ui()
        self._load_background_image()
        self._update_preview()

    def _setup_ui(self):
        self.setWindowTitle("字幕设置")
        self.setMinimumWidth(500)
        self.setMinimumHeight(580)

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

        # Font name
        font_name_layout = QHBoxLayout()
        font_name_label = QLabel("字体名称:")
        font_name_label.setFont(QFont("Microsoft YaHei", 9))
        font_name_label.setFixedWidth(80)
        self._font_name_combo = QComboBox()
        self._font_name_combo.setMinimumWidth(200)
        self._populate_font_list()
        self._font_name_combo.currentTextChanged.connect(self._on_font_changed)
        font_name_layout.addWidget(font_name_label)
        font_name_layout.addWidget(self._font_name_combo)
        font_name_layout.addStretch()
        settings_layout.addLayout(font_name_layout)

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

        # Letter spacing (字间距)
        spacing_layout = QHBoxLayout()
        spacing_label = QLabel("字间距:")
        spacing_label.setFont(QFont("Microsoft YaHei", 9))
        spacing_label.setFixedWidth(80)
        self._letter_spacing_spin = QDoubleSpinBox()
        self._letter_spacing_spin.setRange(-5.0, 20.0)
        self._letter_spacing_spin.setValue(self._style.letter_spacing)
        self._letter_spacing_spin.setSuffix(" px")
        self._letter_spacing_spin.setDecimals(1)
        self._letter_spacing_spin.valueChanged.connect(self._on_style_changed)
        spacing_layout.addWidget(spacing_label)
        spacing_layout.addWidget(self._letter_spacing_spin)
        spacing_layout.addStretch()
        settings_layout.addLayout(spacing_layout)

        layout.addWidget(settings_group)

        # Preview group
        preview_group = QGroupBox("预览")
        preview_group.setFont(QFont("Microsoft YaHei", 10))
        preview_layout = QVBoxLayout(preview_group)

        # 预览比例选择
        ratio_layout = QHBoxLayout()
        ratio_label = QLabel("预览比例:")
        self._ratio_combo = QComboBox()
        self._ratio_combo.addItem("横屏 16:9", "landscape")
        self._ratio_combo.addItem("竖屏 9:16", "portrait")
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

    def _populate_font_list(self):
        """填充字体列表，优先显示中文字体"""
        font_db = QFontDatabase()
        all_families = font_db.families()

        # 常用中文字体列表（优先显示）
        chinese_fonts = [
            "Microsoft YaHei", "微软雅黑",
            "SimHei", "黑体",
            "SimSun", "宋体",
            "KaiTi", "楷体",
            "FangSong", "仿宋",
            "STXihei", "华文细黑",
            "STHeiti", "华文黑体",
            "STKaiti", "华文楷体",
            "STSong", "华文宋体",
            "STFangsong", "华文仿宋",
            "STZhongsong", "华文中宋",
            "YouYuan", "幼圆",
            "LiSu", "隶书",
            "Source Han Sans CN", "思源黑体",
            "Source Han Serif CN", "思源宋体",
            "Noto Sans CJK SC",
            "Noto Serif CJK SC",
            "PingFang SC", "苹方",
            "Hiragino Sans GB",
            "WenQuanYi Micro Hei", "文泉驿微米黑",
            "WenQuanYi Zen Hei", "文泉驿正黑",
        ]

        # 找出系统中存在的中文字体（只保留中文相关，不再混入英文字体）
        available_chinese = []
        chinese_set = set(chinese_fonts)

        for family in all_families:
            if family in chinese_set:
                available_chinese.append(family)
            else:
                # 检查是否包含中文字符（可能是其他中文字体）
                has_chinese = any('\u4e00' <= ch <= '\u9fff' for ch in family)
                if has_chinese:
                    available_chinese.append(family)
                else:
                    # 非中文字体不加入列表
                    pass

        # 按优先级排序中文字体
        def chinese_priority(font):
            try:
                return chinese_fonts.index(font)
            except ValueError:
                return len(chinese_fonts)

        available_chinese.sort(key=chinese_priority)

        # 添加到下拉框（仅中文）
        self._font_name_combo.blockSignals(True)
        self._font_name_combo.clear()

        # 先添加中文字体
        if available_chinese:
            for font in available_chinese:
                self._font_name_combo.addItem(font)

        # 不再添加英文/其他字体

        # 设置当前选中的字体
        current_font = self._style.font_name
        index = self._font_name_combo.findText(current_font)
        if index >= 0:
            self._font_name_combo.setCurrentIndex(index)
        else:
            # 如果找不到，默认选择第一个
            if self._font_name_combo.count() > 0:
                self._font_name_combo.setCurrentIndex(0)
                self._style.font_name = self._font_name_combo.currentText()

        self._font_name_combo.blockSignals(False)

    def _on_font_changed(self, font_name: str):
        """字体变更处理"""
        if font_name:
            self._style.font_name = font_name
            self._update_preview()

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
            self._create_default_background()
            return

        image_files = []
        for f in os.listdir(self._image_dir):
            ext = os.path.splitext(f)[1].lower()
            if ext in self.SUPPORTED_IMAGE_EXTENSIONS:
                image_files.append(os.path.join(self._image_dir, f))

        if image_files:
            selected = random.choice(image_files)
            self._background_image = QPixmap(selected)
        else:
            self._create_default_background()

    def _create_default_background(self):
        """创建默认的预览背景图（模拟竖屏视频）"""
        # 创建一个 1080x1920 的竖屏背景
        width, height = 1080, 1920
        pixmap = QPixmap(width, height)

        # 使用渐变背景模拟视频画面
        painter = QPainter(pixmap)
        from PyQt5.QtGui import QLinearGradient
        gradient = QLinearGradient(0, 0, 0, height)
        gradient.setColorAt(0, QColor("#1a1a2e"))
        gradient.setColorAt(0.5, QColor("#16213e"))
        gradient.setColorAt(1, QColor("#0f3460"))
        painter.fillRect(0, 0, width, height, gradient)

        # 添加一些装饰元素让预览更真实
        painter.setPen(QPen(QColor("#ffffff30"), 2))
        painter.drawLine(100, 200, width - 100, 200)
        painter.drawLine(100, height - 400, width - 100, height - 400)

        # 添加提示文字
        hint_font = QFont("Microsoft YaHei", 24)
        painter.setFont(hint_font)
        painter.setPen(QColor("#ffffff50"))
        painter.drawText(width // 2 - 100, height // 2, "视频预览区域")

        painter.end()
        self._background_image = pixmap

    def _on_ratio_changed(self):
        self._preview_ratio = self._ratio_combo.currentData()
        self._update_preview()

    def _update_preview(self):
        # ????/??????????
        container_width = self._preview_label.parent().width() - 20 if self._preview_label.parent() else 480
        container_width = max(300, container_width)
        max_preview_height = 220

        if self._preview_ratio == "landscape":
            # ?? 16:9
            preview_width = container_width
            preview_height = int(container_width * 9 / 16)
            if preview_height > max_preview_height:
                preview_height = max_preview_height
                preview_width = int(preview_height * 16 / 9)
            sim_width, sim_height = 1920, 1080
        else:
            # ?? 9:16
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

        # 绘制示例字幕文字
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        # 字体大小：确保最小14像素可见
        scaled_font_size = max(14, int(self._style.font_size * scale_ratio))
        font = QFont(normalize_font_name(self._style.font_name), scaled_font_size)
        font.setBold(True)
        if self._style.letter_spacing != 0:
            font.setLetterSpacing(QFont.AbsoluteSpacing, self._style.letter_spacing * scale_ratio)
        painter.setFont(font)

        sample_text = "示例字幕文本"

        # 字幕位置：底部居中（使用矩形布局，避免文本超出画布）
        margin_v = int(preview_height * self._style.margin_v_percent / 100)
        margin_l = int(self._style.margin_l * scale_ratio)
        margin_r = int(self._style.margin_r * scale_ratio)
        available_width = max(20, preview_width - margin_l - margin_r)
        available_height = max(20, preview_height - margin_v)
        text_rect = QRect(margin_l, 0, available_width, available_height)
        text_flags = Qt.AlignHCenter | Qt.AlignBottom

        scaled_outline = max(1, int(self._style.outline_width * scale_ratio))

        # 绘制描边
        if self._style.outline_width > 0:
            painter.setPen(QColor(self._style.outline_color))
            for dx in range(-scaled_outline, scaled_outline + 1):
                for dy in range(-scaled_outline, scaled_outline + 1):
                    if dx != 0 or dy != 0:
                        painter.drawText(text_rect.translated(dx, dy), text_flags, sample_text)

        # 绘制主文字
        painter.setPen(QColor(self._style.primary_color))
        painter.drawText(text_rect, text_flags, sample_text)

        # 如果字幕禁用，显示半透明遮罩提示
        if not self._style.enabled:
            painter.fillRect(0, 0, preview_width, preview_height, QColor(0, 0, 0, 128))
            painter.setPen(QColor("#ffffff"))
            hint_font = QFont("Microsoft YaHei", 14)
            painter.setFont(hint_font)
            hint_text = "字幕已禁用"
            hint_metrics = QFontMetrics(hint_font)
            hint_x = (preview_width - hint_metrics.horizontalAdvance(hint_text)) // 2
            painter.drawText(hint_x, preview_height // 2, hint_text)

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
        self._font_name_combo.setEnabled(enabled)
        self._font_size_spin.setEnabled(enabled)
        self._primary_color_btn.setEnabled(enabled)
        self._outline_color_btn.setEnabled(enabled)
        self._outline_width_spin.setEnabled(enabled)
        self._margin_spin.setEnabled(enabled)
        self._margin_l_spin.setEnabled(enabled)
        self._margin_r_spin.setEnabled(enabled)
        self._letter_spacing_spin.setEnabled(enabled)

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
        self._style.letter_spacing = self._letter_spacing_spin.value()
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
        self._style.letter_spacing = template.style.letter_spacing

        self._enabled_checkbox.setChecked(self._style.enabled)
        # 更新字体选择
        font_index = self._font_name_combo.findText(self._style.font_name)
        if font_index >= 0:
            self._font_name_combo.setCurrentIndex(font_index)
        self._font_size_spin.setValue(self._style.font_size)
        self._outline_width_spin.setValue(self._style.outline_width)
        self._margin_spin.setValue(self._style.margin_v_percent)
        self._margin_l_spin.setValue(self._style.margin_l)
        self._margin_r_spin.setValue(self._style.margin_r)
        self._letter_spacing_spin.setValue(self._style.letter_spacing)
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
