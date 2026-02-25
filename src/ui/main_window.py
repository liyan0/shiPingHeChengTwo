from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QButtonGroup,
    QLabel,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from .home_page import HomePage
from .settings_page import SettingsPage
from .theme import Styles
from ..models.config import Config
from ..models.history import HistoryManager


class MainWindow(QMainWindow):
    def __init__(self, config: Config, history_manager: HistoryManager, project_dir: str):
        super().__init__()
        self.config = config
        self.history_manager = history_manager
        self.project_dir = project_dir

        self.setWindowTitle("带货视频生成工具")
        self.setMinimumSize(800, 600)
        self.resize(1100, 800)

        # 应用全局样式
        self._apply_global_styles()

        self._setup_ui()

    def _apply_global_styles(self):
        """应用全局样式表"""
        global_style = f"""
            {Styles.CHECKBOX}
            {Styles.SPINBOX}
            {Styles.COMBOBOX}
            {Styles.LISTWIDGET}
            {Styles.LINEEDIT}
            {Styles.TEXTEDIT}
            {Styles.PROGRESSBAR}
            {Styles.SLIDER}
            {Styles.GROUPBOX}
            {Styles.RADIOBUTTON}
            {Styles.TABWIDGET}
        """
        self.setStyleSheet(global_style)

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        nav_widget = self._create_nav_bar()
        main_layout.addWidget(nav_widget)

        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack)

        self.home_page = HomePage(
            self.config, self.history_manager, self.project_dir
        )

        self.settings_page = SettingsPage(self.config)

        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.settings_page)

    def _create_nav_bar(self) -> QWidget:
        nav_widget = QWidget()
        nav_widget.setFixedHeight(40)
        nav_widget.setStyleSheet("""
            QWidget#nav_container {
                background-color: #f0f0f0;
                border-bottom: 1px solid #d0d0d0;
            }
        """)
        nav_widget.setObjectName("nav_container")

        nav_layout = QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(15, 0, 15, 0)
        nav_layout.setSpacing(0)

        title_label = QLabel("带货视频生成工具")
        title_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        title_label.setStyleSheet("color: #333333; background: transparent;")
        nav_layout.addWidget(title_label)

        nav_layout.addSpacing(10)

        version_label = QLabel("v1.0")
        version_label.setFont(QFont("Microsoft YaHei", 9))
        version_label.setStyleSheet("color: #888888; background: transparent;")
        nav_layout.addWidget(version_label)

        nav_layout.addSpacing(30)

        self.nav_buttons = QButtonGroup(self)
        self.nav_buttons.setExclusive(True)

        buttons_data = [("首页", 0), ("设置", 1)]

        btn_style = """
            QPushButton {
                color: #0066cc;
                border: none;
                padding: 8px 16px;
                font-size: 13px;
                background-color: transparent;
                border-bottom: 2px solid transparent;
            }
            QPushButton:hover {
                color: #004499;
            }
            QPushButton:checked {
                color: #0066cc;
                border-bottom: 2px solid #0066cc;
            }
        """

        for text, index in buttons_data:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setFont(QFont("Microsoft YaHei", 10))
            btn.setStyleSheet(btn_style)
            self.nav_buttons.addButton(btn, index)
            nav_layout.addWidget(btn)

            if index == 0:
                btn.setChecked(True)

        nav_layout.addStretch()

        self.status_label = QLabel("就绪")
        self.status_label.setFont(QFont("Microsoft YaHei", 9))
        self.status_label.setStyleSheet("color: #0066cc; background: transparent;")
        nav_layout.addWidget(self.status_label)

        self.nav_buttons.buttonClicked[int].connect(self._switch_page)

        return nav_widget

    def _switch_page(self, index: int):
        self.stack.setCurrentIndex(index)
        button = self.nav_buttons.button(index)
        if button:
            button.setChecked(True)

    def update_status(self, status: str):
        self.status_label.setText(status)

    def closeEvent(self, event):
        """Save current prompt when window closes"""
        self.home_page.save_current_prompt()
        self.config.save()
        event.accept()
