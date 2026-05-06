"""INTL-03 schema completeness + applicability constraint tests."""
import pytest
from pydantic import ValidationError

from hsb.contracts.knowledge import (
    KnowledgeEnrichmentOutput,
    KnowledgeStorageInput,
    KnowledgeStorageOutput,
)

VALID_INPUT = dict(
    title="Use jose, not jsonwebtoken, for Edge runtime",
    type="qa",
    context="Builder picked jsonwebtoken which fails on Edge runtime",
    evidence={
        "linear_issue": "LIN-123",
        "pr": "https://github.com/owner/repo/pull/45",
        "files": ["src/auth.ts"],
        "qa_finding": "build error on edge runtime",
    },
    insight="jose is Edge-runtime compatible; jsonwebtoken is CommonJS-only",
    recommendation="Use jose for any JWT signing in Edge runtime contexts",
    applicability="Next.js Edge runtime contexts using JWT",
    date="2026-05-06",
)


def test_valid_input_parses():
    m = KnowledgeStorageInput(**VALID_INPUT)
    assert m.title == VALID_INPUT["title"]


def test_knowledge_storage_input_rejects_all_tasks_applicability():
    bad = {**VALID_INPUT, "applicability": "all tasks"}
    with pytest.raises(ValidationError) as exc:
        KnowledgeStorageInput(**bad)
    assert "applicability" in str(exc.value).lower()


@pytest.mark.parametrize(
    "bad_value",
    ["", "  ", "all tasks", "All Tasks", "ALL", "n/a", "tbd"],
)
def test_knowledge_storage_input_rejects_empty_or_filler_applicability(bad_value):
    bad = {**VALID_INPUT, "applicability": bad_value}
    with pytest.raises(ValidationError):
        KnowledgeStorageInput(**bad)


def test_knowledge_storage_input_forbids_extra_fields():
    bad = {**VALID_INPUT, "rogue_field": "x"}
    with pytest.raises(ValidationError):
        KnowledgeStorageInput(**bad)


def test_knowledge_storage_input_rejects_invalid_type_literal():
    bad = {**VALID_INPUT, "type": "bogus"}
    with pytest.raises(ValidationError):
        KnowledgeStorageInput(**bad)


def test_knowledge_enrichment_output_parses_and_forbids_extras():
    m = KnowledgeEnrichmentOutput(
        work_item_id="LIN-1",
        enrichment_report={"summary": "x"},
        retrieved_entries=["knowledge/qa/2026-05-06-foo.md"],
    )
    assert m.work_item_id == "LIN-1"
    with pytest.raises(ValidationError):
        KnowledgeEnrichmentOutput(
            work_item_id="LIN-1",
            enrichment_report={},
            retrieved_entries=[],
            rogue="x",
        )


def test_knowledge_storage_output_parses_all_four_fields():
    m = KnowledgeStorageOutput(
        stored=True,
        location="knowledge/qa/2026-05-06-foo.md",
        entry_id="2026-05-06-foo",
        was_duplicate=False,
    )
    assert m.stored is True
