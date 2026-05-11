"""SystemPrompt sum-type shape tests."""

from pathlib import Path

import pytest

from llm_providers.prompt import (
    PresetSystemPrompt,
    SkillReference,
    SystemPrompt,
    TextSystemPrompt,
)


def test_all_three_subclass_systemprompt():
    assert issubclass(TextSystemPrompt, SystemPrompt)
    assert issubclass(SkillReference, SystemPrompt)
    assert issubclass(PresetSystemPrompt, SystemPrompt)


def test_text_is_frozen():
    p = TextSystemPrompt(text="hi")
    with pytest.raises(Exception):  # noqa: B017
        p.text = "x"  # type: ignore[misc]


def test_skill_reference_holds_path_and_optional_locator(tmp_path):
    p = SkillReference(path=tmp_path / "skill.md")
    assert p.path == tmp_path / "skill.md"
    assert p.locator is None
    p2 = SkillReference(path=Path("/tmp/x.md"), locator=".claude/skills/foo/SKILL.md")
    assert p2.locator == ".claude/skills/foo/SKILL.md"


def test_preset_holds_id():
    p = PresetSystemPrompt(preset_id="my-preset")
    assert p.preset_id == "my-preset"
