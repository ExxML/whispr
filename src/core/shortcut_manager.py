import ctypes
import ctypes.wintypes
import math
import threading
from typing import Callable

from PyQt6.QtCore import QObject, QPoint, QTimer, pyqtSignal

from core.screenshot_manager import ScreenshotManager
from core.win32_hook import (
    HOOKPROC,
    KBDLLHOOKSTRUCT,
    KEYEVENTF_EXTENDEDKEY,
    LLKHF_EXTENDED,
    LLKHF_INJECTED,
    MOD_ALT,
    MOD_CTRL,
    MOD_SHIFT,
    MODIFIER_VK_CODES,
    VK_DOWN,
    VK_LEFT,
    VK_RIGHT,
    VK_TO_MOD_BIT,
    VK_UP,
    WH_KEYBOARD_LL,
    WM_KEYDOWN,
    WM_KEYUP,
    WM_QUIT,
    WM_SYSKEYDOWN,
    WM_SYSKEYUP,
    kernel32,
    user32,
)
from ui.main_window import MainWindow


class ShortcutManager(QObject):
    """Manages global keyboard shortcuts via a Win32 low-level keyboard hook.

    Key suppression strategy
    ------------------------
    Modifier keys (Ctrl, Alt, Shift) are intercepted and suppressed the moment
    they are pressed down, before any other application sees them. Their state
    is tracked internally. When the user then presses a non-modifier key, the
    hook checks whether the complete combination (held modifiers + that key)
    matches a registered whispr hotkey:

    - Match: the hotkey fires and the entire combination (modifiers + key) is
      fully suppressed — no other application ever sees any part of it.
    - No match: the suppressed modifier key-downs are replayed via keybd_event
      so the target application receives the complete, intact key combination
      as if whispr had never intercepted it.

    Conditional hotkeys (everything except the visibility toggle) are only
    active while the main window is visible.
    """

    # Qt signals for thread-safe communication with the main thread
    # ALL UI actions must be performed on the main thread to avoid crashes and unpredictable behaviour (ex. leaking hotkeys)
    move_signal = pyqtSignal(int, int)
    scroll_signal = pyqtSignal(int)
    quit_signal = pyqtSignal()
    screenshot_signal = pyqtSignal()
    clear_chat_signal = pyqtSignal()
    minimize_signal = pyqtSignal()
    toggle_signal = pyqtSignal()
    send_message_signal = pyqtSignal(str)

    def __init__(
        self, main_window: MainWindow, screenshot_manager: ScreenshotManager
    ) -> None:
        super().__init__()
        self.main_window = main_window
        self.screenshot_manager = screenshot_manager

        # Connect signals
        self.move_signal.connect(
            self._start_animation
        )  # Signal needed because QTimers cannot be started from another thread
        self.scroll_signal.connect(self.main_window.chat_area.shortcut_scroll)
        self.quit_signal.connect(self.main_window.quit_app)
        self.screenshot_signal.connect(self.screenshot_manager.take_screenshot)
        self.clear_chat_signal.connect(self.main_window.chat_area.clear_chat)
        self.minimize_signal.connect(self.main_window.hide)
        self.toggle_signal.connect(self.main_window.toggle_window_visibility)
        self.send_message_signal.connect(self.main_window.send_message)

        # Initialize animation
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._animate_step)
        self.animation_active = False
        self.animation_start_pos: QPoint | None = None
        self.animation_target_pos: QPoint | None = None
        self.animation_progress = 0.0
        self._setup_movement_distances()

        # Hotkey lookup tables: (modifier_bitmask, vk_code) -> (callback, repeat_callbacks)
        self.always_active_hotkeys: dict[
            tuple[int, int], tuple[Callable[[], None], bool]
        ] = {}
        self.main_window_hotkeys: dict[
            tuple[int, int], tuple[Callable[[], None], bool]
        ] = {}
        self.suppressed_vk_codes: set[int] = (
            set()
        )  # Non-modifier keys currently suppressed by a matched hotkey
        self.held_vk_codes: set[int] = (
            set()
        )  # Non-modifier keys currently physically held down
        self.held_modifier_vks: set[int] = (
            set()
        )  # Modifier keys currently held (tracked internally, never forwarded to the OS)
        self.suppressed_mod_events: dict[
            int, tuple[int, int]
        ] = {}  # Modifier key-downs intercepted but not yet delivered: VK -> (scanCode, flags)
        self._set_hotkeys()

        # Low-level keyboard hook (prevent GC of the callback reference)
        self.hook_proc_ref = HOOKPROC(self._low_level_keyboard_proc)
        self.hook_handle = None
        self.hook_thread_id = None
        self._start_hook()

    def _set_hotkeys(self) -> None:
        """Populate the hotkey lookup tables.

        Default Shortcuts:
            Ctrl + E - Show / hide main window (always active)
            Ctrl + D - Generate AI output (trigger on release)
            Ctrl + G - Fix / improve code (trigger on release)
            Ctrl + Alt + <ArrowKeys> - Move main window
            Ctrl + Shift + Up / Down - Scroll chat area
            Ctrl + Shift + S - Take a screenshot
            Ctrl + N - Clear chat history
            Ctrl + Q - Minimize main window
            Ctrl + Shift + Q - Quit the application
        """
        self.always_active_hotkeys = {
            (MOD_CTRL, ord("E")): (self._toggle_window_visibility, False),
            (MOD_CTRL | MOD_SHIFT, ord("Q")): (self._close_app, False),
        }

        self.main_window_hotkeys = {
            (MOD_CTRL | MOD_ALT, VK_LEFT): (self._move_window_left, True),
            (MOD_CTRL | MOD_ALT, VK_RIGHT): (self._move_window_right, True),
            (MOD_CTRL | MOD_ALT, VK_UP): (self._move_window_up, True),
            (MOD_CTRL | MOD_ALT, VK_DOWN): (self._move_window_down, True),
            (MOD_CTRL | MOD_SHIFT, VK_UP): (self._scroll_up, True),
            (MOD_CTRL | MOD_SHIFT, VK_DOWN): (self._scroll_down, True),
            (MOD_CTRL | MOD_SHIFT, ord("S")): (self._screenshot, False),
            (MOD_CTRL, ord("Q")): (self._minimize, False),
            (MOD_CTRL, ord("N")): (self._clear_chat, False),
            (MOD_CTRL, ord("D")): (self._generate_with_screenshot, False),
            (MOD_CTRL, ord("G")): (self._generate_with_screenshot_fix, False),
        }

    # Win32 Keyboard Hook Logic

    def _low_level_keyboard_proc(self, nCode: int, wParam: int, lParam: int) -> int:
        """Win32 low-level keyboard hook callback.

        Implements the modifier suppression strategy described in the class
        docstring. The decision tree for each incoming key event is:

        1. Injected event (from our own keybd_event replay) — pass straight
           through to avoid re-processing.
        2. Modifier key-down — suppress and record internally; do not forward.
        3. Modifier key-up — if the corresponding key-down was suppressed,
           suppress the key-up too (the key was never delivered, so neither
           should its release be).
        4. Non-modifier key-down with a matching hotkey — fire the callback and
           suppress the key; the entire combination stays hidden from the OS.
        5. Non-modifier key-down with no matching hotkey — replay all previously
           suppressed modifier key-downs followed by this key via keybd_event,
           delivering the intact combination to other applications.
        6. Non-modifier key-up for a suppressed key — suppress the release to
           match its suppressed key-down.

        Args:
            nCode (int): Hook code indicating how to process the message.
            wParam (int): Message type identifier (e.g. WM_KEYDOWN, WM_KEYUP).
            lParam (int): Pointer to a KBDLLHOOKSTRUCT containing key event data.

        Returns:
            int: 1 to suppress the key event, or the result of CallNextHookEx.
        """
        if nCode >= 0:
            kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk_code = kb.vkCode
            is_key_down = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
            is_key_up = wParam in (WM_KEYUP, WM_SYSKEYUP)

            # Step 1: Pass through events we injected ourselves via keybd_event (see step 5 below)
            if kb.flags & LLKHF_INJECTED:
                return int(
                    user32.CallNextHookEx(self.hook_handle, nCode, wParam, lParam)
                )

            if vk_code in MODIFIER_VK_CODES:
                # Steps 2 & 3: Intercept all modifier keys so that no partial combination
                # (e.g. a bare Ctrl press) leaks through to other applications. The decision
                # of whether to ultimately suppress or replay is deferred until we see the
                # accompanying non-modifier key.
                if is_key_down:
                    self.held_modifier_vks.add(vk_code)
                    self.suppressed_mod_events[vk_code] = (
                        int(kb.scanCode),
                        int(kb.flags),
                    )
                    return 1  # Step 2: Suppress modifier key-down

                if is_key_up:
                    self.held_modifier_vks.discard(vk_code)
                    if vk_code in self.suppressed_mod_events:
                        del self.suppressed_mod_events[vk_code]
                        return 1  # Step 3: Suppress key-up to match the suppressed key-down
            else:
                # Non-modifier key: now we have the full picture — check the combination
                # against the hotkey tables using the internally tracked modifier state.
                modifiers = self._compute_modifier_mask()
                hotkey_key = (modifiers, vk_code)

                # Look up in always-active table first, then main window table
                entry = self.always_active_hotkeys.get(hotkey_key)
                if entry is None and self.main_window.isVisible():
                    entry = self.main_window_hotkeys.get(hotkey_key)

                if entry is not None:
                    # Step 4: Whispr hotkey matched — fire the callback and suppress the
                    # entire combination; the suppressed modifier key-downs are never replayed.
                    callback, repeat_callbacks = entry
                    if is_key_down:
                        # For no-repeat hotkeys, skip if the key is already physically held
                        if not repeat_callbacks and vk_code in self.held_vk_codes:
                            return 1  # Suppress repeat without calling callback
                        self.held_vk_codes.add(vk_code)
                        self.suppressed_vk_codes.add(vk_code)
                        callback()
                        return 1  # Suppress the key event

                    if is_key_up:
                        self.held_vk_codes.discard(vk_code)
                        if vk_code in self.suppressed_vk_codes:
                            self.suppressed_vk_codes.discard(vk_code)
                            return 1  # Suppress the matching key-up

                elif is_key_down and self.suppressed_mod_events:
                    # Step 5: No hotkey match — replay the suppressed modifier key-downs
                    # followed by this key so other applications receive the intact combination.
                    self._replay_modifiers_and_key(
                        int(vk_code), int(kb.scanCode), int(kb.flags)
                    )
                    return 1  # Suppress the original event; the injected replay delivers it

                elif is_key_up:
                    # Step 6: Suppress key-up for any key whose key-down was already suppressed
                    # (handles the edge case where a modifier was released before key-up)
                    self.held_vk_codes.discard(vk_code)
                    if vk_code in self.suppressed_vk_codes:
                        self.suppressed_vk_codes.discard(vk_code)
                        return 1  # Suppress key-up to match its suppressed key-down

        return int(user32.CallNextHookEx(self.hook_handle, nCode, wParam, lParam))

    def _compute_modifier_mask(self) -> int:
        """Return a bitmask of currently held modifier keys based on internal tracking.

        Uses the internally maintained set of held modifier VK codes rather than
        querying the OS directly, because all modifier events are suppressed before
        the OS can update its own key-state registers.

        Returns:
            int: Bitmask of active modifier keys (MOD_CTRL, MOD_ALT, MOD_SHIFT).
        """
        mask = 0
        for vk in self.held_modifier_vks:
            mask |= VK_TO_MOD_BIT.get(vk, 0)
        return mask

    def _replay_modifiers_and_key(
        self, vk_code: int, scan_code: int, flags: int
    ) -> None:
        """Replay a non-whispr key combination to other applications.

        Injects the previously suppressed modifier key-downs followed by the
        non-modifier key into the input stream via keybd_event, reconstructing
        the full key combination as if whispr had never intercepted it. The
        suppressed modifier records are cleared after injection so that their
        real key-up events (which continue to arrive from the hook) are no
        longer suppressed and pass through normally.

        The injected events carry the LLKHF_INJECTED flag, which the hook uses
        to identify and pass them through without re-processing (step 1).

        Args:
            vk_code (int): Virtual key code of the non-modifier key to replay.
            scan_code (int): Hardware scan code of the non-modifier key.
            flags (int): Hook flags from KBDLLHOOKSTRUCT (used to detect extended keys).
        """
        for mod_vk, (mod_scan, mod_flags) in self.suppressed_mod_events.items():
            kb_flags = KEYEVENTF_EXTENDEDKEY if (mod_flags & LLKHF_EXTENDED) else 0
            user32.keybd_event(mod_vk, mod_scan, kb_flags, None)
        self.suppressed_mod_events.clear()

        kb_flags = KEYEVENTF_EXTENDEDKEY if (flags & LLKHF_EXTENDED) else 0
        user32.keybd_event(vk_code, scan_code, kb_flags, None)

    def _hook_thread_entry(self) -> None:
        """Entry point for the keyboard hook thread.

        Installs the low-level keyboard hook, then enters a message loop that
        keeps the hook alive until a WM_QUIT message is posted.
        """
        self.hook_thread_id = kernel32.GetCurrentThreadId()
        h_module = kernel32.GetModuleHandleW(None)

        self.hook_handle = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            self.hook_proc_ref,
            h_module,
            0,  # Monitor all threads (required for low-level hooks)
        )

        # Pump messages to keep the hook alive
        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            pass  # No dispatch needed; WM_QUIT causes GetMessageW to return 0

        if self.hook_handle:
            user32.UnhookWindowsHookEx(self.hook_handle)
            self.hook_handle = None

    def _start_hook(self) -> None:
        """Start the keyboard hook on a dedicated daemon thread"""
        hook_thread = threading.Thread(target=self._hook_thread_entry, daemon=True)
        hook_thread.start()

    def _stop_hook(self) -> None:
        """Stop the keyboard hook and its message loop"""
        if self.hook_thread_id is not None:
            user32.PostThreadMessageW(self.hook_thread_id, WM_QUIT, 0, 0)
            self.hook_thread_id = None

    # Hotkey Callback Functions

    def _setup_movement_distances(self) -> None:
        """Determine screen geometry and movement distances"""
        assert self.main_window.primary_screen is not None
        self.screen_rect = self.main_window.primary_screen.availableGeometry()
        self.max_move_distance_x = self.screen_rect.width() // 14
        self.max_move_distance_y = self.screen_rect.height() // 14
        self.screen_bounds_offset = (
            2  # Always keep 2 pixels to screen edge to prevent setGeometry errors
        )
        self.animation_duration = 100  # Animation duration in milliseconds
        self.animation_fps = 120  # Frames per second
        self.animation_frame_time = 1000 // self.animation_fps  # Time per frame in ms

    def _start_animation(self, target_x: int, target_y: int) -> None:
        """Begin an animated move to the target position.

        Args:
            target_x (int): Target x-coordinate for the main window.
            target_y (int): Target y-coordinate for the main window.
        """
        self.animation_start_pos = self.main_window.pos()
        self.animation_target_pos = QPoint(target_x, target_y)
        self.animation_progress = 0.0
        self.animation_active = True
        self.animation_timer.start(self.animation_frame_time)

    def _animate_step(self) -> None:
        """Advance one frame of the movement animation"""
        assert self.animation_start_pos is not None
        assert self.animation_target_pos is not None
        self.animation_progress += self.animation_frame_time / self.animation_duration

        if self.animation_progress >= 1.0:
            # Animation complete
            self.main_window.move(self.animation_target_pos)
            self.animation_timer.stop()
            self.animation_active = False
        else:
            # Ease-out sine motion: sin(t * π/2)
            ease_progress = math.sin(self.animation_progress * math.pi / 2)
            current_x = int(
                self.animation_start_pos.x()
                + (self.animation_target_pos.x() - self.animation_start_pos.x())
                * ease_progress
            )
            current_y = int(
                self.animation_start_pos.y()
                + (self.animation_target_pos.y() - self.animation_start_pos.y())
                * ease_progress
            )
            self.main_window.move(current_x, current_y)

    def _toggle_window_visibility(self) -> None:
        """Toggle main window visibility"""
        self.toggle_signal.emit()

    def _move_window_left(self) -> None:
        """Move main window left"""
        if self.animation_active and self.animation_progress < 0.5:
            return
        new_x = max(
            self.screen_bounds_offset,
            self.main_window.geometry().x() - self.max_move_distance_x,
        )
        self.move_signal.emit(new_x, self.main_window.geometry().y())

    def _move_window_right(self) -> None:
        """Move main window right"""
        if self.animation_active and self.animation_progress < 0.5:
            return
        max_x = (
            self.screen_rect.width()
            - self.main_window.geometry().width()
            - self.screen_bounds_offset
        )
        new_x = min(max_x, self.main_window.geometry().x() + self.max_move_distance_x)
        self.move_signal.emit(new_x, self.main_window.geometry().y())

    def _move_window_up(self) -> None:
        """Move main window up"""
        if self.animation_active and self.animation_progress < 0.5:
            return
        new_y = max(
            self.screen_bounds_offset,
            self.main_window.geometry().y() - self.max_move_distance_y,
        )
        self.move_signal.emit(self.main_window.geometry().x(), new_y)

    def _move_window_down(self) -> None:
        """Move main window down"""
        if self.animation_active and self.animation_progress < 0.5:
            return
        max_y = (
            self.screen_rect.height()
            - self.main_window.geometry().height()
            - self.screen_bounds_offset
        )
        new_y = min(max_y, self.main_window.geometry().y() + self.max_move_distance_y)
        self.move_signal.emit(self.main_window.geometry().x(), new_y)

    def _scroll_up(self) -> None:
        """Scroll up in the chat area"""
        self.scroll_signal.emit(-100)

    def _scroll_down(self) -> None:
        """Scroll down in the chat area"""
        self.scroll_signal.emit(100)

    def _close_app(self) -> None:
        """Close the application"""
        self.quit_signal.emit()  # Must emit signal to run on main thread

    def _screenshot(self) -> None:
        """Take a screenshot of the primary screen"""
        self.screenshot_signal.emit()

    def _minimize(self) -> None:
        """Minimize the main window"""
        self.minimize_signal.emit()

    def _clear_chat(self) -> None:
        """Clear the chat history"""
        self.clear_chat_signal.emit()

    def _generate_with_screenshot(self) -> None:
        """Take a screenshot then automatically generate content."""
        self.screenshot_manager.take_screenshot()
        self.send_message_signal.emit(
            """Help me solve this programming problem. Be concise.
1. Give me 5 clarification questions to ask about the problem.
2. State the type of problem (ex. Arrays & Hashing, Two Pointers, Sliding Window, Stack, Binary Search, Linked List, Trees, Heap / Priority Queue, Backtracking, Tries, Graphs, Advanced Graphs, 1-D Dynamic Programming, 2-D Dynamic Programming, Greedy, Intervals, Math & Geometry, and/or Bit Manipulation), data structure(s), what each element in the data structure means, and algorithm(s) used to solve this problem.
3. Give me a high-level, point-form plan to approach and solve this problem (including edge cases).
4. Give me a short example walkthrough using your solution.
5. Give me a code block with the solution in Python, supplied with comments.
6. Give me a concise explanation of the solution.
7. Give me the time and space complexity for the solution."""
        )

    def _generate_with_screenshot_fix(self) -> None:
        """Take a screenshot then automatically generate content to fix or improve code."""
        self.screenshot_manager.take_screenshot()
        self.send_message_signal.emit(
            "Fix or improve the code based on the new instructions. Then, state the changes you made."
        )
