import ctypes
from ctypes import wintypes

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QMouseEvent, QPainter, QPaintEvent, QPen, QResizeEvent
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from core.ai_receiver import AIReceiver
from core.ai_sender import AISender
from core.screenshot_manager import ScreenshotManager
from ui.chat.chat_area import ChatArea
from ui.input.input_field import InputField
from ui.theme import BG_COLOR, PRIMARY_COLOR, qcolor, qss
from ui.window.clear_chat_button import ClearChatButton
from ui.window.screenshot_tray import ScreenshotTray


class MainWindow(QWidget):
    """Render the main application window and its chat controls."""

    BG_COLOR = qcolor(BG_COLOR, 153)

    def __init__(
        self, ai_sender: AISender, screenshot_manager: ScreenshotManager
    ) -> None:
        super().__init__()
        self.ai_sender = ai_sender
        self.screenshot_manager = screenshot_manager
        self._init_UI()
        self.worker = AIReceiver(ai_sender, self.chat_area)
        self.input_field.model_changed.connect(self.ai_sender.set_model)
        self.input_field.thinking_mode_changed.connect(self.ai_sender.set_thinking_mode)

    def toggle_window_visibility(self) -> None:
        """Toggle the main window between visible and hidden states."""
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()  # Bring to front

    def hide(self) -> None:
        """Close the model popup and flush the backing store before hiding."""
        if hasattr(self, "input_field"):
            self.input_field.input_settings.model_dropdown.close_popup()
            self.repaint()
            QApplication.processEvents()
        super().hide()

    def send_message(self, message: str) -> None:
        """Send a user message with any pending screenshot attachments.

        Args:
            message (str): The user's message text.
        """
        attachments = self.screenshot_manager.get_and_clear_pending()
        self.screenshot_tray.clear()
        self.worker.handle_message(message, attachments or None)

    def quit_app(self) -> None:
        """Quit the application, stopping any active worker and clearing chat."""
        # Stop any active worker
        if self.worker is not None:
            self.worker.stop()

        self.chat_area.clear_chat_messages()
        self.ai_sender.reset_chat()
        self.screenshot_manager.clear_screenshots()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def resizeEvent(self, event: QResizeEvent | None) -> None:
        """Reposition the floating screenshot tray when the window is resized.

        Args:
            event (QResizeEvent): The resize event passed to the base widget.
        """
        super().resizeEvent(event)
        self._position_screenshot_tray()

    # Override mousePressEvent to automatically set focus to input field
    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        """Set focus to the input field when the window is clicked.

        Args:
            event (QMouseEvent): The mouse press event.
        """
        self.input_field.input_field.setFocus()
        super().mousePressEvent(event)

    # Override paintEvent to draw app window
    def paintEvent(self, _event: QPaintEvent | None) -> None:
        """Paint the main window with rounded corners and a border."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        radius = 8

        # Draw window with rounded corners
        painter.setBrush(self.BG_COLOR)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, radius, radius)

        # Draw window border
        border_width = 1
        border_rect = rect.adjusted(
            border_width, border_width, -border_width, -border_width
        )
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(qcolor(PRIMARY_COLOR, 128), border_width))
        painter.drawRoundedRect(border_rect, radius, radius)

    def _init_UI(self) -> None:
        """Initialize the main window UI layout and components."""
        # Config variables
        self.window_width = 550
        self.window_height = 600

        # Set window flags for main window behavior
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            # Qt.WindowType.WindowTransparentForInput # Click-through
        )

        # Translucent bg for rounded corners
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Prevent cursor from changing when hovering over the window
        self.setAttribute(Qt.WidgetAttribute.WA_SetCursor, False)
        self.unsetCursor()

        # Window setup (position main window at center-top on screen)
        self.primary_screen = QApplication.primaryScreen()
        assert self.primary_screen is not None
        screen_rect = self.primary_screen.availableGeometry()
        self.setGeometry(
            (screen_rect.width() - self.window_width) // 2,
            2,
            self.window_width,
            self.window_height,
        )

        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create chat area
        self.chat_area = ChatArea(self)

        # Create input field
        self.input_field = InputField(self)

        # Create screenshot tray as a floating overlay (not in any layout)
        self.screenshot_tray = ScreenshotTray(self.screenshot_manager, self)

        # Create and add title bar buttons
        self.clear_chat_button = ClearChatButton(
            self, self._clear_all_chat, self.chat_area
        )
        header_layout = QHBoxLayout()
        header_layout.addWidget(self.clear_chat_button)
        header_layout.addStretch(1)
        self.min_btn = QPushButton("–", self)
        self.min_btn.setFixedSize(36, 32)
        self.min_btn.clicked.connect(self.hide)
        self.min_btn.setStyleSheet(f"""
            QPushButton {{
                color: {qss(PRIMARY_COLOR, 77)};
                border: none;
                font-size: 24px;
                font-weight: bold;
                padding-bottom: 3px;
                text-align: center;
            }}
            QPushButton:hover {{
                background-color: {qss(PRIMARY_COLOR, 128)};
                color: rgba(0, 0, 0, 153);
                border-radius: 0px;
                margin-top: 1px;
            }}
        """)
        self.close_btn = QPushButton("×", self)
        self.close_btn.setFixedSize(36, 32)
        self.close_btn.clicked.connect(self.quit_app)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
            color: {qss(PRIMARY_COLOR, 77)};
                border: none;
                font-size: 24px;
                font-weight: bold;
                padding-bottom: 3px;
                text-align: center;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 77, 69, 128);
                color: rgba(0, 0, 0, 153);
                border-radius: 0px;
                border-top-right-radius: 7px;
                margin-top: 1px;
                margin-right: 1px;
            }}
        """)
        header_layout.addWidget(self.min_btn)
        header_layout.addWidget(self.close_btn)
        main_layout.addLayout(header_layout)

        # Add chat area
        main_layout.addWidget(self.chat_area, stretch=1)

        # Add input field
        self.input_field.message_sent.connect(self.send_message)
        self.input_field.height_changed.connect(self._on_input_height_changed)
        main_layout.addWidget(self.input_field)

        # Position the floating screenshot tray above the input field
        self.screenshot_tray.raise_()
        self.screenshot_tray.visibility_changed.connect(self._position_screenshot_tray)

        # Unset cursor for all child widgets to preserve system cursor
        self._unset_cursor_recursive(self)

        self.show()

        # Set display affinity to exclude main window from screen capture (Windows 10+)
        hwnd = int(self.winId())
        WDA_EXCLUDEFROMCAPTURE = 0x00000011
        result = ctypes.windll.user32.SetWindowDisplayAffinity(
            hwnd, WDA_EXCLUDEFROMCAPTURE
        )
        if result == 0:
            print(
                "Warning: SetWindowDisplayAffinity failed. May appear in screenshots."
            )

        # Setup timer to raise main window so it is always visible (certain Windows operations override the stay on top hint)
        self.visibility_timer = QTimer(self)
        self.visibility_timer.setInterval(1000)
        self.visibility_timer.timeout.connect(self._ensure_window_visible)
        self.visibility_timer.start()

    def _clear_all_chat(self) -> None:
        """Clear all chat data, screenshots, and screenshot tray thumbnails."""
        self.worker.stop()
        self.chat_area.clear_chat_messages()
        self.ai_sender.reset_chat()
        self.screenshot_manager.clear_screenshots()
        self.screenshot_tray.clear()

    def _position_screenshot_tray(self) -> None:
        """Place the screenshot tray above the input field."""
        tray = self.screenshot_tray
        tray_h = tray.height()
        tray.setGeometry(
            0,
            self.input_field.y() - tray_h,
            self.width(),
            tray_h,
        )

    # Set cursor as default texture regardless of where it is hovering on the main window
    def _unset_cursor_recursive(self, widget: QWidget) -> None:
        """Recursively unset cursor for a widget and all its children.

        Args:
            widget (QWidget): The widget to unset the cursor for.
        """
        widget.setAttribute(Qt.WidgetAttribute.WA_SetCursor, False)
        widget.unsetCursor()
        for child in widget.findChildren(QWidget):
            child.setAttribute(Qt.WidgetAttribute.WA_SetCursor, False)
            child.unsetCursor()

    def _on_input_height_changed(self, delta_height: int) -> None:
        """Resize the window downward when the input field height changes.

        Args:
            delta_height (int): The change in height of the input field in pixels.
        """
        self.resize(self.width(), self.height() + delta_height)

    def _ensure_window_visible(self) -> None:
        """Raise the main window if it is no longer the topmost window."""
        try:
            if not self._is_topmost_window():
                self.raise_()
        except Exception:
            pass

    def _is_topmost_window(self) -> bool:
        """Check if the main window is the topmost window at its corner positions.

        Returns:
            bool: True if the main window is topmost at all sampled points.
        """
        try:
            rect = self.frameGeometry()
            assert self.primary_screen is not None
            scale = self.primary_screen.devicePixelRatio()
            ga_root = 2
            self_hwnd = int(self.winId())
            self_root = ctypes.windll.user32.GetAncestor(
                wintypes.HWND(self_hwnd), ga_root
            )
            padding = 15
            corners = [
                rect.topLeft() + QPoint(padding, padding),
                rect.topRight() + QPoint(-padding, padding),
                rect.bottomLeft() + QPoint(padding, -padding),
                rect.bottomRight() + QPoint(-padding, -padding),
            ]
            for corner in corners:
                pt = wintypes.POINT(int(corner.x() * scale), int(corner.y() * scale))
                hwnd_at_pt = ctypes.windll.user32.WindowFromPoint(pt)
                if hwnd_at_pt:
                    target_root = ctypes.windll.user32.GetAncestor(
                        wintypes.HWND(hwnd_at_pt), ga_root
                    )
                    if int(self_root) != int(target_root):
                        return False
            return True
        except Exception:
            return True
