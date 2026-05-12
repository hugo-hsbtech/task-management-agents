"""ProviderRegistry, AuthRegistry, and auto_resolve_auth.

Decorator-based registries: subclasses self-register at class definition time
via @ProviderRegistry.register("name") and @AuthRegistry.register("kind").
Open for extension (one decorator), closed for modification (no edits to
registry.py to add a provider).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

from llm_providers.auth.base import AuthStrategy
from llm_providers.base import BaseProvider
from llm_providers.errors import AuthResolutionError, ProviderNotFoundError

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

logger = logging.getLogger(__name__)


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
            logger.debug("Registered provider %r → %s", name, provider_cls.__name__)
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
        return cls.get(name)(auth=auth)

    @classmethod
    def build_from_auth_method(
        cls,
        name: str,
        *,
        auth_method: str,
    ) -> BaseProvider:
        """Instantiate a provider using a named auth method (e.g. 'api_key', 'oauth2').

        Walks ``provider_cls.supported_auth`` and picks the first strategy whose
        ``kind`` matches ``auth_method``, then calls its ``default()`` constructor.

        Raises ``ValueError`` if no registered strategy matches ``auth_method``.
        """
        provider_cls = cls.get(name)
        for strat_cls in provider_cls.supported_auth:
            if strat_cls.kind == auth_method:
                return provider_cls(auth=strat_cls.default())

        raise ValueError(
            f"Provider {name!r} has no auth strategy with kind={auth_method!r}. "
            f"Available: {[s.kind for s in provider_cls.supported_auth]}"
        )

    @classmethod
    def build_auto(
        cls,
        name: str,
        *,
        accepted_kinds: Iterable[str] | None = None,
    ) -> BaseProvider:
        provider_cls = cls.get(name)
        auth = auto_resolve_auth(name, accepted_kinds=accepted_kinds)
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
            if not issubclass(strat_cls, AuthStrategy):
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
            logger.debug("Registered auth strategy %r → %s", kind, strat_cls.__name__)
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


def auto_resolve_auth(
    provider_name: str,
    *,
    accepted_kinds: Iterable[str] | None = None,
) -> AuthStrategy:
    """Walk provider.supported_auth in declared (preferred-first) order.

    For each candidate strategy:
      1. If accepted_kinds is provided and strategy.kind is not in it → skip.
      2. Try strategy.default() — if it raises, record and skip.
      3. If instance.detect() returns False, record and skip.
      4. Otherwise return the instance.

    Raises AuthResolutionError if no strategy resolves; the error lists every
    strategy tried and why it was skipped.
    """
    provider_cls = ProviderRegistry.get(provider_name)
    accepted = set(accepted_kinds) if accepted_kinds is not None else None
    skipped: list[tuple[str, str]] = []

    for strat_cls in provider_cls.supported_auth:
        if accepted is not None and strat_cls.kind not in accepted:
            skipped.append((strat_cls.__name__, "filtered_by_accepted_kinds"))
            continue
        try:
            instance = strat_cls.default()
        except Exception as e:  # noqa: BLE001 — strategy owns its construction errors
            skipped.append((strat_cls.__name__, f"construct_failed: {e}"))
            continue
        if instance.detect():
            return instance
        skipped.append((strat_cls.__name__, "not_detected"))

    raise AuthResolutionError(
        provider=provider_name, skipped=skipped, accepted=accepted
    )
