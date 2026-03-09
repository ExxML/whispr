import os

from PyQt6.QtCore import QRect, QVariantAnimation, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFontMetrics,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPixmap,
)
from PyQt6.QtWidgets import QWidget


class ThinkingModeButton(QWidget):
    """Button to toggle AI thinking mode on/off.

    Renders the thinking_mode_button.png icon at the specified opacity. When active, a
    semi-transparent yellow circle fades in behind the icon to indicate thinking mode is enabled.
    """

    thinking_mode_changed = pyqtSignal(bool)

    ENABLED_OVERLAY_COLOR = QColor(255, 200, 0)
    DISABLED_OUTLINE_COLOR = QColor(255, 255, 255)
    ENABLED_ICON_OPACITY = 255 / 255
    DISABLED_ICON_OPACITY = 150 / 255

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._active = False
        self._overlay_opacity: float = 0.0

        self._animation = QVariantAnimation(self)
        self._animation.setDuration(100)
        self._animation.valueChanged.connect(self._on_animation_value)

        font = self.font()
        font.setPixelSize(10)
        fm = QFontMetrics(font)
        self._icon_size = fm.height()
        widget_size = round(
            self._icon_size * 1.5
        )  # Make the yellow circle larger without increasing the icon size
        self.setFixedSize(widget_size, widget_size)

        self.icon_path = os.path.join(
            os.getcwd(), "src", "assets", "thinking_mode_button.png"
        )
        self._pixmap = QPixmap(str(self.icon_path))

        self._pixmap_active = QPixmap(self._pixmap.size())
        self._pixmap_active.fill(Qt.GlobalColor.transparent)
        tint_painter = QPainter(self._pixmap_active)
        tint_painter.drawPixmap(0, 0, self._pixmap)
        tint_painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceIn
        )
        tint_painter.fillRect(self._pixmap_active.rect(), self.ENABLED_OVERLAY_COLOR)
        tint_painter.end()

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        """Toggle thinking mode and animate the overlay on click."""
        if event is None:
            return

        self._active = not self._active

        self._animation.stop()
        self._animation.setStartValue(self._overlay_opacity)
        self._animation.setEndValue(self.DISABLED_ICON_OPACITY if self._active else 0.0)
        self._animation.start()

        self.thinking_mode_changed.emit(self._active)

    def paintEvent(self, _event: QPaintEvent | None) -> None:
        """Draw the yellow circle overlay and the icon at 50% opacity."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Draw semi-transparent yellow circle overlay behind the icon
        if self._overlay_opacity > 0.0:
            overlay = QColor(self.ENABLED_OVERLAY_COLOR)
            overlay.setAlphaF(self._overlay_opacity)
            painter.save()
            painter.setBrush(overlay)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(self.rect().adjusted(1, 1, -1, -1))
            painter.restore()

        # Draw outline circle: yellow at icon opacity when active, white at icon opacity when inactive
        outline_color = (
            self.ENABLED_OVERLAY_COLOR if self._active else self.DISABLED_OUTLINE_COLOR
        )
        outline_opacity = (
            self.ENABLED_ICON_OPACITY if self._active else self.DISABLED_ICON_OPACITY
        )
        pen = painter.pen()
        pen.setColor(outline_color)
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setOpacity(outline_opacity)
        painter.drawEllipse(self.rect().adjusted(1, 1, -1, -1))

        # Draw the icon: yellow-tinted at full opacity when active, normal at 50% opacity otherwise
        x = (self.width() - self._icon_size) // 2
        y = (self.height() - self._icon_size) // 2
        target = QRect(x, y, self._icon_size, self._icon_size)
        if self._active:
            painter.setOpacity(self.ENABLED_ICON_OPACITY)
            painter.drawPixmap(target, self._pixmap_active, self._pixmap_active.rect())
        else:
            painter.setOpacity(self.DISABLED_ICON_OPACITY)
            painter.drawPixmap(target, self._pixmap, self._pixmap.rect())

        painter.end()

    def _on_animation_value(self, value: object) -> None:
        """Update the overlay opacity from the current animation frame.

        Args:
            value (object): The interpolated opacity value emitted by the animation.
        """
        if isinstance(value, float):
            self._overlay_opacity = value
            self.update()
