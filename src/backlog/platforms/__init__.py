"""Backlog platform implementations."""

from backlog.platforms.base import BacklogPlatform
from backlog.platforms.linear import LINEAR_BACKLOG_TOOL_NAMES, LinearPlatform

SupportedPlatform = LinearPlatform

__all__ = [
    "LINEAR_BACKLOG_TOOL_NAMES",
    "BacklogPlatform",
    "LinearPlatform",
    "SupportedPlatform",
]
