---
name: pydantic-ai-agents
description: PydanticAI agent patterns for structured output reliability — Field descriptions, Literal types, retries, optional defaults, and schema design. Use when creating or modifying PydanticAI agents, defining output_type schemas, or debugging structured output validation failures.
---

# PydanticAI Agent Patterns

Patterns for building reliable PydanticAI agents with structured output in the Ezra platform.

## When to Activate

- Creating a new PydanticAI `Agent` with `output_type`
- Defining Pydantic `BaseModel` schemas used as agent output types
- Debugging `UnexpectedModelBehavior: Exceeded maximum retries for output validation`
- Reviewing agent code that uses structured output

## Core Rules

### 1. Every field MUST have a `Field(description=...)`

PydanticAI serializes the output schema as a tool definition for the LLM. Bare fields like `name: str` produce a JSON schema with no context — the model has to guess what goes where from the system prompt alone. Field descriptions are injected directly into the tool schema.

```python
# BAD — the LLM sees {"name": {"type": "string"}} with no guidance
class ScanResult(BaseModel):
    name: str
    signal: str

# GOOD — the LLM sees descriptions in the tool schema
class ScanResult(BaseModel):
    name: str = Field(description="Company name in clean proper case")
    signal: str = Field(description="Funding amounts, contracts, partnerships. Be specific.")
```

### 2. Use `Literal` for constrained string fields

Bare `str` fields for values like confidence levels or categories force the LLM to remember valid values from the prompt. `Literal` types embed the valid options directly in the schema.

```python
# BAD — model might return "High", "HIGH", "very high", "h", etc.
confidence: str

# GOOD — schema enforces valid values, validation catches mistakes
Confidence = Literal["high", "medium", "low"]
confidence: Confidence = Field(description="How confident the assessment is")
```

Define `Literal` types as module-level aliases for reuse and readability.

### 3. Set `retries=3` on every Agent

The default `retries=1` means the model gets one shot at self-correction after a validation failure. For structured output with multiple fields, that's not enough.

```python
agent = Agent(
    model=settings.model_name,
    output_type=MyResult,
    system_prompt=system_prompt,
    instrument=build_pydantic_ai_instrumentation(),
    retries=3,
)
```

### 4. Use `default=""` or `| None` for fields that may not apply

If a field only applies conditionally (e.g., `disqualification_reason` only matters when `qualified=false`), make it optional. Required fields with no valid value cause the LLM to hallucinate filler.

```python
# BAD — model forced to produce a reason even for qualified companies
disqualification_reason: str

# GOOD — empty default when the field doesn't apply
disqualification_reason: str = Field(
    default="",
    description="If qualified=false, the specific reason. Empty string if qualified."
)
```

Use `default=""` when downstream code uses `value or ""` (string context). Use `| None` with `default=None` when downstream code checks `if value is not None`.

### 5. List wrapper fields need descriptions too

When the output type wraps a list, describe what the list contains and any constraints.

```python
class ScanResult(BaseModel):
    companies: list[DiscoveredCompany] = Field(
        description="List of extracted companies from the search results"
    )
```

### 6. Keep output schemas flat when possible

Deeply nested schemas increase the chance of validation errors. If a nested model only has 2-3 fields, consider flattening into the parent.

### 7. Match field names to prompt terminology

If the prompt says "estimated financing need", name the field `est_financing_need`, not `financing_estimate` or `need_amount`. The LLM maps between prompt language and field names — minimize that distance.

### 8. Don't duplicate the prompt in Field descriptions

Field descriptions should be concise schema-level hints, not copies of the system prompt. The prompt provides context and reasoning; the field description tells the model what format/content goes in that specific field.

## Agent Construction Checklist

When creating or reviewing a PydanticAI agent, verify:

- [ ] `retries=3` is set on the Agent
- [ ] `instrument=build_pydantic_ai_instrumentation()` is set (per `ezra-llm-integration` skill)
- [ ] Every field on the output BaseModel has `Field(description=...)`
- [ ] Constrained-value string fields use `Literal` types
- [ ] Conditionally-applicable fields have defaults (`default=""` or `default=None`)
- [ ] Field names align with prompt terminology
- [ ] Output schema is as flat as practical

## Debugging Validation Failures

When you see `UnexpectedModelBehavior: Exceeded maximum retries for output validation`:

1. Check which field failed validation in the Pydantic error (look for `Field required` or `type=missing`)
2. Add or improve the `Field(description=...)` for that field
3. If the field is sometimes inapplicable, add a default
4. If the field has constrained values, switch to `Literal`
5. Increase `retries` if not already at 3
6. Check that the system prompt's output section matches the schema field names
