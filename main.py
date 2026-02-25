import sys
import os

# Pre-load torch before Qt to avoid DLL conflict on Windows
try:
    import torch
except ImportError:
    pass

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from src.ui.main_window import MainWindow
from src.models.config import Config
from src.models.history import HistoryManager


def main():
    project_dir = os.path.dirname(os.path.abspath(__file__))

    config_path = os.path.join(project_dir, "config.json")
    history_path = os.path.join(project_dir, "history.json")

    config = Config.load(config_path)
    history_manager = HistoryManager(history_path)

    save_dir = os.path.join(project_dir, "input", "视频图片素材文件夹")
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow(config, history_manager, project_dir)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
