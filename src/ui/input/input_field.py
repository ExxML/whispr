from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QTextEdit, QVBoxLayout, QWidget

from ui.input.input_settings import InputSettings


class InputField(QWidget):
    """Render the input bar and message field."""

    message_sent = pyqtSignal(str)
    model_changed = pyqtSignal(str)
    thinking_mode_changed = pyqtSignal(bool)
    height_changed = pyqtSignal(int)

    def __init__(self, main_window: QWidget) -> None:
        super().__init__(main_window)
        self._init_UI()

    def _init_UI(self) -> None:
        """Initialize the input field UI layout and resizable text field."""
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(0)

        # Grey rounded container that holds both the text edit and the settings row
        self.input_container = QWidget()
        self.input_container.setObjectName("inputContainer")
        self.input_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.input_container.setStyleSheet("""
            QWidget#inputContainer {
                background-color: transparent;
                border: 1px solid rgba(255, 255, 255, 128);
                border-radius: 14px;
            }
        """)

        input_container_layout = QVBoxLayout(self.input_container)
        input_container_layout.setContentsMargins(
            8, 8, 8, 5
        )  # Smaller bottom margin due to vertically centered InputSettings row
        input_container_layout.setSpacing(0)

        self.input_field = _AutoResizeTextEdit()
        self.input_field.setPlaceholderText("How can I help you?")
        self.input_field.height_changed.connect(
            lambda delta: QTimer.singleShot(
                0, lambda d=delta: self.height_changed.emit(d)
            )
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
                padding: 2px 6px 2px 6px;  /* top, right, bottom, left */
            }
        """)
        scrollbar = self.input_field.verticalScrollBar()
        assert scrollbar is not None
        scrollbar.setStyleSheet("""
            QScrollBar:vertical {
                background-color: transparent;
                width: 4px;
                margin: 2px 0px 2px 0px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(255, 255, 255, 102);
                border-radius: 2px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgba(255, 255, 255, 128);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                border: none;
                background: transparent;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)

        self.input_settings = InputSettings(self.input_container)
        self.input_settings.model_changed.connect(self.model_changed)
        self.input_settings.thinking_mode_changed.connect(self.thinking_mode_changed)
        self.height_changed.connect(self.input_settings.model_dropdown.reposition_popup)

        input_container_layout.addWidget(self.input_field)
        input_container_layout.addWidget(self.input_settings)

        root_layout.addWidget(self.input_container)

    def _send_message(self) -> None:
        """Send the current message and clear the input field."""
        message = self.input_field.toPlainText().strip()
        if message:
            self.input_settings.model_dropdown.close_popup()
            self.message_sent.emit(message)
            self.input_field.clear()
            self.input_field.setFocus()

    def _set_enabled(self, enabled: bool) -> None:
        """Enable or disable the input field.

        Args:
            enabled (bool): Whether the input field should accept user input.
        """
        self.input_field.setEnabled(enabled)


class _AutoResizeTextEdit(QTextEdit):
    """Resize a text edit automatically to fit its content."""

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
        """Send the message on Enter and insert a newline on Shift+Enter.

        Args:
            event (QKeyEvent): The key event being handled.
        """
        if (
            event is not None
            and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            self.send_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

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
