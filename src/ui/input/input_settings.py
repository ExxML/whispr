from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QWidget

from ui.input.model_dropdown import ModelDropdown


class InputSettings(QWidget):
    """Settings row displayed below the message input field."""

    model_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.model_dropdown = ModelDropdown()
        self._init_UI()

    def _init_UI(self) -> None:
        """Initialize the settings row layout with the model selector dropdown."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.model_dropdown.model_changed.connect(self.model_changed)

        layout.addStretch()
        layout.addWidget(self.model_dropdown)
