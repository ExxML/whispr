from PyQt6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PyQt6.QtGui import QColor, QLinearGradient, QPainter
from PyQt6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from ui.chat_bubble import ChatBubble

FADE_HEIGHT = 20


class ChatArea(QScrollArea):
    """Scrollable chat area for displaying message history."""

    def __init__(self, main_window: QWidget, bg_color: QColor) -> None:
        super().__init__(main_window)
        self.bg_color = bg_color
        self._init_UI()
        self._init_scroll_animation()
        self._reset_stream()

    def resizeEvent(self, _event) -> None:
        """Position the fade overlays at the top and bottom of the viewport."""
        super().resizeEvent(_event)
        vp = self.viewport().geometry()
        # Inset by 2px on each side to avoid the 1px window border
        x = vp.x() + 2
        w = max(0, vp.width() - 4)
        self._top_fade.setGeometry(x, vp.y(), w, FADE_HEIGHT)
        self._bottom_fade.setGeometry(
            x, vp.y() + vp.height() - FADE_HEIGHT, w, FADE_HEIGHT
        )
        self._top_fade.raise_()
        self._bottom_fade.raise_()

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
            QTimer.singleShot(
                400, lambda: self._animate_to(self.verticalScrollBar().maximum(), 100)
            )

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

    def clear_chat(self) -> None:
        """Clear all messages from the chat area."""
        # Remove all widgets except the stretch
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def shortcut_scroll(self, amount: int) -> None:
        """Scroll the chat area by a specified amount.

        Args:
            amount (int): The pixel amount to scroll (positive for down, negative for up).
        """
        scrollbar = self.verticalScrollBar()
        target = scrollbar.value() + amount
        duration = 100
        self._animate_to(target, duration)

    def _init_UI(self) -> None:
        """Initialize the chat area UI layout, scroll settings, and styling."""
        # Configure scroll area
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Create container widget for messages
        self.chat_container = QWidget()
        self.chat_container.setStyleSheet("background-color: transparent;")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(3, 3, 3, 3)
        self.chat_layout.addStretch()

        # Set the container as the scroll area's widget
        self.setWidget(self.chat_container)

        # Create fade overlays (positioned in resizeEvent)
        self._top_fade = _FadeOverlay(self, is_top=True)
        self._bottom_fade = _FadeOverlay(self, is_top=False)
        self._top_fade.hide()
        self._bottom_fade.hide()

        # Update fade visibility on scroll
        sb = self.verticalScrollBar()
        sb.valueChanged.connect(self._update_fades)
        sb.rangeChanged.connect(self._update_fades)

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
                background-color: rgba(255, 255, 255, 0.3);
                border-radius: 2px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgba(255, 255, 255, 0.5);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

    def _reset_stream(self) -> None:
        """Reset the streaming bubble and accumulated text to a blank state."""
        self.streaming_bubble = None
        self.streaming_text = ""

    def _init_scroll_animation(self) -> None:
        """Initialize smooth scrolling animation."""
        self.scroll_animation = QPropertyAnimation(
            self.verticalScrollBar(), b"value", self
        )
        self.scroll_animation.setEasingCurve(QEasingCurve.Type.OutQuad)

    def _update_fades(self) -> None:
        """Show or hide fade overlays based on scroll position."""
        sb = self.verticalScrollBar()
        self._top_fade.setVisible(sb.value() > sb.minimum())
        self._bottom_fade.setVisible(sb.value() < sb.maximum())

    def _animate_to(self, target: int, duration: int) -> None:
        """Animate scrollbar to target position.

        Args:
            target (int): The target scroll position.
            duration (int): The animation duration in milliseconds.
        """
        anim = self.scroll_animation
        if anim.state() == QAbstractAnimation.State.Running:
            anim.stop()
        sb = self.verticalScrollBar()
        target = max(sb.minimum(), min(target, sb.maximum()))
        anim.setTargetObject(sb)
        anim.setStartValue(sb.value())
        anim.setEndValue(target)
        anim.setDuration(duration)
        anim.start()


class _FadeOverlay(QWidget):
    """Overlay widget that fades content into the window background color.

    Paints a vertical gradient from transparent to the window background color
    so that text near the edges blends smoothly into the background.
    """

    def __init__(self, chat_area: ChatArea, is_top: bool) -> None:
        super().__init__(chat_area)
        self.bg_color = chat_area.bg_color
        self._is_top = is_top
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, _event) -> None:
        """Paint a gradient from transparent to the window background color."""
        p = QPainter(self)
        h = self.height()
        gradient = QLinearGradient(0, 0, 0, h)
        transparent = QColor(self.bg_color)
        transparent.setAlpha(0)
        if self._is_top:
            gradient.setColorAt(0.0, self.bg_color)
            gradient.setColorAt(1.0, transparent)
        else:
            gradient.setColorAt(0.0, transparent)
            gradient.setColorAt(1.0, self.bg_color)
        p.fillRect(self.rect(), gradient)
