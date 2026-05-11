"""Tests for hsb.settings.wio_ipc.WIOIPCSettings."""

from pathlib import Path


def test_defaults_are_none(monkeypatch):
    monkeypatch.delenv("HSB_WIO_INPUT_FILE", raising=False)
    monkeypatch.delenv("HSB_WIO_OUTPUT_FILE", raising=False)
    from hsb.settings.wio_ipc import WIOIPCSettings

    settings = WIOIPCSettings()
    assert settings.input_file is None
    assert settings.output_file is None


def test_reads_env_as_paths(monkeypatch):
    monkeypatch.setenv("HSB_WIO_INPUT_FILE", "/tmp/wio-in.json")
    monkeypatch.setenv("HSB_WIO_OUTPUT_FILE", "/tmp/wio-out.json")
    from hsb.settings.wio_ipc import WIOIPCSettings

    settings = WIOIPCSettings()
    assert settings.input_file == Path("/tmp/wio-in.json")
    assert settings.output_file == Path("/tmp/wio-out.json")
    assert isinstance(settings.input_file, Path)
    assert isinstance(settings.output_file, Path)
