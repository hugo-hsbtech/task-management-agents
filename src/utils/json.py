"""JSON utility helpers."""

import json


def extract_json_object(text: str) -> dict:
    """Extract the first JSON object from a string.

    Finds the outermost ``{...}`` block and parses it.

    Raises ``ValueError`` if no braces are found.
    Raises ``json.JSONDecodeError`` if the extracted block is not valid JSON.
    """
    start = text.index("{")
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("No complete JSON object found in string")
