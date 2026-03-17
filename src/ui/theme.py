"""统一主题样式管理"""


class Colors:
    """颜色常量"""
    PRIMARY = "#0066cc"
    PRIMARY_HOVER = "#0055aa"
    PRIMARY_DARK = "#004499"

    TEXT_PRIMARY = "#333333"
    TEXT_SECONDARY = "#666666"
    TEXT_DISABLED = "#999999"
    TEXT_HINT = "#888888"

    BG_WHITE = "#ffffff"
    BG_LIGHT = "#f8f8f8"
    BG_GRAY = "#f0f0f0"
    BG_HOVER = "#e8f4fc"
    BG_SELECTED = "#cce5ff"
    BG_SELECTED_HOVER = "#b8daff"
    BG_DARK = "#2d2d2d"

    BORDER = "#d0d0d0"
    BORDER_DARK = "#b0b0b0"
    BORDER_FOCUS = "#0066cc"
    BORDER_LIGHT = "#e0e0e0"


class Styles:
    """组件样式"""

    # QCheckBox - 添加可见的边框
    CHECKBOX = """
        QCheckBox {
            color: #333333;
            background: transparent;
            spacing: 3px;
            padding: 1px;
        }
        QCheckBox::indicator {
            width: 12px;
            height: 12px;
            border: 2px solid #b0b0b0;
            border-radius: 3px;
            background-color: #ffffff;
        }
        QCheckBox::indicator:hover {
            border-color: #0066cc;
        }
        QCheckBox::indicator:checked {
            background-color: #0066cc;
            border-color: #0066cc;
        }
        QCheckBox::indicator:checked:hover {
            background-color: #0055aa;
            border-color: #0055aa;
        }
        QCheckBox:disabled {
            color: #999999;
        }
        QCheckBox::indicator:disabled {
            border-color: #d0d0d0;
            background-color: #f0f0f0;
        }
    """

    # QSpinBox/QDoubleSpinBox - 确保文字和按钮可见
    SPINBOX = """
        QSpinBox, QDoubleSpinBox {
            border: 1px solid #d0d0d0;
            border-radius: 3px;
            padding: 2px 3px;
            padding-right: 18px;
            background-color: #ffffff;
            color: #333333;
            min-height: 18px;
            min-width: 70px;
        }
        QSpinBox:hover, QDoubleSpinBox:hover {
            border-color: #0066cc;
        }
        QSpinBox:focus, QDoubleSpinBox:focus {
            border-color: #0066cc;
        }
        QSpinBox:disabled, QDoubleSpinBox:disabled {
            background-color: #f0f0f0;
            color: #999999;
        }
        QSpinBox::up-button, QDoubleSpinBox::up-button {
            subcontrol-origin: border;
            subcontrol-position: top right;
            width: 16px;
            border-left: 1px solid #d0d0d0;
            border-bottom: 1px solid #d0d0d0;
            border-top-right-radius: 3px;
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f8f8f8, stop:1 #e8e8e8);
        }
        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e0f0ff, stop:1 #c0e0ff);
        }
        QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed {
            background: #b0d0f0;
        }
        QSpinBox::down-button, QDoubleSpinBox::down-button {
            subcontrol-origin: border;
            subcontrol-position: bottom right;
            width: 16px;
            border-left: 1px solid #d0d0d0;
            border-bottom-right-radius: 3px;
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f8f8f8, stop:1 #e8e8e8);
        }
        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e0f0ff, stop:1 #c0e0ff);
        }
        QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {
            background: #b0d0f0;
        }
        QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
            width: 0;
            height: 0;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-bottom: 5px solid #555555;
        }
        QSpinBox::up-arrow:hover, QDoubleSpinBox::up-arrow:hover {
            border-bottom-color: #0066cc;
        }
        QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
            width: 0;
            height: 0;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid #555555;
        }
        QSpinBox::down-arrow:hover, QDoubleSpinBox::down-arrow:hover {
            border-top-color: #0066cc;
        }
        QSpinBox::up-arrow:disabled, QSpinBox::down-arrow:disabled,
        QDoubleSpinBox::up-arrow:disabled, QDoubleSpinBox::down-arrow:disabled {
            border-top-color: #cccccc;
            border-bottom-color: #cccccc;
        }
    """

    # QComboBox - 修复悬停时文字消失
    COMBOBOX = """
        QComboBox {
            border: 1px solid #d0d0d0;
            border-radius: 3px;
            padding: 1px 4px;
            background-color: #ffffff;
            color: #333333;
            min-height: 14px;
            min-width: 80px;
        }
        QComboBox:hover {
            border-color: #b0b0b0;
            background-color: #ffffff;
            color: #333333;
        }
        QComboBox:focus {
            border-color: #0066cc;
        }
        QComboBox:disabled {
            background-color: #f0f0f0;
            color: #999999;
        }
        QComboBox::drop-down {
            border: none;
            width: 16px;
            background: transparent;
        }
        QComboBox::down-arrow {
            width: 10px;
            height: 10px;
        }
        QComboBox QAbstractItemView {
            border: 1px solid #d0d0d0;
            background-color: #ffffff;
            color: #333333;
            selection-background-color: #cce5ff;
            selection-color: #333333;
            outline: none;
        }
        QComboBox QAbstractItemView::item {
            padding: 2px 4px;
            min-height: 14px;
            color: #333333;
            background-color: #ffffff;
        }
        QComboBox QAbstractItemView::item:hover {
            background-color: #e8f4fc;
            color: #333333;
        }
        QComboBox QAbstractItemView::item:selected {
            background-color: #cce5ff;
            color: #333333;
        }
    """

    # QListWidget - 增强选中效果
    LISTWIDGET = """
        QListWidget {
            border: 1px solid #d0d0d0;
            border-radius: 3px;
            background-color: #ffffff;
            outline: none;
        }
        QListWidget::item {
            padding: 5px 8px;
            border-bottom: 1px solid #f0f0f0;
            color: #333333;
            background-color: #ffffff;
        }
        QListWidget::item:hover {
            background-color: #f5f5f5;
            color: #333333;
        }
        QListWidget::item:selected {
            background-color: #cce5ff;
            color: #333333;
            border-left: 3px solid #0066cc;
        }
        QListWidget::item:selected:hover {
            background-color: #b8daff;
            color: #333333;
        }
    """

    # QLineEdit - 输入框样式
    LINEEDIT = """
        QLineEdit {
            border: 1px solid #d0d0d0;
            border-radius: 3px;
            padding: 2px 6px;
            background-color: #ffffff;
            color: #333333;
            min-height: 12px;
        }
        QLineEdit:hover {
            border-color: #b0b0b0;
        }
        QLineEdit:focus {
            border-color: #0066cc;
        }
        QLineEdit:disabled {
            background-color: #f0f0f0;
            color: #999999;
        }
    """

    # QTextEdit - 文本编辑框样式
    TEXTEDIT = """
        QTextEdit {
            border: 1px solid #d0d0d0;
            border-radius: 3px;
            padding: 4px;
            background-color: #ffffff;
            color: #333333;
        }
        QTextEdit:hover {
            border-color: #b0b0b0;
        }
        QTextEdit:focus {
            border-color: #0066cc;
        }
        QTextEdit:disabled {
            background-color: #f0f0f0;
            color: #999999;
        }
    """

    # QPushButton - 主要按钮
    BUTTON_PRIMARY = """
        QPushButton {
            color: #ffffff;
            background-color: #0066cc;
            border: 1px solid #0055aa;
            border-radius: 3px;
            padding: 2px 8px;
            min-height: 16px;
        }
        QPushButton:hover {
            background-color: #0055aa;
        }
        QPushButton:pressed {
            background-color: #004499;
        }
        QPushButton:disabled {
            background-color: #cccccc;
            border-color: #bbbbbb;
            color: #888888;
        }
    """

    # QPushButton - 次要按钮
    BUTTON_SECONDARY = """
        QPushButton {
            color: #0066cc;
            background-color: #f8f8f8;
            border: 1px solid #d0d0d0;
            border-radius: 3px;
            padding: 2px 8px;
            min-height: 16px;
        }
        QPushButton:hover {
            background-color: #e8f4fc;
            border-color: #0066cc;
        }
        QPushButton:pressed {
            background-color: #cce5ff;
        }
        QPushButton:disabled {
            color: #999999;
            background-color: #f0f0f0;
            border-color: #d0d0d0;
        }
    """

    # QPushButton - 停止/危险按钮
    BUTTON_DANGER = """
        QPushButton {
            color: #ffffff;
            background-color: #dc3545;
            border: 1px solid #c82333;
            border-radius: 3px;
            padding: 2px 8px;
            min-height: 16px;
        }
        QPushButton:hover {
            background-color: #c82333;
        }
        QPushButton:pressed {
            background-color: #bd2130;
        }
        QPushButton:disabled {
            background-color: #e9a0a7;
            border-color: #e9a0a7;
        }
    """

    # QProgressBar - 进度条
    PROGRESSBAR = """
        QProgressBar {
            border: 1px solid #d0d0d0;
            border-radius: 3px;
            background-color: #f0f0f0;
            text-align: center;
            color: #333333;
            min-height: 12px;
        }
        QProgressBar::chunk {
            background-color: #0066cc;
            border-radius: 2px;
        }
    """

    # QSlider - 滑块
    SLIDER = """
        QSlider::groove:horizontal {
            border: 1px solid #d0d0d0;
            height: 3px;
            background: #f0f0f0;
            border-radius: 2px;
        }
        QSlider::handle:horizontal {
            background: #0066cc;
            border: 1px solid #0055aa;
            width: 12px;
            height: 12px;
            margin: -4px 0;
            border-radius: 6px;
        }
        QSlider::handle:horizontal:hover {
            background: #0055aa;
        }
        QSlider::sub-page:horizontal {
            background: #cce5ff;
            border-radius: 3px;
        }
    """

    # QTabWidget - 标签页
    TABWIDGET = """
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
            color: #333333;
        }
        QTabBar::tab:selected {
            background-color: #ffffff;
            border-bottom: 1px solid #ffffff;
            color: #0066cc;
        }
        QTabBar::tab:hover:!selected {
            background-color: #e8e8e8;
        }
    """

    # QGroupBox - 分组框
    GROUPBOX = """
        QGroupBox {
            border: 1px solid #d0d0d0;
            border-radius: 3px;
            margin-top: 4px;
            padding-top: 4px;
            background-color: #ffffff;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 3px;
            color: #333333;
        }
    """

    # QRadioButton - 单选按钮
    RADIOBUTTON = """
        QRadioButton {
            color: #333333;
            background: transparent;
            spacing: 3px;
            padding: 1px;
        }
        QRadioButton::indicator {
            width: 12px;
            height: 12px;
            border: 2px solid #b0b0b0;
            border-radius: 9px;
            background-color: #ffffff;
        }
        QRadioButton::indicator:hover {
            border-color: #0066cc;
        }
        QRadioButton::indicator:checked {
            background-color: #0066cc;
            border-color: #0066cc;
        }
        QRadioButton:disabled {
            color: #999999;
        }
        QRadioButton::indicator:disabled {
            border-color: #d0d0d0;
            background-color: #f0f0f0;
        }
    """

    # QGroupBox - 设置面板分组框
    SETTINGS_GROUPBOX = """
        QGroupBox {
            border: 1px solid #d0d0d0;
            border-radius: 3px;
            margin-top: 8px;
            padding-top: 6px;
            background-color: #ffffff;
            font-family: "Microsoft YaHei";
            font-size: 9pt;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 6px;
            color: #0066cc;
            font-weight: bold;
        }
    """

    # 日志区域样式
    LOG_AREA = """
        QTextEdit {
            background-color: #1e1e1e;
            color: #d4d4d4;
            border: none;
            font-family: Consolas, "Microsoft YaHei", monospace;
            font-size: 11px;
            padding: 6px;
        }
    """

    # 工具栏样式
    TOOLBAR = """
        QWidget {
            background-color: #f8f8f8;
            border-bottom: 1px solid #e0e0e0;
        }
    """

    # 内容框架样式
    CONTENT_FRAME = """
        QFrame {
            background-color: #ffffff;
            border: 1px solid #d0d0d0;
            border-radius: 3px;
        }
    """


def get_input_style():
    """获取输入框通用样式"""
    return """
        QLineEdit, QComboBox {
            border: 1px solid #d0d0d0;
            border-radius: 3px;
            padding: 2px 6px;
            background-color: #ffffff;
            color: #333333;
            min-height: 12px;
        }
        QLineEdit:hover, QComboBox:hover {
            border-color: #b0b0b0;
        }
        QLineEdit:focus, QComboBox:focus {
            border-color: #0066cc;
        }
        QComboBox::drop-down {
            border: none;
            width: 16px;
        }
        QComboBox QAbstractItemView {
            border: 1px solid #d0d0d0;
            background-color: #ffffff;
            color: #333333;
            selection-background-color: #cce5ff;
            selection-color: #333333;
        }
        QComboBox QAbstractItemView::item {
            padding: 2px 4px;
            min-height: 14px;
            color: #333333;
        }
        QComboBox QAbstractItemView::item:hover {
            background-color: #e8f4fc;
            color: #333333;
        }
    """


def get_spin_style():
    """获取数字输入框通用样式"""
    return Styles.SPINBOX


def get_label_style():
    """获取标签通用样式"""
    return "color: #333333; border: none; background: transparent;"
