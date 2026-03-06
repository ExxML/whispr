from PyQt6.QtWidgets import QHBoxLayout, QWidget


class InputSettings(QWidget):
    """Settings row displayed below the message input field."""

    MODELS: list[tuple[str, str]] = [
        ("Gemini 2.5 Flash Lite", "gemini-2.5-flash-lite"),
        ("Gemini 2.5 Flash", "gemini-2.5-flash"),
        ("Gemini 3 Flash Preview", "gemini-3-flash-preview"),
    ]

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._init_UI()

    def _init_UI(self) -> None:
        """Initialize the settings row layout with the model selector dropdown."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
