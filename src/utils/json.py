"""JSON utility helpers."""

import json


def extract_json_object(text: str) -> dict:
    """Extract the first JSON object from a string.

    Finds the outermost ``{...}`` block and parses it.

    Raises ``ValueError`` if no braces are found.
    Raises ``json.JSONDecodeError`` if the extracted block is not valid JSON.
    """
    start = text.index("{")
    end = text.rindex("}") + 1
    return json.loads(text[start:end])
