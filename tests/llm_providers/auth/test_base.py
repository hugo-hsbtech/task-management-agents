"""AuthStrategy ABC + Credential shape tests."""

import pytest

from llm_providers.auth.base import AuthStrategy, Credential


def test_credential_is_frozen():
    c = Credential(kind="api_key", payload={"key": "secret"})
    with pytest.raises(Exception):  # noqa: B017
        c.kind = "oauth2_cli_token"  # type: ignore[misc]


def test_auth_strategy_cannot_be_instantiated_directly():
    with pytest.raises(TypeError, match="abstract"):
        AuthStrategy()  # type: ignore[abstract]


def test_auth_strategy_subclass_must_implement_methods():
    class Incomplete(AuthStrategy):
        kind = "incomplete"

    with pytest.raises(TypeError, match="abstract"):
        Incomplete()  # type: ignore[abstract]


def test_auth_strategy_full_subclass_constructs():
    class Full(AuthStrategy):
        kind = "full"

        def detect(self) -> bool:
            return True

        def resolve(self) -> Credential:
            return Credential(kind=self.kind, payload={})

        @classmethod
        def default(cls) -> "Full":
            return cls()

    f = Full()
    assert f.detect() is True
    assert f.resolve().kind == "full"
    assert isinstance(Full.default(), Full)
