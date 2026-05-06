"""Helpers for the WIO's Intelligence steps (Step 1 Enrich, Step 5 Store).

NOT a standalone agent class — the Intelligence Agent runs inline within the
WIO ``ClaudeSDKClient`` session (D-04, D-06). This module provides only prompt
builders. INTL-04: this module never imports from ``hsb.agents.linear_agent`` —
it does not initiate Linear writes.

G1 (OAuth2-only) is enforced at the SDK construction chokepoint
(:func:`hsb.agents._sdk_options.assert_oauth2_only`, called from
:func:`hsb.agents._sdk_options.make_options`). This module does NOT call the
SDK directly (it only builds prompt strings), so it has no module-top OAuth2
assertion. The previous plan revision had one and broke pytest collection
when ``ANTHROPIC_API_KEY`` was set in the developer environment for unrelated
reasons.
"""
from __future__ import annotations

import json as _json


def build_enrichment_prompt(work_item_id: str, work_item_json: str) -> str:
    """WIO Step 1 prompt — Knowledge Store retrieval (skill 10)."""
    return (
        f"Enrich work item {work_item_id} from the Knowledge Store before "
        "implementation. Apply skill 10 (knowledge-context-enrichment) "
        "retrieval rules. Use Glob and Grep over knowledge/ to find entries "
        "whose 'applicability' matches this work item's domain, technology, "
        "or pattern. Produce an Enrichment Report and store it as "
        "`knowledge_context` for the Builder step. Do NOT call any Linear "
        "MCP tool.\n\n"
        f"Work item context:\n{work_item_json}"
    )


def build_storage_prompt(qa_result: dict, implementation_notes: dict) -> str:
    """WIO Step 5 prompt — Knowledge Store write evaluation (skill 11)."""
    return (
        "Evaluate QA findings and implementation notes from this cycle. "
        "Apply skill 11 (knowledge-storage) ingestion criteria. Write "
        "Knowledge Store entries ONLY for insights that meet the signal "
        "threshold (recurring finding, architectural drift, reusable "
        "workaround, decision that should influence future work). Before "
        "writing each entry, use Grep to check the target category for "
        "near-duplicate titles; if found, skip and report "
        "`was_duplicate: true`. Every written entry MUST include all 8 "
        "required fields per KnowledgeStorageInput (title, type, context, "
        "evidence with linear_issue+pr+files, insight, recommendation, "
        "applicability, date). Do NOT call any Linear MCP tool.\n\n"
        f"QA result:\n{_json.dumps(qa_result, indent=2)}\n\n"
        f"Implementation notes:\n{_json.dumps(implementation_notes, indent=2)}"
    )
