import ctypes
import ctypes.wintypes

# Hook & message constants
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012

# Virtual key codes
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28

# Modifier bitmask values used in hotkey lookup tables
MOD_CTRL = 0x01
MOD_ALT = 0x02
MOD_SHIFT = 0x04

# All modifier virtual key codes (generic + left/right variants)
MODIFIER_VK_CODES = frozenset(
    {
        VK_SHIFT,
        VK_CONTROL,
        VK_MENU,
        0xA0,
        0xA1,  # VK_LSHIFT, VK_RSHIFT
        0xA2,
        0xA3,  # VK_LCONTROL, VK_RCONTROL
        0xA4,
        0xA5,  # VK_LMENU, VK_RMENU
    }
)

# Mapping from modifier VK codes to bitmask values
VK_TO_MOD_BIT: dict[int, int] = {
    VK_SHIFT: MOD_SHIFT,
    VK_CONTROL: MOD_CTRL,
    VK_MENU: MOD_ALT,
    0xA0: MOD_SHIFT,  # VK_LSHIFT
    0xA1: MOD_SHIFT,  # VK_RSHIFT
    0xA2: MOD_CTRL,  # VK_LCONTROL
    0xA3: MOD_CTRL,  # VK_RCONTROL
    0xA4: MOD_ALT,  # VK_LMENU
    0xA5: MOD_ALT,  # VK_RMENU
}

# Low-level keyboard hook flag constants
LLKHF_EXTENDED = 0x01
LLKHF_INJECTED = 0x10

# keybd_event flag constants
KEYEVENTF_EXTENDEDKEY = 0x01


# Win32 structure for low-level keyboard hook data
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.wintypes.DWORD),
        ("scanCode", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


# Callback type for the low-level keyboard hook (LRESULT(nCode, wParam, lParam))
HOOKPROC = ctypes.CFUNCTYPE(
    ctypes.wintypes.LPARAM,  # LRESULT return
    ctypes.c_int,  # nCode
    ctypes.wintypes.WPARAM,  # wParam (message type)
    ctypes.wintypes.LPARAM,  # lParam (pointer to KBDLLHOOKSTRUCT)
)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Configure Win32 function signatures for type safety
user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    HOOKPROC,
    ctypes.wintypes.HINSTANCE,
    ctypes.wintypes.DWORD,
]
user32.SetWindowsHookExW.restype = ctypes.c_void_p
user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
user32.UnhookWindowsHookEx.restype = ctypes.wintypes.BOOL
user32.CallNextHookEx.argtypes = [
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
]
user32.CallNextHookEx.restype = ctypes.wintypes.LPARAM
user32.GetMessageW.argtypes = [
    ctypes.POINTER(ctypes.wintypes.MSG),
    ctypes.wintypes.HWND,
    ctypes.wintypes.UINT,
    ctypes.wintypes.UINT,
]
user32.GetMessageW.restype = ctypes.wintypes.BOOL
user32.PostThreadMessageW.argtypes = [
    ctypes.wintypes.DWORD,
    ctypes.wintypes.UINT,
    ctypes.wintypes.WPARAM,
    ctypes.wintypes.LPARAM,
]
user32.PostThreadMessageW.restype = ctypes.wintypes.BOOL
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
kernel32.GetModuleHandleW.argtypes = [ctypes.wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = ctypes.wintypes.HMODULE
user32.keybd_event.argtypes = [
    ctypes.c_ubyte,
    ctypes.c_ubyte,
    ctypes.wintypes.DWORD,
    ctypes.c_void_p,
]
user32.keybd_event.restype = None


def get_active_modifiers() -> int:
    """Return a bitmask representing the currently held modifier keys.

    Returns:
        int: Bitmask of active modifier keys (MOD_CTRL, MOD_ALT, MOD_SHIFT).
    """
    mods = 0
    if user32.GetAsyncKeyState(VK_CONTROL) & 0x8000:
        mods |= MOD_CTRL
    if user32.GetAsyncKeyState(VK_MENU) & 0x8000:
        mods |= MOD_ALT
    if user32.GetAsyncKeyState(VK_SHIFT) & 0x8000:
        mods |= MOD_SHIFT
    return mods
