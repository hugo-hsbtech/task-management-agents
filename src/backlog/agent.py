"""Provider-agnostic backlog agent."""

import asyncio
import json

from pydantic import ValidationError

from backlog.contracts import BacklogInput, BacklogOutput
from backlog.platforms.linear import IssueResult
from backlog.prompts import BACKLOG_SYSTEM_PROMPT, BACKLOG_USER_PROMPT_TEMPLATE
from llm_providers import ApiKey, OAuth2CliToken, ProviderOptions, ProviderRegistry
from llm_providers.auth.base import AuthStrategy
from llm_providers.base import BaseProvider
from llm_providers.prompt import TextSystemPrompt
from llm_providers.tools import ToolPolicy
from settings import (
    ApiKeyAuth,
    OAuth2ADCAuth,
    OAuth2CliAuth,
    ProviderSettings,
    settings,
)
from utils.json import extract_json_object
from utils.prompt import build_prompt, to_json

MAX_VALIDATION_RETRIES = 3
DEFAULT_MAX_TURNS = 3


class BacklogAgent:
    """Provider-agnostic backlog agent with explicit runtime state."""

    def __init__(
        self,
        *,
        provider_settings: ProviderSettings | None = None,
        provider: BaseProvider | None = None,
        tool_policy: ToolPolicy | None = None,
        max_validation_retries: int = MAX_VALIDATION_RETRIES,
        max_turns: int = DEFAULT_MAX_TURNS,
    ) -> None:
        self.provider_settings = provider_settings or settings.provider
        self.provider = provider or build_provider(self.provider_settings)
        self.tool_policy = tool_policy
        self.max_validation_retries = max_validation_retries
        self.max_turns = max_turns

    async def run(self, input_contract: BacklogInput) -> BacklogOutput:
        """Generate backlog issues with this agent's configured provider."""

        options = self.make_provider_options(input_contract)
        prompt = build_prompt(
            BACKLOG_USER_PROMPT_TEMPLATE,
            output_schema=to_json(BacklogOutput.model_json_schema()),
            platform=to_json(input_contract.platform.model_dump(mode="json")),
            platform_defaults=to_json(input_contract.platform.issue_defaults()),
            plan_content=to_json(input_contract.plan_content),
            stacks=to_json(input_contract.stacks),
            platform_name=to_json(input_contract.platform.platform_name),
            context=to_json(input_contract.context),
        )

        last_error: Exception | None = None
        for _attempt in range(1, self.max_validation_retries + 1):
            final_text = ""
            async for message in self.provider.query(prompt, options):  # type: ignore[attr-defined]
                if message.is_final:
                    final_text = message.text

            if not final_text:
                last_error = ValueError("provider returned no final message")
                continue

            try:
                raw = extract_json_object(final_text)
                raw.setdefault(
                    "platform",
                    input_contract.platform.model_dump(mode="json"),
                )
                output = BacklogOutput.model_validate(raw)
                return self.with_platform_defaults(output, input_contract)
            except (ValueError, json.JSONDecodeError, ValidationError) as exc:
                last_error = exc

        raise ValueError(
            f"Backlog agent failed validation after "
            f"{self.max_validation_retries} attempts: {last_error}"
        )

    def run_sync(self, input_contract: BacklogInput) -> BacklogOutput:
        """Synchronous entry point for this agent instance."""

        return asyncio.run(self.run(input_contract))

    async def create_issues(self, output: BacklogOutput) -> list[IssueResult]:
        """Apply a planned backlog output to the platform via the platform protocol."""

        api_key = self._require_platform_api_key()
        return await output.platform.execute(output, api_key=api_key)

    async def run_and_create(
        self,
        input_contract: BacklogInput,
    ) -> tuple[BacklogOutput, list[IssueResult]]:
        """Generate backlog output, then create/reuse issues in the platform."""

        output = await self.run(input_contract)
        created = await self.create_issues(output)
        return output, created

    def create_issues_sync(self, output: BacklogOutput) -> list[IssueResult]:
        """Synchronous issue creation entry point for this agent instance."""

        return asyncio.run(self.create_issues(output))

    def run_and_create_sync(
        self,
        input_contract: BacklogInput,
    ) -> tuple[BacklogOutput, list[IssueResult]]:
        """Synchronously generate backlog output and create/reuse platform issues."""

        return asyncio.run(self.run_and_create(input_contract))

    def make_provider_options(self, input_contract: BacklogInput) -> ProviderOptions:
        return ProviderOptions(
            system_prompt=TextSystemPrompt(BACKLOG_SYSTEM_PROMPT),
            model=str(self.provider_settings.model),
            max_turns=self.max_turns,
            tool_policy=self.tool_policy or self.build_tool_policy(input_contract),
            output_schema=BacklogOutput.model_json_schema(),
            extras={
                "backlog": {
                    "platform": input_contract.platform.platform_name,
                    "stacks": tuple(input_contract.stacks),
                }
            },
        )

    def build_tool_policy(self, input_contract: BacklogInput) -> ToolPolicy:
        api_key = self._require_platform_api_key()
        return input_contract.platform.tool_policy(api_key=api_key)

    def _require_platform_api_key(self) -> str:
        api_key_secret = settings.linear.api_key
        if api_key_secret is None:
            raise ValueError(
                "Platform API key required: set LINEAR_API_KEY in settings.linear"
            )
        return api_key_secret.get_secret_value()

    @staticmethod
    def with_platform_defaults(
        output: BacklogOutput,
        input_contract: BacklogInput,
    ) -> BacklogOutput:
        defaults = input_contract.platform.issue_defaults()
        normalized = output.model_copy(deep=True)
        normalized.platform = input_contract.platform
        for issue in normalized.issues:
            issue.fields.platform_fields = {
                **defaults,
                **issue.fields.platform_fields,
            }
        return normalized


def build_provider(provider_settings: ProviderSettings | None = None) -> BaseProvider:
    """Build the configured LLM provider without reading env vars in this module."""

    provider_settings = provider_settings or settings.provider
    auth = _auth_from_settings(provider_settings)
    return ProviderRegistry.build(provider_settings.name.value, auth=auth)


async def run_backlog_agent_async(
    input_contract: BacklogInput,
    *,
    provider_settings: ProviderSettings | None = None,
    provider: BaseProvider | None = None,
    tool_policy: ToolPolicy | None = None,
) -> BacklogOutput:
    """Generate backlog issues with the configured LLM provider."""

    agent = BacklogAgent(
        provider_settings=provider_settings,
        provider=provider,
        tool_policy=tool_policy,
    )
    return await agent.run(input_contract)


def run_backlog_agent(
    input_contract: BacklogInput,
    *,
    provider_settings: ProviderSettings | None = None,
    provider: BaseProvider | None = None,
    tool_policy: ToolPolicy | None = None,
) -> BacklogOutput:
    """Synchronous entry point for backlog generation."""

    agent = BacklogAgent(
        provider_settings=provider_settings,
        provider=provider,
        tool_policy=tool_policy,
    )
    return agent.run_sync(input_contract)


def _auth_from_settings(provider_settings: ProviderSettings) -> AuthStrategy:
    auth = provider_settings.auth
    if isinstance(auth, ApiKeyAuth):
        return ApiKey.from_auth(auth)
    if isinstance(auth, OAuth2CliAuth):
        return OAuth2CliToken.from_settings(auth)
    if isinstance(auth, OAuth2ADCAuth):
        raise ValueError("oauth2_adc auth is not wired in llm_providers yet")
    raise TypeError(f"Unsupported auth settings type: {type(auth).__name__}")
