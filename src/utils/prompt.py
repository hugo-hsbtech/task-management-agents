"""Generic prompt building and introspection utilities."""

import json
from string import Formatter


def build_prompt(template: str, **kwargs: object) -> str:
    """Format *template* with *kwargs*, validate the result as JSON, and return it."""
    prompt = template.format(**kwargs)
    json.loads(prompt)
    return prompt


def prompt_template_fields(template: str) -> set[str]:
    """Return the named format fields present in *template*."""
    return {
        field_name for _, field_name, _, _ in Formatter().parse(template) if field_name
    }


def to_json(value: object) -> str:
    """Serialize *value* to a compact, deterministic JSON string."""
    return json.dumps(value, ensure_ascii=True, sort_keys=True)
