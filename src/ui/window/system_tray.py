import os

from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from core.shortcut_manager import ShortcutManager
from ui.window.main_window import MainWindow


class SystemTray(QSystemTrayIcon):
    """Manage the system tray icon for the main window."""

    def __init__(
        self, main_window: MainWindow, shortcut_manager: ShortcutManager
    ) -> None:
        # Set icon
        base_dir = os.getcwd()
        icon_path = os.path.join(base_dir, "src", "assets", "blank.ico")
        icon = QIcon(icon_path)

        super().__init__(icon)
        self.setToolTip("whispr")
        self.main_window = main_window
        self.shortcut_manager = shortcut_manager

        # Quit action
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit_app)

        # Add actions to menu
        self.menu = QMenu()
        self.menu.addAction(quit_action)

        # Set the context menu
        self.setContextMenu(self.menu)

        # Connect the activated signal (click) to toggle the window
        self.activated.connect(self._on_tray_activated)

        self.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle system tray icon activation events.

        Args:
            reason (QSystemTrayIcon.ActivationReason): The reason the tray icon was activated.
        """
        # Show/Hide on left click
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.main_window.toggle_window_visibility()

    def _quit_app(self) -> None:
        """Quit the application via the main window."""
        self.main_window.quit_app()
