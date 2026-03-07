from PyQt6.QtCore import QRect, Qt, pyqtSignal
from PyQt6.QtGui import QFontMetrics, QPainter, QPaintEvent
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QStyle, QStyleOptionComboBox, QWidget

from core.ai_sender import DEFAULT_MODEL, MODELS


class InputSettings(QWidget):
    """Settings row displayed below the message input field."""

    model_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.model_dropdown = _ModelDropdown()
        self._init_UI()

    def _init_UI(self) -> None:
        """Initialize the settings row layout with the model selector dropdown."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.model_dropdown.model_changed.connect(self.model_changed)

        layout.addStretch()
        layout.addWidget(self.model_dropdown)


class _ModelDropdown(QComboBox):
    """Dropdown for selecting the active Gemini model."""

    model_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._init_UI()

    def _init_UI(self) -> None:
        """Populate the dropdown with available models and apply styling."""
        self.setStyleSheet("""
            QComboBox {
                background-color: transparent;
                color: rgba(255, 255, 255, 128);
                border: none;
                font-size: 12px;
                padding: 4px 4px;
            }
            QComboBox::drop-down {
                border: none;
                width: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: rgba(20, 20, 20, 153);
                color: rgba(255, 255, 255, 128);
                border: 1px solid rgba(255, 255, 255, 50);
                outline: 0;
            }
            QComboBox QAbstractItemView::item {
                padding: 6px 8px;
                outline: 0;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: transparent;
                color: rgba(255, 255, 255, 255);
                border: none;
                outline: 0;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: transparent;
                color: rgba(255, 255, 255, 255);
                border: none;
                outline: 0;
            }
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        for display_name, model_id in MODELS:
            self.addItem(display_name, model_id)

        fm = QFontMetrics(self.font())
        max_width = max(fm.horizontalAdvance(display_name) for display_name, _ in MODELS)
        self.setFixedWidth(max_width + 25)  # Additional padding to avoid text truncation

        default_index = self.findData(DEFAULT_MODEL)
        if default_index >= 0:
            self.setCurrentIndex(default_index)

        self.currentIndexChanged.connect(self._on_model_changed)

    def _on_model_changed(self, _index: int) -> None:
        """Emit the selected model ID when the user changes the selection."""
        model_id = self.currentData()
        if isinstance(model_id, str):
            self.model_changed.emit(model_id)

    def paintEvent(self, _event: QPaintEvent | None) -> None:
        """Draw the combo box with right-aligned text."""
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)

        painter = QPainter(self)
        self.style().drawComplexControl(QStyle.ComplexControl.CC_ComboBox, opt, painter, self)

        text_rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            opt,
            QStyle.SubControl.SC_ComboBoxEditField,
            self,
        )
        painter.setPen(opt.palette.color(opt.palette.currentColorGroup(), opt.palette.ColorRole.Text))
        painter.setFont(self.font())
        painter.drawText(QRect(text_rect), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self.currentText())
        painter.end()
