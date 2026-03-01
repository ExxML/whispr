from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QVBoxLayout, QWidget


class InputBar(QWidget):
    """Input bar with a text field."""

    # Signal emitted when a message is sent
    message_sent = pyqtSignal(str)

    def __init__(self, main_window: QWidget) -> None:
        super().__init__(main_window)
        self._init_UI()

    def _init_UI(self) -> None:
        """Initialize the input bar UI layout and text field."""
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Input row
        input_row = QHBoxLayout()
        input_row.setContentsMargins(12, 12, 12, 12)
        input_row.setSpacing(8)

        # Create text input field
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("How can I help you?")
        self.input_field.returnPressed.connect(self._send_message)

        # Set font
        font = QFont("Microsoft JhengHei", 10)
        self.input_field.setFont(font)
        self.input_field.setMinimumHeight(32)

        # Style the input field
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.2);
                color: rgba(255, 255, 255, 1.0);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 16px;
                padding: 6px 10px;
            }
            QLineEdit:focus {
                border: 1px solid rgba(255, 255, 255, 0.8);
            }
        """)

        input_row.addWidget(self.input_field)
        outer_layout.addLayout(input_row)

    def _send_message(self) -> None:
        """Send the current message and clear the input field."""
        message = self.input_field.text().strip()
        if message:
            self.message_sent.emit(message)
            self.input_field.clear()
            self.input_field.setFocus()

    def _set_enabled(self, enabled: bool) -> None:
        """Enable or disable the input bar.

        Args:
            enabled (bool): Whether the input bar should be enabled.
        """
        self.input_field.setEnabled(enabled)
