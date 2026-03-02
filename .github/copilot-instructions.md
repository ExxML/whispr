# Copilot Instructions — whispr

## Project Overview

whispr is a Windows-only desktop overlay for real-time AI programming assistance. It captures screenshots, sends them with chat context to the Gemini API, and streams formatted responses into a PyQt6 app window.

## Architecture

```
src/whispr.py — Entry point; wires together all components
src/core/ — Backend: AI, input hooks, screenshots
src/ui/ — PyQt6 overlay UI (frameless, translucent)
src/data/ — Runtime data (chat_history.json, config.json, cache/)
src/assets/ — Icons and images
```

**Data flow:** User hotkey → `ShortcutManager` emits Qt signal → `AIReceiver.handle_message()` → spawns `threading.Thread` calling `AISender.generate_content_with_screenshot()` → Gemini streaming API → chunks emitted via `pyqtSignal` → `ChatArea` renders via `ChatBubble` + `ai_formatter.py`.

**Key component roles:**
- `ShortcutManager` (`core/shortcut_manager.py`) — Win32 low-level keyboard hook (`WH_KEYBOARD_LL`) on a dedicated thread. All hotkey callbacks emit **Qt signals** to marshal work onto the main thread; never call UI methods directly from the hook thread.
- `AISender` (`core/ai_sender.py`) — Gemini API client. Uses `google-genai` with streaming (`generate_content_stream`). Model: `gemini-2.5-flash` with thinking disabled.
- `AIReceiver` (`core/ai_receiver.py`) — Bridges AI generation (background `threading.Thread`) and the UI via `pyqtSignal`. Uses `threading` instead of `QThread` due to Nuitka compilation issues.
- `MainWindow` (`ui/main_window.py`) — Frameless, translucent `QWidget` with `WindowStaysOnTopHint | Tool` flags. Custom `paintEvent` draws rounded corners/border. Visibility timer re-raises window every 1s.
- `ai_formatter.py` (`ui/ai_formatter.py`) — Converts Markdown-like bot text to HTML for `QLabel`. Currently a known pain point (see WIP.md); being redesigned.

## Critical Conventions

### Threading Model
- **UI work must happen on the main Qt thread.** The `ShortcutManager` hook thread and `AIReceiver` generation thread communicate with UI exclusively through `pyqtSignal`. Adding a new hotkey or AI action must follow this pattern.
- Use `threading.Thread(daemon=True)` for background work, not `QThread` (Nuitka compat).

### Hotkey System
- Hotkeys are registered in `ShortcutManager._define_hotkeys()` as `(modifier_bitmask, vk_code) → (callback, repeat_allowed)` tuples in two dicts: `_always_active_hotkeys` (work even when overlay is hidden) and `_main_window_hotkeys` (only when visible).
- Modifier constants (`MOD_CTRL`, `MOD_ALT`, `MOD_SHIFT`) and Win32 types are defined in `core/win32_hook.py`.
- All matched key events are **suppressed** (return 1 from hook proc). The hook also tracks held keys to prevent repeat-firing for non-repeatable hotkeys.

## Static Analysis

All code must pass the following checks before merging:

```
ruff check src          # Linter
ruff format --check src # Formatter
mypy --strict src       # Type checker (strict mode)
```

The CI workflow (`.github/workflows/static-analysis.yml`) runs these automatically on every push and pull request. Write code that satisfies all three from the start.

## Coding Style Conventions

### Import Statements
All import statements must follow PEP 8 standard import ordering:
1. Standard library imports
2. Third-party imports
3. Local application imports

Separate each group with exactly one blank line. Sort imports alphabetically within each group. Within each group, bare `import X` statements come before `from X import Y` statements. When importing multiple names from a single module, list them alphabetically on one line:
```python
from PyQt6.QtCore import QObject, QPoint, QTimer, pyqtSignal
```
When the list is long, use a parenthesized multi-line form with one name per line, alphabetized:
```python
from core.win32_hook import (
    HOOKPROC,
    KBDLLHOOKSTRUCT,
    MOD_ALT,
    MOD_CTRL,
)
```
Use **absolute imports** (ex. `from core.ai_receiver import AIReceiver`) for all imports, regardless of whether it is in the same module or cross-module.
Never use wildcard/star imports.

### Class and Function/Method Definitions Grouping
All public classes/functions/methods must be defined before private ones. Additionally, keep related functions/methods together, e.g., all GUI setup functions together.

### Docstrings
Every function (except __init__), method, and class must have a Google-style docstring using triple double quotes (`"""`). All docstrings should be in imperative mood and every sentence should end with a period.

**One-line docstrings:** Opening and closing quotes on the same line if the docstring fits in a single line.
```python
def stop(self):
    """Signal the thread to stop."""
```

**Multi-line docstrings:** Opening triple quotes on the same line as a short summary. Blank line after summary before sections. Closing triple quotes on their own line, aligned with the enclosing definition.

**Sections** (include only if relevant):
- `Args:` — List parameters with type in parentheses and description. Omit if there are no parameters.
- `Returns:` — Describe the return value with type and description. Omit if `None`.

Do not document unused parameters required only for overriding methods. 

Example:
```python
def generate_content(self, user_input, on_chunk=None):
    """Generate AI content by streaming from the Gemini model.

    Args:
        user_input (str): The user's input text to send to the model.
        on_chunk (callable, optional): Callback invoked with each text chunk as it streams.

    Returns:
        str: The full generated response text.
    """
```

**Class docstrings** are typically single-line. For complex classes, use a multi-line docstring with a blank line separating the summary from the extended description:
```python
class ShortcutManager(QObject):
    """Manages global keyboard shortcuts via a Win32 low-level keyboard hook.

    All registered hotkeys are suppressed so other applications never see the
    key events.
    """
```

### Type Hints
Always add type hints, return types, and function annotations to all functions and methods. Use `-> None` for functions that do not return a value. If the type of a parameter or return value is unclear, use `Any` from the `typing` module. If there are multiple possible types, use `|` to indicate a union (e.g. `str | None`). For callbacks, use `Callable` from `typing` (never the built-in `callable`) with the appropriate signature (e.g. `Callable[[str], None]` for a function that takes a string and returns nothing).

**Strict mypy requirements (`mypy --strict`):**
- Generic types must always include type parameters: use `re.Match[str]`, not `re.Match`; use `list[str]`, not `list`; etc.
- Never use `callable` as a type — always import and use `Callable` from `typing`.
- PyQt6 event override methods must accept `| None` on the event parameter to match the supertype signature, e.g.:
  ```python
  def mousePressEvent(self, event: QMouseEvent | None) -> None:
  def paintEvent(self, _event: QPaintEvent | None) -> None:
  def resizeEvent(self, event: QResizeEvent | None) -> None:
  def enterEvent(self, event: QEnterEvent | None) -> None:
  def leaveEvent(self, event: QEvent | None) -> None:
  ```
- When calling Qt methods that return `X | None` (e.g. `QApplication.primaryScreen()`, `verticalScrollBar()`), either assert the result is not `None` or store it typed as `X` before use. When possible, directly instantiate objects in __init__ instead of setting the variable as `None` in __init__. This ensures the variable is always properly typed and eliminates the need for `None` checks.
- Functions that return a value from a C-extension call (e.g. ctypes/win32) must explicitly cast the result to the declared return type (e.g. `return int(...)`) to avoid returning `Any`.

Example:
```python
def process(a: int, b: int) -> None:
```

When passing in an object as a parameter, the parameter name should be the class name in lower_snake_case and the type hint should be the class of the object. You should use the most general type that covers the operations needed. Do not over-specify unless subclass-specific functionality of the parameter is required (ex. accessing a parameter object's methods/variables).

Example:
```python
def __init__(self, main_window: QWidget, bg_color: QColor) -> None:  # main_window is only used for super.__init__ and therefore does not need to be typed as MainWindow
```
```python
def __init__(self, chat_area: ChatArea, is_top: bool) -> None:  # chat_area.bg_color is accessed later in the method, which falls under subclass-specific functionality, and therefore chat_area should be typed as ChatArea, not QWidget
```

### Naming Conventions

| Category | Convention | Examples |
|---|---|---|
| Classes | `PascalCase` | `MainWindow`, `ChatBubble`, `AIReceiver` |
| Public Functions / Methods | `snake_case` | `take_screenshot`, `handle_message` |
| Private Functions / Methods | Single underscore prefix | `_initUI`, `_on_response_chunk` |
| Public Variables | `snake_case` | `full_response`, `chat_history_path` |
| Private Variables | No prefix | `streaming_bubble`, `visibility_timer` | 
| Public Constants | `UPPER_SNAKE_CASE` | `WH_KEYBOARD_LL`, `MOD_CTRL` |
| Private Constants | No prefix | `BG_COLOR`, `VK_SHIFT` |
| Qt Signals | `snake_case`, no underscore | `message_sent`, `move_signal`, `finished` |
| Event Handler Methods | `on_` prefix | `on_response_ready`, `on_tray_activated` |

Acronyms stay uppercase in class names: `AISender`, `AIReceiver`. No double-underscore (name-mangling) prefixes.

Unused variables and parameters (in functions that are overriden, for example) should be prefixed with an underscore to indicate intentional non-use (e.g. `_unused_param`).

### String Formatting
- Use **f-strings** for all string interpolation. Never use `.format()` or `%`-style formatting.
- Use **single quotes** (`'...'`) only when the outside string uses double quotes.
- Use **double quotes** (`"..."`) for all regular strings.
- Use **triple double quotes** (`"""..."""`) for docstrings and multi-line prompt strings.
- Never use **triple single quotes**.


### Whitespace and Formatting
- **Indentation:** 4 spaces.
- **Blank lines:** 2 blank lines before top-level class/function definitions. 1 blank line between methods within a class while respecting the surrounding indentation. 1 blank line between logical blocks inside methods while respecting the surrounding indentation.
- **Line length:** No strict limit, but keep lines reasonable (~120 characters). Long expressions may span multiple lines.
- **Multi-line expressions:** Opening paren at end of line, closing paren on its own line aligned with the statement. Operators at end of line:
```python
self.setWindowFlags(
    Qt.WindowType.FramelessWindowHint |
    Qt.WindowType.WindowStaysOnTopHint |
    Qt.WindowType.Tool
)
```

### Inline Comments
- Separated by at least 2 spaces from code. Use sparingly for non-obvious logic.