from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPaintEvent, QPen, QPixmap
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from core.screenshot_manager import ScreenshotManager


PREVIEW_WIDTH = 80
PREVIEW_HEIGHT = 45
BTN_SIZE = 16
BTN_OVERHANG = BTN_SIZE // 2  # X button slightly protrudes beyond the edge of the image


class ScreenshotThumbnail(QWidget):
    """Small preview thumbnail of a pending screenshot with a remove button."""

    removed = pyqtSignal(str)

    def __init__(self, path: str, screenshot_tray: QWidget) -> None:
        super().__init__(screenshot_tray)
        self.path = path
        # Extra BTN_OVERHANG pixels on top and right let the X button protrude outside the image
        self.setFixedSize(PREVIEW_WIDTH + BTN_OVERHANG, PREVIEW_HEIGHT + BTN_OVERHANG)

        # Load and scale the image to fill the thumbnail dimensions
        src = QPixmap(path)
        self.pixmap = src.scaled(
            PREVIEW_WIDTH,
            PREVIEW_HEIGHT,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        ).copy(0, 0, PREVIEW_WIDTH, PREVIEW_HEIGHT)

        # Remove attachment button in the top-right corner of the image with some overhang
        self.remove_btn = QPushButton("×", self)
        self.remove_btn.setFixedSize(BTN_SIZE, BTN_SIZE)
        self.remove_btn.move(PREVIEW_WIDTH - BTN_OVERHANG - 3, 3)
        self.remove_btn.clicked.connect(lambda: self.removed.emit(self.path))
        self.remove_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(20, 20, 20, 153);
                color: rgba(255, 255, 255, 230);
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                padding-bottom: 3px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 153);
                color: rgba(20, 20, 20, 230);
            }
        """)

    def paintEvent(self, _event: QPaintEvent | None) -> None:
        """Draw the thumbnail image clipped to rounded corners with a subtle border."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Image occupies the lower-left PREVIEW_WIDTH × PREVIEW_HEIGHT area; the top/right margins are for the button overhang
        clip = QPainterPath()
        clip.addRoundedRect(
            0.0,
            float(BTN_OVERHANG),
            float(PREVIEW_WIDTH),
            float(PREVIEW_HEIGHT),
            6.0,
            6.0,
        )
        painter.setClipPath(clip)
        painter.drawPixmap(0, BTN_OVERHANG, self.pixmap)

        painter.setClipping(False)
        painter.setPen(QPen(QColor(255, 255, 255, 60), 1.0))
        painter.drawRoundedRect(
            QRectF(0.5, BTN_OVERHANG + 0.5, PREVIEW_WIDTH - 1.0, PREVIEW_HEIGHT - 1.0),
            6.0,
            6.0,
        )


class ScreenshotTray(QWidget):
    """Horizontal tray that displays pending screenshot thumbnails above the input field."""

    visibility_changed = pyqtSignal()

    def __init__(
        self, screenshot_manager: ScreenshotManager, main_window: QWidget
    ) -> None:
        super().__init__(main_window)
        self.screenshot_manager = screenshot_manager

        # Transparent background so the chat text behind the tray remains readable
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.tray_layout = QHBoxLayout(self)
        self.tray_layout.setContentsMargins(
            12, 0, 12, 0
        )  # Extra right margin to avoid the scroll bar
        self.tray_layout.setSpacing(6)
        self.tray_layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        # Height includes the overhang area so thumbnails are not clipped
        self.setFixedHeight(PREVIEW_HEIGHT + BTN_OVERHANG + 6)
        self.setVisible(False)

        screenshot_manager.screenshot_added.connect(self._add_thumbnail)

    def clear(self) -> None:
        """Remove all thumbnails and hide the tray."""
        while self.tray_layout.count():
            item = self.tray_layout.takeAt(0)
            widget = item.widget() if item else None
            if widget:
                widget.deleteLater()
        self.setVisible(False)
        self.visibility_changed.emit()

    def _add_thumbnail(self, path: str) -> None:
        """Add a thumbnail for a newly captured screenshot.

        Args:
            path (str): The file path of the screenshot to display.
        """
        thumb = ScreenshotThumbnail(path, self)
        thumb.removed.connect(self._on_thumbnail_removed)
        self.tray_layout.addWidget(thumb)
        self.setVisible(True)
        self.visibility_changed.emit()

    def _on_thumbnail_removed(self, path: str) -> None:
        """Handle removal of a single thumbnail and detach its path from pending screenshots.

        Args:
            path (str): The file path of the screenshot being removed.
        """
        self.screenshot_manager.remove_pending(path)

        for i in range(self.tray_layout.count()):
            item = self.tray_layout.itemAt(i)
            widget = item.widget() if item else None
            if isinstance(widget, ScreenshotThumbnail) and widget.path == path:
                self.tray_layout.removeWidget(widget)
                widget.deleteLater()
                break

        if self.tray_layout.count() == 0:
            self.setVisible(False)
            self.visibility_changed.emit()
