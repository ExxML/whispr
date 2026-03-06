from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPaintEvent, QPainter, QPen, QPolygon
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QWidget


class InputSettings(QWidget):
    """Settings row displayed below the message input field."""

    model_changed = pyqtSignal(str)

    MODELS: list[tuple[str, str]] = [
        ("Gemini 2.5 Flash Lite", "gemini-2.5-flash-lite"),
        ("Gemini 2.5 Flash", "gemini-2.5-flash"),
        ("Gemini 3 Flash Preview", "gemini-3-flash-preview"),
    ]

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._init_UI()

    def selected_model(self) -> str:
        """Return the model identifier of the currently selected item.

        Returns:
            str: The model identifier string of the currently selected model.
        """
        return str(self.model_combo.currentData())

    def _init_UI(self) -> None:
        """Initialize the settings row layout with the model selector dropdown."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addStretch()

        self.model_combo = _ModelComboBox()
        for display, model_id in self.MODELS:
            self.model_combo.addItem(display, userData=model_id)
        self.model_combo.setCurrentIndex(1)  # Default: Gemini 2.5 Flash
        self.model_combo.setFont(QFont("Microsoft JhengHei", 8))
        self.model_combo.view().setMinimumWidth(self.model_combo.sizeHint().width())
        self.model_combo.view().setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        # Style only the popup view; button/frame chrome is suppressed by _ModelComboBox.paintEvent
        self.model_combo.setStyleSheet("""
            QComboBox QAbstractItemView {
                background-color: rgba(20, 20, 20, 153);
                color: rgba(255, 255, 255, 200);
                border: 1px solid rgba(255, 255, 255, 50);
                border-radius: 14px;
                padding: 4px;
                selection-background-color: rgba(255, 255, 255, 35);
                selection-color: rgba(255, 255, 255, 230);
                outline: 0px;
            }
            QComboBox QAbstractItemView::item {
                background-color: transparent;
                padding: 4px 8px;
                min-height: 22px;
                border: none;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: rgba(255, 255, 255, 35);
                border: none;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: rgba(255, 255, 255, 35);
                border: none;
            }
        """)
        self.model_combo.currentTextChanged.connect(self.model_changed)

        layout.addWidget(self.model_combo)


class _ModelComboBox(QComboBox):
    """A frameless QComboBox that renders only the current text and a chevron arrow."""

    ARROW_W = 14
    TEXT_ARROW_GAP = 6

    def __init__(self) -> None:
        super().__init__()
        self.popup_open = False
        self.hiding = False
        self.anim: QPropertyAnimation | None = None

    def showPopup(self) -> None:
        """Open the popup and animate it expanding downward from zero height."""
        if self.anim is not None:
            self.anim.stop()
            self.anim = None
        self.popup_open = True
        self.hiding = False
        self.update()
        super().showPopup()

        view = self.view()
        assert view is not None
        full_h = view.height()
        view.setMaximumHeight(0)
        anim = QPropertyAnimation(view, b"maximumHeight", self)
        anim.setDuration(150)
        anim.setStartValue(0)
        anim.setEndValue(full_h)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self.anim = anim

    def hidePopup(self) -> None:
        """Animate the popup retracting before hiding it."""
        if self.hiding:
            return
        if self.anim is not None:
            self.anim.stop()
            self.anim = None
        self.hiding = True

        view = self.view()
        assert view is not None
        current_h = view.height()
        anim = QPropertyAnimation(view, b"maximumHeight", self)
        anim.setDuration(150)
        anim.setStartValue(current_h)
        anim.setEndValue(0)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        anim.finished.connect(self._finish_hide)
        anim.start()
        self.anim = anim

    def paintEvent(self, _event: QPaintEvent | None) -> None:
        """Draw only the selected item text and a chevron arrow; no frame or button chrome."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        alpha = 200 if self.underMouse() else 127
        color = QColor(255, 255, 255, alpha)

        # Draw current text right-aligned, leaving gap + ARROW_W for the chevron
        painter.setPen(color)
        painter.setFont(self.font())
        text_rect = self.rect().adjusted(0, 0, -(self.ARROW_W + self.TEXT_ARROW_GAP), 0)
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight),
            self.currentText(),
        )

        # Draw V-shaped chevron (pointing up when open, down when closed)
        painter.setPen(QPen(color, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        cx = self.width() - self.ARROW_W // 2
        cy = self.height() // 2
        if self.popup_open:
            arrow = QPolygon(
                [QPoint(cx - 4, cy + 2), QPoint(cx, cy - 2), QPoint(cx + 4, cy + 2)]
            )
        else:
            arrow = QPolygon(
                [QPoint(cx - 4, cy - 2), QPoint(cx, cy + 2), QPoint(cx + 4, cy - 2)]
            )
        painter.drawPolyline(arrow)

    def _finish_hide(self) -> None:
        """Reset popup view max-height, clear state, and call the base hidePopup."""
        self.anim = None
        self.popup_open = False
        self.hiding = False
        self.update()
        view = self.view()
        assert view is not None
        view.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
        super().hidePopup()
