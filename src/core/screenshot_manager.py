import glob
import os

import mss
from PyQt6.QtCore import QObject, pyqtSignal


class ScreenshotManager(QObject):
    """Handles capturing screenshots of the primary screen."""

    screenshot_added = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        base_dir = os.getcwd()
        self.screenshots_dir = os.path.join(
            base_dir, "src", "data", "cache", "screenshots"
        )
        os.makedirs(self.screenshots_dir, exist_ok=True)  # Ensure the folder exists
        self.screenshot_count = 0
        self.pending_paths: list[str] = []

    def take_screenshot(self) -> str:
        """Take a screenshot of the primary screen and save it to the screenshots directory.

        Returns:
            str: The filepath of the saved screenshot, or an empty string on failure.
        """
        try:
            filename = f"screenshot{self.screenshot_count}.png"
            filepath = os.path.join(self.screenshots_dir, filename)

            # Create a new mss instance for each call (thread-safe)
            with mss.mss() as sct:
                # Screenshot the primary monitor
                monitor = sct.monitors[1]  # 0 is all monitors, 1 is primary
                screenshot = sct.grab(monitor)
                mss.tools.to_png(screenshot.rgb, screenshot.size, output=str(filepath))

            self.screenshot_count += 1
            self.pending_paths.append(filepath)
            self.screenshot_added.emit(filepath)
            return filepath

        except Exception as e:
            print(f"Error taking screenshot: {str(e)}")
            return ""

    def get_and_clear_pending(self) -> list[str]:
        """Return all pending screenshot paths and clear the pending list.

        Returns:
            list[str]: The list of pending screenshot file paths.
        """
        paths = self.pending_paths.copy()
        self.pending_paths.clear()
        return paths

    def remove_pending(self, path: str) -> None:
        """Remove a specific screenshot from the pending list.

        Args:
            path (str): The file path of the screenshot to remove.
        """
        if path in self.pending_paths:
            self.pending_paths.remove(path)

    def clear_screenshots(self) -> None:
        """Delete all screenshots from the screenshots directory and reset the counter."""
        self.pending_paths.clear()

        try:
            pattern = os.path.join(self.screenshots_dir, "screenshot*.png")
            for filepath in glob.glob(pattern):
                os.remove(filepath)
        except Exception as e:
            print(f"Error clearing screenshots: {str(e)}")

        self.screenshot_count = 0
