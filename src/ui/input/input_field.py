from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFocusEvent, QFont, QKeyEvent
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QTextEdit, QVBoxLayout, QWidget

from ui.input.input_settings import InputSettings


class InputField(QWidget):
    """Input bar with a text field."""

    message_sent = pyqtSignal(str)
    model_changed = pyqtSignal(str)
    height_changed = pyqtSignal(int)

    CONTAINER_STYLE = """
        QWidget {
            background-color: transparent;
            border: 1px solid rgba(255, 255, 255, 128);
            border-radius: 14px;
        }
    """
    CONTAINER_FOCUS_STYLE = """
        QWidget {
            background-color: transparent;
            border: 1px solid rgba(255, 255, 255, 179);
            border-radius: 14px;
        }
    """

    def __init__(self, main_window: QWidget) -> None:
        super().__init__(main_window)
        self._init_UI()

    def _init_UI(self) -> None:
        """Initialize the input field UI layout and resizable text field."""
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        outer_row = QHBoxLayout()
        outer_row.setContentsMargins(12, 12, 12, 12)
        outer_row.setSpacing(0)

        # Grey rounded container that holds both the text edit and the settings row
        self.input_container = QWidget()
        self.input_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.input_container.setStyleSheet(self.CONTAINER_STYLE)

        container_layout = QVBoxLayout(self.input_container)
        container_layout.setContentsMargins(8, 8, 8, 6)
        container_layout.setSpacing(0)

        self.input_field = _AutoResizeTextEdit()
        self.input_field.setPlaceholderText("How can I help you?")
        self.input_field.height_changed.connect(
            lambda delta: QTimer.singleShot(
                0, lambda d=delta: self.height_changed.emit(d)
            )
        )
        self.input_field.focus_in.connect(
            lambda: self.input_container.setStyleSheet(self.CONTAINER_FOCUS_STYLE)
        )
        self.input_field.focus_out.connect(
            lambda: self.input_container.setStyleSheet(self.CONTAINER_STYLE)
        )
        self.input_field.send_requested.connect(self._send_message)

        font = QFont("Microsoft JhengHei", 10)
        self.input_field.setFont(font)

        # Text edit is transparent; the container provides the visual frame
        self.input_field.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                color: rgba(255, 255, 255, 255);
                border: none;
                padding: 2px 6px;
            }
            QScrollBar:vertical {
                width: 4px;
                margin: 2px 0px 2px 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 102);
            }
        """)

        self.settings = InputSettings(self.input_container)
        self.settings.model_changed.connect(self.model_changed)

        container_layout.addWidget(self.input_field)
        container_layout.addWidget(self.settings)

        outer_row.addWidget(self.input_container)
        outer_layout.addLayout(outer_row)

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

    focus_in = pyqtSignal()
    focus_out = pyqtSignal()
    height_changed = pyqtSignal(int)
    send_requested = pyqtSignal()

    MAX_LINES = 10

    def __init__(self) -> None:
        super().__init__()
        self._prev_height: int = 0
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        doc = self.document()
        assert doc is not None
        doc.contentsChanged.connect(self._adjust_height)
        QTimer.singleShot(0, self._adjust_height)

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        """Send on plain Enter; insert newline on Shift+Enter."""
        if (
            event is not None
            and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self.send_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event: QFocusEvent | None) -> None:
        """Emit focus_in when the widget gains keyboard focus."""
        super().focusInEvent(event)
        self.focus_in.emit()

    def focusOutEvent(self, event: QFocusEvent | None) -> None:
        """Emit focus_out when the widget loses keyboard focus."""
        super().focusOutEvent(event)
        self.focus_out.emit()

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
        if self._prev_height != 0:
            delta = new_height - self._prev_height
            if delta != 0:
                QTimer.singleShot(0, lambda d=delta: self.height_changed.emit(d))
        self._prev_height = new_height
