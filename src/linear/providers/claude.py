"""Claude-specific hook wiring for the Linear Agent.

Wraps the hook functions from ``linear.providers.hooks`` in
``claude_agent_sdk.HookMatcher`` and assembles the ``LINEAR_HOOKS`` dict
expected by ``ProviderOptions.extras["claude"]["hooks"]``.

Import this module only when building options for the Claude provider.
"""

from claude_agent_sdk import HookMatcher

from linear.providers.hooks import (
    enforce_list_filters,
    linear_audit_hook,
    linear_retry_hook,
    pre_compact_handler,
)

LINEAR_HOOKS = {
    "PostToolUseFailure": [
        HookMatcher(matcher="^mcp__linear__", hooks=[linear_retry_hook])
    ],
    "PostToolUse": [HookMatcher(matcher="^mcp__linear__", hooks=[linear_audit_hook])],
    "PreCompact": [HookMatcher(hooks=[pre_compact_handler])],
    "PreToolUse": [
        HookMatcher(matcher="mcp__linear__list_issues", hooks=[enforce_list_filters])
    ],
}
