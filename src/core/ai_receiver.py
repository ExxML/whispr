import threading

from PyQt6.QtCore import QObject, pyqtSignal

from core.ai_sender import AISender
from ui.chat.chat_area import ChatArea


class AIReceiver(QObject):
    """Handles AI response streaming and chat area updates."""

    # Signals for cross-thread communication
    # Using threading instead of QThread due to compilation issues with Nuitka
    # Each signal carries a stream_id so stale signals from superseded streams are ignored
    finished = pyqtSignal(int)
    error = pyqtSignal(str, int)
    progress = pyqtSignal(str, int)

    def __init__(self, ai_sender: AISender, chat_area: ChatArea) -> None:
        super().__init__()
        self.ai_sender = ai_sender
        self.chat_area = chat_area
        self.ai_thread: threading.Thread | None = None
        self.stop_flag = threading.Event()  # Stop flag for the currently running stream
        self.stream_id: int = (
            0  # Incremented on each new stream; used to discard stale queued signals
        )
        self.message: str | None = None
        self.attachments: list[str] | None = None

        # Connect signals to response handlers once
        self.progress.connect(self._on_response_chunk)
        self.finished.connect(self._on_response_ready)
        self.error.connect(self._on_response_error)

    def handle_message(
        self, message: str, attachments: list[str] | None = None
    ) -> None:
        """Handle a user message by displaying it and starting AI generation.

        Args:
            message (str): The user's message text.
            attachments (list[str], optional): List of file paths to attach to the request.
        """
        # Stop the current stream and finalize any in-progress bubble
        self.stop_flag.set()
        if self.chat_area.streaming_bubble is not None:
            self.chat_area.finalize_assistant_stream()

        # Advance stream_id so any signals already queued from the old stream are ignored
        self.stream_id += 1
        current_id = self.stream_id

        # Fresh stop flag for the new stream; capture locally so the thread always
        # checks its own flag even if self.stop_flag is later replaced
        self.stop_flag = threading.Event()
        local_flag = self.stop_flag

        self.message = message
        self.attachments = attachments

        # Immediately add user's message to the chat area
        self.chat_area.add_message(message, is_user=True)

        # Start new thread
        self.ai_thread = threading.Thread(
            target=self._run, args=(current_id, local_flag), daemon=True
        )
        self.ai_thread.start()

    def stop(self) -> None:
        """Signal the current stream to stop and invalidate any queued signals."""
        self.stop_flag.set()
        self.stream_id += (
            1  # Discard any progress/finished/error signals already queued
        )

    def _run(self, stream_id: int, stop_flag: threading.Event) -> None:
        """Execute AI content generation and emit progress and completion signals.

        Args:
            stream_id (int): The generation ID for this stream invocation.
            stop_flag (threading.Event): The cancellation flag for this stream.
        """
        assert self.message is not None
        try:
            self.ai_sender.send_message(
                self.message,
                self.attachments,
                lambda text: self._on_chunk(text, stream_id, stop_flag),
                stop_flag,
            )
            # Only emit finished if we weren't stopped
            if not stop_flag.is_set():
                self.finished.emit(stream_id)

        except Exception as e:
            # Only emit error if we weren't stopped
            if not stop_flag.is_set():
                self.error.emit(str(e), stream_id)

    def _on_chunk(self, text: str, stream_id: int, stop_flag: threading.Event) -> None:
        """Handle a streamed text chunk by emitting it to the UI thread.

        Args:
            text (str): The text chunk received from the AI stream.
            stream_id (int): The generation ID for this stream invocation.
            stop_flag (threading.Event): The cancellation flag for this stream.
        """
        if text and not stop_flag.is_set():
            self.progress.emit(text, stream_id)

    def _on_response_ready(self, stream_id: int) -> None:
        """Handle successful AI response.

        Args:
            stream_id (int): The generation ID of the completed stream.
        """
        if stream_id != self.stream_id:
            return
        self.chat_area.finalize_assistant_stream()

    def _on_response_error(self, error: str, stream_id: int) -> None:
        """Handle AI response error.

        Args:
            error (str): The error message from the AI response.
            stream_id (int): The generation ID of the stream that errored.
        """
        if stream_id != self.stream_id:
            return
        error_msg = f"Error generating response: {error}"
        self.chat_area.show_stream_error(error_msg)

    def _on_response_chunk(self, chunk: str, stream_id: int) -> None:
        """Stream chunk text into the current assistant bubble.

        Args:
            chunk (str): Text chunk from the AI response stream.
            stream_id (int): The generation ID that emitted this chunk.
        """
        if stream_id != self.stream_id:
            return
        # Lazily create the assistant bubble only when first chunk arrives
        if self.chat_area.streaming_bubble is None:
            self.chat_area.start_assistant_stream()
        self.chat_area.append_to_stream(chunk)
