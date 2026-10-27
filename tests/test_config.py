import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hftracer import config as configuration
from hftracer.cli import app
from hftracer.config import Config, config_path, load_config, new_device_id, save_config


def test_config_path_respects_xdg_and_home(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(isolated_home / "custom"))
    assert config_path() == isolated_home / "custom/hftracer/config.json"
    monkeypatch.delenv("XDG_CONFIG_HOME")
    assert config_path() == isolated_home / ".config/hftracer/config.json"
    monkeypatch.setenv("XDG_CONFIG_HOME", "")
    assert config_path() == isolated_home / ".config/hftracer/config.json"


def test_config_roundtrip_and_private_permissions() -> None:
    config = Config("alice/traces", "device-id")
    save_config(config)
    assert load_config() == config
    assert config_path().stat().st_mode & 0o777 == 0o600


def test_failed_atomic_write_preserves_existing_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    previous = Config("alice/traces", "device-id")
    save_config(previous)

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("Replace failed")

    monkeypatch.setattr(configuration.os, "replace", fail_replace)
    with pytest.raises(OSError, match="Replace failed"):
        save_config(Config("alice/new", "device-id"))
    assert load_config() == previous
    assert list(config_path().parent.iterdir()) == [config_path()]


@pytest.mark.parametrize(
    "content",
    [
        "invalid JSON",
        "[]",
        "null",
        "{}",
        json.dumps({"bucket_id": 3, "device_id": "device"}),
        json.dumps({"bucket_id": "alice/traces", "device_id": None}),
        json.dumps({"bucket_id": "alice/traces/nested", "device_id": "device"}),
        json.dumps({"bucket_id": "alice/traces", "device_id": "../other-device"}),
    ],
)
def test_invalid_config_stops_both_commands(content: str) -> None:
    config_path().parent.mkdir(parents=True)
    config_path().write_text(content)
    for command in ("init", "sync"):
        result = CliRunner().invoke(app, [command])
        assert result.exit_code == 1
        assert "Cannot read configuration" in result.output


@pytest.mark.parametrize("hostname", ["Laptop.Example", "///", ""])
def test_device_id_is_path_safe_and_unique(
    monkeypatch: pytest.MonkeyPatch, hostname: str
) -> None:
    monkeypatch.setattr(configuration.socket, "gethostname", lambda: hostname)
    first, second = new_device_id(), new_device_id()
    assert re.fullmatch(r"[a-z0-9-]+-[a-f0-9]{32}", first)
    assert first != second
