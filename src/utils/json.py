"""JSON utility helpers."""

import json


def extract_json_object(text: str) -> dict[str, object]:
    """Extract the first JSON object from a string.

    Finds the outermost ``{...}`` block and parses it.

    Raises ``ValueError`` if no braces are found.
    Raises ``json.JSONDecodeError`` if the extracted block is not valid JSON.
    """
    start = text.index("{")
    depth = 0
    in_string = False
    escape = False
    for i, ch in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        if in_string:
            if ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                result: dict[str, object] = json.loads(text[start : i + 1])
                return result
    raise ValueError("No complete JSON object found in string")
