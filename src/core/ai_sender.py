import mimetypes
import os
import threading
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.chats import Chat


MODEL = "gemini-3-flash-preview"
CONFIG = types.GenerateContentConfig(
    thinking_config=types.ThinkingConfig(
        thinking_budget=0
    )  # Disable thinking mode for faster responses
)


class AISender:
    """Handles sending user input to Gemini via a persistent chat session."""

    def __init__(self) -> None:
        # Load environment variables from the .env file
        base_dir = Path(__file__).resolve().parent.parent.parent
        load_dotenv(base_dir / ".env")

        # Initialize Gemini client and start a chat session
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.chat = self._create_chat()

    def reset_chat(self) -> None:
        """Reset the chat session, clearing all conversation history."""
        self.chat = self._create_chat()

    def send_message(
        self,
        user_input: str,
        attachments: list[str] | None = None,
        on_chunk: Callable[[str], None] | None = None,
        stop_flag: threading.Event | None = None,
    ) -> str:
        """Send a message and stream the response from the Gemini model.

        Args:
            user_input (str): The user's input text to send to the model.
            attachments (list[str], optional): List of file paths to attach to the request.
            on_chunk (callable, optional): Callback invoked with each text chunk as it streams.
            stop_flag (threading.Event, optional): When set, the stream is aborted immediately.

        Returns:
            str: The full generated response text.
        """
        # Build message parts from attachments
        message: list[types.Part | str] = []
        for filepath in attachments or []:
            mime_type = mimetypes.guess_type(filepath)[0] or "application/octet-stream"
            with open(filepath, "rb") as f:
                message.append(
                    types.Part.from_bytes(data=f.read(), mime_type=mime_type)
                )
        message.append(user_input)

        full_response = ""
        for chunk in self.chat.send_message_stream(message):
            # Break early if cancelled — closing the iterator shuts down the HTTP stream
            if stop_flag is not None and stop_flag.is_set():
                break
            if chunk.text:
                full_response += chunk.text
                print(chunk.text, end="", flush=True)
                if on_chunk is not None:
                    try:
                        on_chunk(chunk.text)
                    except Exception:
                        pass

        return full_response

    def _create_chat(self) -> Chat:
        """Create a new Gemini chat session.

        Returns:
            Chat: A new chat session instance.
        """
        return self.client.chats.create(model=MODEL, config=CONFIG)
