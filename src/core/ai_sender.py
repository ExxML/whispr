import mimetypes
import os
import threading
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv
from google import genai
from google.genai import types


MODELS: list[tuple[str, str]] = [
    ("Gemini 2.5 Flash Lite", "gemini-2.5-flash-lite"),
    ("Gemini 2.5 Flash", "gemini-2.5-flash"),
    ("Gemini 3 Flash Preview", "gemini-3-flash-preview"),
]  # Format: (<display name>, <model ID>)
DEFAULT_MODEL = MODELS[2][1]
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

        # Initialize Gemini client and history
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = DEFAULT_MODEL
        self.history: list[types.Content] = []

    def set_model(self, model_id: str) -> None:
        """Set the active Gemini model.

        Args:
            model_id (str): The model identifier string.
        """
        self.model = model_id

    def reset_chat(self) -> None:
        """Reset the chat session, clearing all conversation history."""
        self.history = []

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
        # Build user message parts from attachments and text
        parts: list[types.Part] = []
        for filepath in attachments or []:
            mime_type = mimetypes.guess_type(filepath)[0] or "application/octet-stream"
            with open(filepath, "rb") as f:
                parts.append(types.Part.from_bytes(data=f.read(), mime_type=mime_type))
        parts.append(types.Part.from_text(text=user_input))

        user_content = types.Content(role="user", parts=parts)
        contents = self.history + [user_content]

        full_response = ""
        for chunk in self.client.models.generate_content_stream(
            model=self.model,
            contents=contents,
            config=CONFIG,
        ):
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

        # Only persist the exchange to history if we were not cancelled mid-stream.
        # Store the model turn as a single merged text part (matching what the API
        # returns in non-streaming mode) rather than one part per streaming chunk.
        if full_response and (stop_flag is None or not stop_flag.is_set()):
            self.history.append(user_content)
            self.history.append(
                types.Content(
                    role="model", parts=[types.Part.from_text(text=full_response)]
                )
            )

        return full_response
