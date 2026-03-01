import math

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ui.ai_formatter import format_message


class ChatBubble(QWidget):
    """A chat bubble widget for displaying messages"""

    def __init__(self, message: str, is_user: bool = False) -> None:
        super().__init__()
        self.message = message
        self.is_user = is_user
        self._init_UI()

    def set_bot_message(self, message: str) -> None:
        """Format the bot message and set the text as the label.

        Args:
            message (str): The raw bot message text to format and display.
        """
        self.message = message
        self.message_label.setText(format_message(message))

    def start_loading_animation(self) -> None:
        """Start the animated three-dot loading indicator."""
        self._loading_frame = 0
        self._loading_timer = QTimer(self)
        self._loading_timer.timeout.connect(self._tick_loading)
        self._loading_timer.start(80)
        self._tick_loading()

    def stop_loading_animation(self) -> None:
        """Stop the loading animation and clean up the timer."""
        if hasattr(self, "_loading_timer") and self._loading_timer is not None:
            self._loading_timer.stop()
            self._loading_timer.deleteLater()
            self._loading_timer = None

    def _init_UI(self) -> None:
        """Initialize the chat bubble UI layout and styling."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        # Create message label with HTML formatting
        # Default formatting for user message only (bot message uses formatting in set_bot_message)
        html_message = f'<div style="line-height: 1.4; white-space: pre-wrap;">{self.message}</div>'
        self.message_label = QLabel(html_message)
        self.message_label.setTextFormat(Qt.TextFormat.RichText)
        self.message_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        # Set font
        font = QFont("Helvetica", 11)
        self.message_label.setFont(font)

        # Style the bubble based on sender
        if self.is_user:
            # User messages: light gray, aligned right
            self.message_label.setStyleSheet("""
                QLabel {
                    color: rgba(255, 255, 255, 1.0);
                    background-color: transparent;
                    border: 1px solid rgba(255, 255, 255, 1.0);
                    border-radius: 8px;
                    padding: 5px 4px -3px 5px;  /* top, right, bottom, left */
                }
            """)  # padding adjusted to visually center text within the bubble

            # Let Qt estimate the natural width of the message, then word wrap if necessary
            natural_width = self.message_label.sizeHint().width()
            max_width = 400

            if natural_width > max_width:
                self.message_label.setFixedWidth(max_width)
                self.message_label.setWordWrap(True)
            else:
                self.message_label.setFixedWidth(natural_width)

            layout.addStretch()
            layout.addWidget(self.message_label)
        else:
            # Bot messages: transparent, aligned left
            self.message_label.setStyleSheet("""
                QLabel {
                    color: rgba(255, 255, 255, 1.0);
                    background-color: transparent;
                    padding: 0px 0px 0px 1px;  /* top, right, bottom, left */
                }
            """)
            self.message_label.setWordWrap(True)
            self.message_label.setFixedWidth(515)
            layout.addWidget(self.message_label)
            layout.addStretch()

        layout.setSpacing(0)

    def _tick_loading(self) -> None:
        """Advance the loading animation by one frame."""
        t = self._loading_frame * (2 * math.pi / 20)  # 20 frames per cycle (~1.6 s)

        def dot_opacity(phase_offset: float) -> float:
            """Compute a smooth opacity value using a sine wave with a phase offset.

            Args:
                phase_offset (float): The phase offset in radians for this dot.

            Returns:
                float: Opacity in the range [0.1, 0.95].
            """
            return 0.1 + 0.85 * (math.sin(t + phase_offset) + 1) / 2

        o1 = dot_opacity(0)
        o2 = dot_opacity(2 * math.pi / 3)
        o3 = dot_opacity(4 * math.pi / 3)

        html = (
            f"<span style='color: rgba(255, 255, 255, {o1:.2f}); font-size: 16px;'>&#9679;</span>"
            f"&nbsp;"
            f"<span style='color: rgba(255, 255, 255, {o2:.2f}); font-size: 16px;'>&#9679;</span>"
            f"&nbsp;"
            f"<span style='color: rgba(255, 255, 255, {o3:.2f}); font-size: 16px;'>&#9679;</span>"
        )
        self.message_label.setText(html)
        self._loading_frame = (self._loading_frame + 1) % 20
