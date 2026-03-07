import re


def format_message(message: str) -> str:
    """Convert a raw bot message (Markdown-like text) to an HTML string.

    Args:
        message (str): The raw bot message text to format.

    Returns:
        str: HTML-formatted message string ready for a QLabel.
    """
    # Escape HTML special characters in the entire message first
    formatted = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Replace fenced code blocks with formatted HTML
    formatted = re.sub(r"```(.*?)```", _format_code_block, formatted, flags=re.DOTALL)

    # Format headers
    formatted = re.sub(
        r"^#####\s+(.+?)(<br>|$)", r"<h5>\1</h5>", formatted, flags=re.MULTILINE
    )
    formatted = re.sub(
        r"^####\s+(.+?)(<br>|$)", r"<h4>\1</h4>", formatted, flags=re.MULTILINE
    )
    formatted = re.sub(
        r"^###\s+(.+?)(<br>|$)", r"<h3>\1</h3>", formatted, flags=re.MULTILINE
    )
    formatted = re.sub(
        r"^##\s+(.+?)(<br>|$)", r"<h2>\1</h2>", formatted, flags=re.MULTILINE
    )
    formatted = re.sub(
        r"^#\s+(.+?)(<br>|$)", r"<h1>\1</h1>", formatted, flags=re.MULTILINE
    )

    # Replace **text** with <b>text</b>
    formatted = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", formatted)

    # Replace `inline code` with formatted HTML
    formatted = re.sub(r"`([^`\n]+)`", _format_inline_code, formatted)

    # Preserve leading spaces by converting them to &nbsp;
    formatted = re.sub(
        r"(?m)^( +)",
        lambda m: "&nbsp;" * len(m.group(1)),
        formatted,
    )

    # Replace newlines with <br> tags (but not adjacent to headings)
    formatted = re.sub(r"(?<!</h[1-5]>)\n(?!<h[1-5]>)", "<br>", formatted)

    return f"<div style='line-height: 1.4; white-space: pre-wrap;'>{formatted}</div>"


def _format_inline_code(match: re.Match[str]) -> str:
    """Format an inline code match with monospace styling.

    Args:
        match (re.Match): Regex match object containing the inline code.

    Returns:
        str: HTML-formatted inline code string.
    """
    code = match.group(1)
    return (
        f"<code style='font-family: monospace; "
        f"background-color: rgba(255, 255, 255, 26); "
        f"padding: 0.2em 0.4em; "
        f"border-radius: 3px;'>{code}</code>"
    )


def _format_code_block(match: re.Match[str]) -> str:
    """Format a fenced code block with syntax highlighting and styling.

    Args:
        match (re.Match): Regex match object containing the code block content.

    Returns:
        str: HTML-formatted code block string.
    """
    code = match.group(1)
    # Escape any HTML special characters inside the block
    code = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Colour comments in green
    code = re.sub(
        r"(#.*?)(?=\n|$)",
        r"<span style='color: #749852;'>\1</span>",
        code,
        flags=re.MULTILINE,
    )

    return (
        f"<div style='"
        "background-color: rgba(0, 0, 0, 26); "
        "color: rgba(255, 255, 255, 255); "
        "font-family: JetBrains Mono; "
        "font-size: 11pt; "
        "white-space: pre-wrap; "
        "word-wrap: break-word; "
        "word-break: break-word; "
        "tab-size: 4; "
        "-moz-tab-size: 4; "
        "text-align: left;"
        "'>"
        f"<span style='white-space: pre-wrap;'>{code}</span>"
        "</div>"
    )
