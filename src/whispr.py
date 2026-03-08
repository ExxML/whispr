import sys

from PyQt6.QtWidgets import QApplication

from core.ai_sender import AISender
from core.screenshot_manager import ScreenshotManager
from core.shortcut_manager import ShortcutManager
from ui.window.main_window import MainWindow
from ui.window.system_tray import SystemTray


if __name__ == "__main__":
    # Launch the application and its components
    app = QApplication(sys.argv)
    screenshot_manager = ScreenshotManager()
    ai_sender = AISender()
    main_window = MainWindow(ai_sender, screenshot_manager)
    shortcut_manager = ShortcutManager(main_window, screenshot_manager)
    tray_icon = SystemTray(main_window, shortcut_manager)

    sys.exit(app.exec())
