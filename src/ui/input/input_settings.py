from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QWidget

from ui.input.model_dropdown import ModelDropdown
from ui.input.thinking_mode_button import ThinkingModeButton


class InputSettings(QWidget):
    """Settings row displayed below the message input field."""

    model_changed = pyqtSignal(str)
    thinking_mode_changed = pyqtSignal(bool)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.model_dropdown = ModelDropdown()
        self.thinking_mode_button = ThinkingModeButton()
        self._init_UI()

    def _init_UI(self) -> None:
        """Initialize the settings row layout with the model selector dropdown."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.model_dropdown.model_changed.connect(self.model_changed)
        self.thinking_mode_button.thinking_mode_changed.connect(
            self.thinking_mode_changed
        )

        layout.addStretch()
        layout.addWidget(self.model_dropdown)
        layout.addWidget(self.thinking_mode_button)
