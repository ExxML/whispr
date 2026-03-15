from PyQt6.QtGui import QColor

PRIMARY_COLOR: tuple[int, int, int] = (255, 255, 255)
BG_COLOR: tuple[int, int, int] = (20, 20, 20)


def qcolor(rgb: tuple[int, int, int], alpha: int | None = None) -> QColor:
    """Convert an RGB tuple and optional alpha value to a QColor object.

    Args:
        rgb (tuple[int, int, int]): Store the red, green, and blue channel values.
        alpha (int | None): Store the optional alpha channel value.

    Returns:
        QColor: Return the converted Qt color object.
    """
    r, g, b = rgb
    c = QColor(r, g, b)
    if alpha is not None:
        c.setAlpha(alpha)
    return c


def qss(rgb: tuple[int, int, int], alpha: int | None = None) -> str:
    """Convert an RGB tuple and optional alpha value to a QSS string.

    Args:
        rgb (tuple[int, int, int]): Store the red, green, and blue channel values.
        alpha (int | None): Store the optional alpha channel value.

    Returns:
        str: Return the formatted QSS color string.
    """
    r, g, b = rgb
    if alpha is None:
        return f"rgb({r}, {g}, {b})"
    return f"rgba({r}, {g}, {b}, {alpha})"
