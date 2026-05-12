"""Linear Agent

Executes Linear System of Record operations via an injected LLM provider.

The agent owns:
  - the system prompt
  - the retry + validation loop
  - JSON extraction from the provider response

The agent does NOT own:
  - which provider to use
  - how auth is resolved
  - which model or MCP server to connect to
  - any hook wiring

All of that is the caller's responsibility. The caller constructs a
``BaseProvider`` and ``ProviderOptions`` and passes them in.

Public surface:
  - ``run_linear_agent(prompt, provider, options)``          → ``str | None``
  - ``run_validated_linear_agent(input, provider, options)`` → ``LinearOutput``
"""

import json
import logging

from pydantic import ValidationError

from linear.contracts import LinearInput, LinearOutput
from linear.prompts import INVALID_JSON, INVALID_OUTPUT, OPERATION_PROMPT
from llm_providers.base import BaseProvider
from llm_providers.protocol import Message, ProviderOptions
from utils.json import extract_json_object

logger = logging.getLogger(__name__)

MAX_VALIDATION_RETRIES = 3


async def run_linear_agent(
    prompt: str, provider: BaseProvider, options: ProviderOptions
) -> str | None:
    """Execute one Linear Agent turn. Returns the result string or None on failure.

    Streams ``Message`` objects from the provider:
      - Non-final messages: log text/tool activity for operator visibility.
      - Final message: extract result text.

    Raises ``RuntimeError`` on agent failure.
    """
    result_text: str | None = None

    async for msg in provider.query(prompt, options):
        msg: Message
        if not msg.is_final:
            if msg.text:
                logger.debug(msg.text)
            elif msg.raw is not None:
                for block in getattr(msg.raw, "content", []) or []:
                    if hasattr(block, "name") and not hasattr(block, "text"):
                        logger.debug("[TOOL] %s", block.name)
        else:
            result_text = msg.text or None

    return result_text


async def run_validated_linear_agent(
    input: LinearInput,
    provider: BaseProvider,
    options: ProviderOptions,
) -> LinearOutput:
    """Execute a Linear operation with retry and Pydantic output validation."""

    items_json = json.dumps(
        [item.model_dump(exclude_none=True) for item in input.items],
        indent=2,
    )
    project_ref = str(input.project.url or input.project.name)
    prompt = OPERATION_PROMPT.format(
        operation=input.operation.value,
        project=project_ref,
        item_count=len(input.items),
        items_json=items_json,
    )

    last_error: Exception | None = None

    for attempt in range(1, MAX_VALIDATION_RETRIES + 1):
        result_text = await run_linear_agent(prompt, provider, options)

        if result_text is None:
            logger.warning("Attempt %d: agent returned None result", attempt)
            continue

        try:
            raw = extract_json_object(result_text)
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning("Attempt %d: could not parse JSON: %s", attempt, e)
            last_error = e
            prompt += INVALID_JSON.format(error=e)
            continue

        try:
            output = LinearOutput.model_validate(raw)
            logger.info("Attempt %d: validation succeeded", attempt)
            return output
        except ValidationError as e:
            last_error = e
            logger.warning(
                "Attempt %d: LinearOutput validation failed:\n%s",
                attempt,
                e.json(indent=2),
            )
            prompt += INVALID_OUTPUT.format(errors=e.json(indent=2))

    raise ValueError(
        f"Linear Agent failed validation after {MAX_VALIDATION_RETRIES} attempts. "
        f"Last error: {last_error}"
    )
