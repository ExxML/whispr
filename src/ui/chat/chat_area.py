from math import exp

from PyQt6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
)
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPixmap, QWheelEvent
from PyQt6.QtWidgets import QGraphicsEffect, QScrollArea, QVBoxLayout, QWidget

from ui.chat.chat_bubble import ChatBubble


class ChatArea(QScrollArea):
    """Display message history in a scrollable chat area."""

    def __init__(self, main_window: QWidget) -> None:
        super().__init__(main_window)
        self.streaming_bubble: ChatBubble | None = None
        self.streaming_text: str = ""
        self._init_UI()
        self._init_scroll_animation()
        self._reset_stream()

    def add_message(self, message: str, is_user: bool) -> None:
        """Add a new message to the chat area.

        Args:
            message (str): The message text to display.
            is_user (bool): Whether the message is from the user.
        """
        # Remove the stretch before adding new message
        self.chat_layout.takeAt(self.chat_layout.count() - 1)

        # Create and add the chat bubble
        bubble = ChatBubble(message, is_user)
        self.chat_layout.addWidget(bubble)

        # Pre-create the assistant loading bubble so it is visible when the chat scrolls down
        if is_user:
            self.streaming_bubble = ChatBubble("", is_user=False)
            self.streaming_text = ""
            self.chat_layout.addWidget(self.streaming_bubble)
            self.streaming_bubble.start_loading_animation()

        # Add stretch back at the end
        self.chat_layout.addStretch()

        # Force scroll to bottom after a delay
        if is_user:
            sb = self.scrollbar
            QTimer.singleShot(400, lambda: self._animate_to(sb.maximum(), 100))

    def start_assistant_stream(self) -> None:
        """Create an assistant bubble to stream content into (not saved until finalized)."""
        if self.streaming_bubble is not None:
            return
        # Remove stretch, add empty assistant bubble, then add stretch back
        self.chat_layout.takeAt(self.chat_layout.count() - 1)
        self.streaming_bubble = ChatBubble("", is_user=False)
        self.streaming_text = ""
        self.chat_layout.addWidget(self.streaming_bubble)
        self.chat_layout.addStretch()

    def append_to_stream(self, chunk_text: str) -> None:
        """Append text to the current streaming assistant bubble.

        Args:
            chunk_text (str): The text chunk to append to the stream.
        """
        if self.streaming_bubble is None:
            return
        if not self.streaming_text:
            self.streaming_bubble.stop_loading_animation()
        self.streaming_text += chunk_text
        self.streaming_bubble.set_bot_message(self.streaming_text)

    def finalize_assistant_stream(self) -> None:
        """Finalize the streamed assistant message and clear streaming state."""
        if self.streaming_bubble is None:
            return
        self.streaming_bubble.stop_loading_animation()
        self._reset_stream()

    def show_stream_error(self, error_msg: str) -> None:
        """Display an error message in the current streaming bubble, replacing the loading indicator.

        If no streaming bubble exists, falls back to adding a new bot message.

        Args:
            error_msg (str): The error text to display.
        """
        if self.streaming_bubble is None:
            self.add_message(error_msg, is_user=False)
            return
        self.streaming_bubble.stop_loading_animation()
        self.streaming_bubble.set_bot_message(error_msg)
        self._reset_stream()

    def clear_chat_messages(self) -> None:
        """Clear all messages from the chat area."""
        # Reset streaming state before deleting widgets to avoid dangling references
        self._reset_stream()

        # Remove all widgets except the stretch
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

    def shortcut_scroll(self, amount: int) -> None:
        """Scroll the chat area by a specified amount.

        Args:
            amount (int): The pixel amount to scroll (positive for down, negative for up).
        """
        target = self.scrollbar.value() + amount
        duration = 100
        self._animate_to(target, duration)

    def _init_UI(self) -> None:
        """Initialize the chat area UI layout, scroll settings, and styling."""
        # Configure scroll area
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        # Create container widget for messages
        self.chat_container = QWidget()
        self.chat_container.setStyleSheet("background-color: transparent;")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(3, 3, 3, 3)
        self.chat_layout.addStretch()

        # Set the container as the scroll area's widget
        self.setWidget(self.chat_container)

        scrollbar = self.verticalScrollBar()
        assert scrollbar is not None
        self.scrollbar = scrollbar

        # Style the scroll area
        self.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: rgba(0, 0, 0, 0);
                width: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(255, 255, 255, 77);
                border-radius: 2px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgba(255, 255, 255, 128);
            }
            QScrollBar::handle:vertical:disabled {
                background-color: transparent;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

        # Apply fade effect to the top and bottom edges of the viewport
        viewport = self.viewport()
        assert viewport is not None
        self.fade_effect = _FadeOverlay()
        viewport.setGraphicsEffect(self.fade_effect)

        # Connect scroll signals for position-aware fading.
        # Defer via singleShot(0) so the scrollbar value is read after Qt has
        # finished applying all pending layout/range adjustments.
        self.scrollbar.valueChanged.connect(
            lambda _val: QTimer.singleShot(0, self._update_fade_visibility)
        )
        self.scrollbar.rangeChanged.connect(
            lambda _min, _max: QTimer.singleShot(0, self._update_fade_visibility)
        )

    def _update_fade_visibility(self) -> None:
        """Scale each fade edge based on distance from the nearest scroll edge."""
        sb = self.scrollbar
        fade_start = self.fade_effect.FADE_START_DIST
        top_dist = sb.value() - sb.minimum()
        bottom_dist = sb.maximum() - sb.value()
        self.fade_effect.top_strength = min(1.0, max(0.0, top_dist / fade_start))
        self.fade_effect.bottom_strength = min(1.0, max(0.0, bottom_dist / fade_start))
        self.fade_effect.update()

    def _reset_stream(self) -> None:
        """Reset the streaming bubble and accumulated text to a blank state."""
        self.streaming_bubble = None
        self.streaming_text = ""

    def _init_scroll_animation(self) -> None:
        """Initialize smooth scrolling animation."""
        self.scroll_animation = QPropertyAnimation(self.scrollbar, b"value", self)
        self.scroll_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.scroll_target: int = 0

    def wheelEvent(self, event: QWheelEvent | None) -> None:
        """Handle mouse wheel events with smooth animated scrolling.

        Accumulates the running animation target so rapid wheel spins
        chain naturally instead of restarting from the current position.

        Args:
            event (QWheelEvent): The wheel event that drives the scroll delta.
        """
        if event is None:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return
        # Scale factor: 120 units per standard notch → ~80 px per notch.
        step = round(-delta * 2 / 3)
        if step == 0:
            event.accept()
            return
        anim = self.scroll_animation
        base = (
            self.scroll_target
            if anim.state() == QAbstractAnimation.State.Running
            else self.scrollbar.value()
        )
        sb = self.scrollbar
        self.scroll_target = max(sb.minimum(), min(base + step, sb.maximum()))
        self._animate_to(self.scroll_target, 150)
        event.accept()

    def _animate_to(self, target: int, duration: int) -> None:
        """Animate scrollbar to target position.

        Args:
            target (int): The target scroll position.
            duration (int): The animation duration in milliseconds.
        """
        anim = self.scroll_animation
        if anim.state() == QAbstractAnimation.State.Running:
            anim.stop()
        sb = self.scrollbar
        target = max(sb.minimum(), min(target, sb.maximum()))
        anim.setTargetObject(sb)
        anim.setStartValue(sb.value())
        anim.setEndValue(target)
        anim.setDuration(duration)
        anim.start()


class _FadeOverlay(QGraphicsEffect):
    """Fade the top and bottom edges of a widget to transparent."""

    FADE_HEIGHT = 30
    FADE_START_DIST = FADE_HEIGHT // 2
    FADE_STEPS = 10
    FADE_EXPONENT = 2.5

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.top_strength = 0.0
        self.bottom_strength = 0.0

    def _set_exponential_stops(
        self, gradient: QLinearGradient, *, edge_at_start: bool, strength: float
    ) -> None:
        """Populate gradient stops every 0.1 with exponential edge fade."""
        scale = exp(self.FADE_EXPONENT) - 1.0

        for step in range(self.FADE_STEPS + 1):
            position = step / self.FADE_STEPS
            distance = position if edge_at_start else 1.0 - position
            full_fade_alpha = round(
                255 * ((exp(self.FADE_EXPONENT * distance) - 1.0) / scale)
            )
            alpha = round(255 - strength * (255 - full_fade_alpha))
            gradient.setColorAt(position, QColor(0, 0, 0, alpha))

    def draw(self, painter: QPainter | None) -> None:
        """Draw the source widget with faded top and bottom edges.

        Args:
            painter (QPainter): The painter used to render the effect output.
        """
        if painter is None:
            return

        result: tuple[QPixmap, QPoint | None] = self.sourcePixmap(
            Qt.CoordinateSystem.LogicalCoordinates
        )
        pixmap, offset = result

        if pixmap.isNull() or offset is None:
            return

        # QPainter on a high-DPR pixmap operates in logical coordinates, so
        # we must derive logical dimensions from the raw pixel size.
        dpr = pixmap.devicePixelRatio()
        height = pixmap.height() / dpr
        width = pixmap.width() / dpr
        fade_px = float(self.FADE_HEIGHT)

        if height > 2 * fade_px:
            fade_painter = QPainter(pixmap)
            fade_painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_DestinationIn
            )

            if self.top_strength > 0.0:
                top_gradient = QLinearGradient(0, 0, 0, fade_px)
                self._set_exponential_stops(
                    top_gradient,
                    edge_at_start=True,
                    strength=self.top_strength,
                )
                fade_painter.fillRect(QRectF(0, 0, width, fade_px), top_gradient)

            if self.bottom_strength > 0.0:
                bottom_gradient = QLinearGradient(0, height - fade_px, 0, height)
                self._set_exponential_stops(
                    bottom_gradient,
                    edge_at_start=False,
                    strength=self.bottom_strength,
                )
                fade_painter.fillRect(
                    QRectF(0, height - fade_px, width, fade_px),
                    bottom_gradient,
                )

            fade_painter.end()

        painter.drawPixmap(offset, pixmap)
