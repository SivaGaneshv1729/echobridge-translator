"""EchoBridge: Zero-Cost Offline Real-Time Speech Translator Application Entry Point."""
import sys
import os
import ctypes
import logging

# Ensure UTF-8 stdout on Windows
sys.stdout.reconfigure(encoding='utf-8')

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from ui.main_window import MainWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s"
)
logger = logging.getLogger("EchoBridge")

def set_windows_app_id():
    """Set Windows Application User Model ID for clean taskbar grouping."""
    if sys.platform == "win32":
        try:
            myappid = "echobridge.translator.offline.1.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

def main():
    if getattr(sys, 'frozen', False):
        # When running as a compiled PyInstaller executable, ensure CWD is executable directory
        exe_dir = os.path.dirname(sys.executable)
        os.chdir(exe_dir)
        sys.path.insert(0, exe_dir)

    set_windows_app_id()
    
    # Ensure high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("EchoBridge")
    app.setOrganizationName("EchoBridge")

    window = MainWindow("config/settings.json")
    window.show()

    logger.info("EchoBridge UI launched successfully.")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
