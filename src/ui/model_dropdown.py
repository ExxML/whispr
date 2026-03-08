from PyQt6.QtCore import QEvent, QObject, QPoint, QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QCloseEvent,
    QColor,
    QEnterEvent,
    QFontMetrics,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
)
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from core.ai_sender import DEFAULT_MODEL, MODELS

ITEM_HORIZONTAL_PADDING = 8
ITEM_VERTICAL_PADDING = 6


class ModelDropdown(QWidget):
    """Custom dropdown button for selecting the active Gemini model."""

    model_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current_model_id = DEFAULT_MODEL
        self.current_display = next(
            name for name, model_id in MODELS if model_id == DEFAULT_MODEL
        )
        self.popup: _ModelPopup | None = None
        self.shield: _PopupShield | None = None
        self._init_UI()

    def eventFilter(self, watched: QObject | None, event: QEvent | None) -> bool:
        """Close the popup on a mouse press outside it."""
        if (
            event is not None
            and event.type() == QEvent.Type.MouseButtonPress
            and isinstance(event, QMouseEvent)
            and self.popup is not None
            and not self.popup.geometry().contains(event.pos())
        ):
            self.popup.close()
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        """Toggle the model selection popup on click."""
        if event is None:
            return

        if self.popup is not None and self.popup.isVisible():
            self.popup.close()
            return

        self._show_popup()

    def paintEvent(self, _event: QPaintEvent | None) -> None:
        """Draw the current model name right-aligned."""
        painter = QPainter(self)
        painter.setPen(QColor(255, 255, 255, 128))
        painter.setFont(self.font())
        painter.drawText(
            QRect(-4, 0, self.width(), self.height()),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            self.current_display,
        )
        painter.end()

    def _init_UI(self) -> None:
        """Set up widget dimensions and cursor."""
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        font = self.font()
        font.setPixelSize(12)
        self.setFont(font)

        fm = QFontMetrics(font)
        max_width = max(fm.horizontalAdvance(name) for name, _ in MODELS)
        self.setFixedWidth(max_width + 25)
        self.setFixedHeight(fm.height() + 8)

    def _show_popup(self) -> None:
        """Create and display the model selection popup above this widget."""
        main_window = self.window()
        assert main_window is not None

        global_pos = self.mapToGlobal(QPoint(self.width(), 0))
        local_pos = main_window.mapFromGlobal(global_pos)

        self.popup = _ModelPopup(main_window, self.current_model_id)
        self.popup.model_selected.connect(self._on_model_selected)
        self.popup.closed.connect(self._on_popup_closed)
        popup_size = self.popup.sizeHint()
        self.popup.setGeometry(
            local_pos.x() - popup_size.width(),
            local_pos.y() - popup_size.height(),
            popup_size.width(),
            popup_size.height(),
        )

        self.shield = _PopupShield(main_window)
        self.shield.setGeometry(self.popup.geometry())
        self.shield.raise_()
        self.shield.show()

        self.popup.raise_()
        self.popup.show()
        main_window.installEventFilter(self)

    def _on_model_selected(self, display_name: str, model_id: str) -> None:
        """Handle a model selection from the popup."""
        self.current_display = display_name
        self.current_model_id = model_id
        self.update()
        self.model_changed.emit(model_id)

    def _on_popup_closed(self) -> None:
        """Clean up the shield, event filter, and popup references."""
        main_window = self.window()
        if main_window is not None:
            main_window.removeEventFilter(self)
        if self.shield is not None:
            self.shield.close()
            self.shield = None
        self.popup = None


class _ModelPopup(QWidget):
    """Frameless popup widget for selecting a Gemini model."""

    model_selected = pyqtSignal(str, str)
    closed = pyqtSignal()

    def __init__(self, parent: QWidget, current_model_id: str) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._init_UI(current_model_id)

    def closeEvent(self, event: QCloseEvent | None) -> None:
        """Emit the closed signal when the popup is closing."""
        self.closed.emit()
        super().closeEvent(event)

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        """Close the popup on Escape key press."""
        if event is not None and event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def paintEvent(self, _event: QPaintEvent | None) -> None:
        """Draw the popup background with rounded corners and a border."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)

        painter.fillPath(path, QColor(20, 20, 20, 153))
        painter.strokePath(path, QPen(QColor(255, 255, 255, 128), 1))
        painter.end()

    def _init_UI(self, current_model_id: str) -> None:
        """Build the list of model items."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)

        font = self.font()
        font.setPixelSize(12)
        fm = QFontMetrics(font)
        item_width = (
            max(fm.horizontalAdvance(name) for name, _ in MODELS)
            + ITEM_HORIZONTAL_PADDING * 2
        )

        for display_name, model_id in MODELS:
            item = _ModelItem(display_name, model_id, model_id == current_model_id)
            item.setFixedWidth(item_width)
            item.clicked.connect(self._on_item_clicked)
            layout.addWidget(item)

    def _on_item_clicked(self, display_name: str, model_id: str) -> None:
        """Forward the selection and close the popup."""
        self.model_selected.emit(display_name, model_id)
        self.close()


class _PopupShield(QWidget):
    """Clears the main window content behind the popup so app UI does not bleed through."""

    def paintEvent(self, _event: QPaintEvent | None) -> None:
        """Erase the backing store pixels to transparent with rounded corners."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)

        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 9, 9)
        painter.fillPath(path, Qt.GlobalColor.transparent)
        painter.end()


class _ModelItem(QWidget):
    """Individual model option within the selection popup."""

    clicked = pyqtSignal(str, str)

    def __init__(self, display_name: str, model_id: str, is_selected: bool) -> None:
        super().__init__()
        self.display_name = display_name
        self.model_id = model_id
        self.is_selected = is_selected
        self.is_hovered = False
        self._init_UI()

    def enterEvent(self, event: QEnterEvent | None) -> None:
        """Highlight the item on mouse hover."""
        self.is_hovered = True
        self.update()

    def leaveEvent(self, event: QEvent | None) -> None:
        """Remove highlight when mouse leaves."""
        self.is_hovered = False
        self.update()

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        """Emit clicked signal with the model display name and ID."""
        if event is not None:
            self.clicked.emit(self.display_name, self.model_id)

    def paintEvent(self, _event: QPaintEvent | None) -> None:
        """Draw the model name with color based on selection and hover state."""
        painter = QPainter(self)

        if self.is_hovered:
            painter.setPen(QColor(255, 255, 255, 255))
        else:
            painter.setPen(QColor(255, 255, 255, 128))

        painter.setFont(self.font())
        text_rect = QRect(
            ITEM_HORIZONTAL_PADDING,
            0,
            self.width() - ITEM_HORIZONTAL_PADDING * 2,
            self.height(),
        )
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.display_name,
        )
        painter.end()

    def _init_UI(self) -> None:
        """Set up the item dimensions and cursor."""
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        font = self.font()
        font.setPixelSize(12)
        self.setFont(font)

        fm = QFontMetrics(font)
        self.setFixedHeight(fm.height() + ITEM_VERTICAL_PADDING * 2)
