from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, create_autospec

import pytest
from huggingface_hub import HfApi, SyncPlan

from hftracer import cli


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    return home


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = create_autospec(HfApi, instance=True)
    mock.whoami.return_value = {"name": "alice"}
    mock.bucket_info.return_value = SimpleNamespace(private=True)
    mock.sync_bucket.return_value = SyncPlan(source="", dest="", timestamp="")
    monkeypatch.setattr(cli, "HfApi", lambda: mock)
    return mock
