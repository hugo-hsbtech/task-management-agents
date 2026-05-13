"""llm_providers — decoupled multi-provider LLM library.

Public surface re-exported below. Importing this package also triggers
provider and auth-strategy registration as a side effect.
"""

# Side-effect imports — must come before public-surface re-exports so the
# registries are populated when downstream code reads them.
from llm_providers import (
    auth,  # noqa: F401  (registers strategies if any)
    providers,  # noqa: F401  (registers Claude + OpenAI)
)
from llm_providers.auth import ApiKey, AuthStrategy, Credential, OAuth2CliToken
from llm_providers.auth.factory import resolve_auth
from llm_providers.base import BaseProvider, StatefulClient
from llm_providers.errors import (
    AuthDetectionFailed,
    AuthResolutionError,
    ClaudeAuthError,
    ClaudeRateLimitError,
    CredentialMismatch,
    LLMProvidersError,
    ProviderNotFoundError,
    ProviderRuntimeError,
    TranslationError,
    UnsupportedAuthError,
    UnsupportedCapabilityError,
)
from llm_providers.prompt import (
    PresetSystemPrompt,
    SkillReference,
    SystemPrompt,
    TextSystemPrompt,
)
from llm_providers.protocol import (
    Capabilities,
    Message,
    PermissionMode,
    ProviderOptions,
)
from llm_providers.registry import (
    AuthRegistry,
    ProviderRegistry,
)
from llm_providers.tools import McpServerSpec, ToolPolicy, ToolSpec

__all__ = [
    # Auth
    "ApiKey",
    "AuthStrategy",
    "Credential",
    "OAuth2CliToken",
    # Base
    "BaseProvider",
    "StatefulClient",
    # Errors
    "AuthDetectionFailed",
    "AuthResolutionError",
    "ClaudeAuthError",
    "ClaudeRateLimitError",
    "CredentialMismatch",
    "LLMProvidersError",
    "ProviderNotFoundError",
    "ProviderRuntimeError",
    "TranslationError",
    "UnsupportedAuthError",
    "UnsupportedCapabilityError",
    # Prompt
    "PresetSystemPrompt",
    "SkillReference",
    "SystemPrompt",
    "TextSystemPrompt",
    # Protocol
    "Capabilities",
    "Message",
    "PermissionMode",
    "ProviderOptions",
    # Registry
    "AuthRegistry",
    "ProviderRegistry",
    "resolve_auth",
    # Tools
    "McpServerSpec",
    "ToolPolicy",
    "ToolSpec",
]
