"""ProviderRegistry + AuthRegistry.

Decorator-based registries: subclasses self-register at class definition
time via ``@ProviderRegistry.register("name")`` and
``@AuthRegistry.register("kind")``. Open for extension (one decorator),
closed for modification (no edits to registry.py to add a provider).

The walk-and-detect ``auto_resolve_auth`` flow has been removed — auth
resolution is now strict-direct via
:func:`llm_providers.auth.factory.resolve_auth`, which maps a
(provider, auth_kind) pair to exactly one credential source.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from libs.logging import get_logger
from llm_providers.auth.base import AuthStrategy
from llm_providers.base import BaseProvider
from llm_providers.errors import ProviderNotFoundError

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)


class ProviderRegistry:
    """Registry of BaseProvider subclasses keyed by their `name` ClassVar."""

    _providers: ClassVar[dict[str, type[BaseProvider]]] = {}

    @classmethod
    def register(cls, name: str) -> Callable[[type[BaseProvider]], type[BaseProvider]]:
        def decorator(provider_cls: type[BaseProvider]) -> type[BaseProvider]:
            if not issubclass(provider_cls, BaseProvider):
                raise TypeError(
                    f"{provider_cls.__name__} must subclass BaseProvider to be "
                    "registered."
                )
            if name in cls._providers:
                raise ValueError(
                    f"Provider {name!r} is already registered by "
                    f"{cls._providers[name].__name__}; refusing to overwrite."
                )
            declared = provider_cls.__dict__.get("name")
            if declared is None:
                # Class did not set `name` itself; adopt the decorator name as
                # the single source of truth.
                provider_cls.name = name
            elif declared != name:
                raise ValueError(
                    f"Decorator name={name!r} != class.name={declared!r}. "
                    "Both sources of truth must match."
                )
            cls._providers[name] = provider_cls
            logger.debug("provider.registered", name=name, cls=provider_cls.__name__)
            return provider_cls

        return decorator

    @classmethod
    def get(cls, name: str) -> type[BaseProvider]:
        try:
            return cls._providers[name]
        except KeyError:
            raise ProviderNotFoundError(
                name=name, available=tuple(sorted(cls._providers))
            ) from None

    @classmethod
    def build(cls, name: str, *, auth: AuthStrategy) -> BaseProvider:
        """Construct a provider with an already-resolved auth strategy."""
        return cls.get(name)(auth=auth)

    @classmethod
    def build_from_settings(cls, name: str, *, auth_kind: str) -> BaseProvider:
        """Construct a provider, resolving its credential from settings.

        Strict-direct: ``(name, auth_kind)`` must match a row in the
        :func:`llm_providers.auth.factory.resolve_auth` matrix. Missing
        credentials raise ``AuthResolutionError`` with a message naming
        the env var or file the operator must set.

        Provider name is validated first, so a bogus name surfaces as
        ``ProviderNotFoundError`` rather than an ``AuthResolutionError`` —
        the caller's diagnostic is clearer that way.
        """
        provider_cls = cls.get(name)
        # Lazy import — factory pulls settings, which we don't want loaded
        # at module import time.
        from llm_providers.auth.factory import resolve_auth

        auth = resolve_auth(name, auth_kind)
        return provider_cls(auth=auth)

    @classmethod
    def names(cls) -> tuple[str, ...]:
        return tuple(sorted(cls._providers))


class AuthRegistry:
    """Registry of AuthStrategy subclasses keyed by their `kind` ClassVar."""

    _strategies: ClassVar[dict[str, type[AuthStrategy]]] = {}

    @classmethod
    def register(cls, kind: str) -> Callable[[type[AuthStrategy]], type[AuthStrategy]]:
        def decorator(strat_cls: type[AuthStrategy]) -> type[AuthStrategy]:
            # Name-based MRO check rather than ``issubclass``: when callers
            # evict ``llm_providers.auth.base`` from ``sys.modules`` (the test
            # suite does this to exercise reload behavior), ``AuthStrategy``'s
            # class identity changes but registry.py's import is cached, so a
            # direct ``issubclass`` returns False against the stale reference.
            if not any(c.__name__ == "AuthStrategy" for c in strat_cls.__mro__):
                raise TypeError(
                    f"{strat_cls.__name__} must subclass AuthStrategy to be registered."
                )
            if kind in cls._strategies:
                raise ValueError(
                    f"AuthStrategy {kind!r} is already registered by "
                    f"{cls._strategies[kind].__name__}; refusing to overwrite."
                )
            declared = getattr(strat_cls, "kind", None)
            if declared != kind:
                raise ValueError(
                    f"Decorator kind={kind!r} != class.kind={declared!r}. "
                    "Both sources of truth must match."
                )
            cls._strategies[kind] = strat_cls
            logger.debug("auth.strategy_registered", kind=kind, cls=strat_cls.__name__)
            return strat_cls

        return decorator

    @classmethod
    def get(cls, kind: str) -> type[AuthStrategy]:
        try:
            return cls._strategies[kind]
        except KeyError:
            raise KeyError(
                f"AuthStrategy {kind!r} not registered. Available: "
                f"{tuple(sorted(cls._strategies))}."
            ) from None

    @classmethod
    def kinds(cls) -> tuple[str, ...]:
        return tuple(sorted(cls._strategies))
