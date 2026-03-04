from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QTextEdit, QVBoxLayout, QWidget


class InputField(QWidget):
    """Input bar with a text field."""

    message_sent = pyqtSignal(str)
    height_changed = pyqtSignal(int)
    _return_pressed = pyqtSignal()

    def __init__(self, main_window: QWidget) -> None:
        super().__init__(main_window)
        self._init_UI()

    def _init_UI(self) -> None:
        """Initialize the input field UI layout and resizable text field."""
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(12, 12, 12, 12)
        input_row.setSpacing(8)

        self.input_field = _AutoResizeTextEdit()
        self.input_field.setPlaceholderText("How can I help you?")
        self.input_field.height_changed.connect(self.height_changed)
        self._return_pressed.connect(self._send_message)

        font = QFont("Microsoft JhengHei", 10)
        self.input_field.setFont(font)

        # Style the input field
        self.input_field.setStyleSheet("""
            QTextEdit {
                background-color: rgba(255, 255, 255, 0.2);
                color: rgba(255, 255, 255, 1.0);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 14px;
                padding: 2px 6px;
            }
            QTextEdit:focus {
                border: 1px solid rgba(255, 255, 255, 0.8);
            }
            QScrollBar:vertical {
                width: 4px;
                margin: 2px 0px 2px 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.4);
            }
        """)

        input_row.addWidget(self.input_field)
        outer_layout.addLayout(input_row)

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        """Handle key press events, emitting _return_pressed on unmodified Enter."""
        if (
            event is not None
            and event.key() == Qt.Key.Key_Return
            and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self._return_pressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def _send_message(self) -> None:
        """Send the current message and clear the input field."""
        message = self.input_field.toPlainText().strip()
        if message:
            self.message_sent.emit(message)
            self.input_field.clear()
            self.input_field.setFocus()

    def _set_enabled(self, enabled: bool) -> None:
        """Enable or disable the input field."""
        self.input_field.setEnabled(enabled)


class _AutoResizeTextEdit(QTextEdit):
    """A QTextEdit that automatically resizes its height to fit its content."""

    height_changed = pyqtSignal(int)

    MAX_LINES = 10

    def __init__(self) -> None:
        super().__init__()
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        doc = self.document()
        assert doc is not None
        doc.contentsChanged.connect(self._adjust_height)
        QTimer.singleShot(0, self._adjust_height)

    def _adjust_height(self) -> None:
        """Adjust height based on document content, capped at MAX_LINES."""
        font_metrics = self.fontMetrics()
        line_height = font_metrics.lineSpacing()
        max_height = line_height * self.MAX_LINES

        doc = self.document()
        assert doc is not None
        doc_height = doc.size().height()
        margins = self.contentsMargins().top() + self.contentsMargins().bottom()
        desired_height = int(doc_height + margins)
        new_height = (
            max_height + margins if desired_height > max_height else desired_height
        )

        self.setFixedHeight(new_height)
        QTimer.singleShot(0, lambda: self.height_changed.emit(new_height))
