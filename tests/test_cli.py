import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest
from huggingface_hub import SyncOperation, SyncPlan
from huggingface_hub.utils import tqdm
from typer.testing import CliRunner

from hftracer import cli
from hftracer.config import Config, config_path, load_config, save_config

runner = CliRunner()


def test_init_prompt_defaults_to_user_traces(api: MagicMock) -> None:
    result = runner.invoke(cli.app, ["init"], input="\n")
    assert result.exit_code == 0, result.output
    assert "alice/traces" in result.output
    assert "No agent directories found yet" in result.output
    api.create_bucket.assert_called_once_with(
        "alice/traces", private=True, exist_ok=True
    )
    api.bucket_info.assert_called_once_with("alice/traces")
    config = load_config()
    assert config is not None
    assert config.bucket_id == "alice/traces"
    assert set(json.loads(config_path().read_text())) == {"bucket_id", "device_id"}
    api.sync_bucket.assert_not_called()


def test_init_explicit_bucket_reports_sources(
    api: MagicMock, isolated_home: Path
) -> None:
    source = isolated_home / ".codex/sessions"
    source.mkdir(parents=True)
    result = runner.invoke(cli.app, ["init", "--bucket", "team/private-traces"])
    assert result.exit_code == 0, result.output
    assert "Sources: codex/sessions" in result.output
    api.create_bucket.assert_called_once_with(
        "team/private-traces", private=True, exist_ok=True
    )


def test_init_custom_prompt_answer(api: MagicMock) -> None:
    result = runner.invoke(cli.app, ["init"], input="team/custom\n")
    assert result.exit_code == 0, result.output
    api.create_bucket.assert_called_once_with(
        "team/custom", private=True, exist_ok=True
    )


def test_reinit_preserves_device_and_uses_configured_default(
    api: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    previous = Config("team/existing", "original-device")
    save_config(previous)
    monkeypatch.setattr("hftracer.config.socket.gethostname", lambda: "new-hostname")
    result = runner.invoke(cli.app, ["init"], input="\n")
    assert result.exit_code == 0, result.output
    assert "team/existing" in result.output
    assert load_config() == previous

    result = runner.invoke(cli.app, ["init", "--bucket", "team/other"])
    assert result.exit_code == 0, result.output
    assert load_config() == Config("team/other", "original-device")


def test_init_authentication_failure(api: MagicMock) -> None:
    api.whoami.side_effect = OSError("No credentials")
    result = runner.invoke(cli.app, ["init", "--bucket", "alice/traces"])
    assert result.exit_code == 1
    assert "hf auth login" in result.output
    assert "HF_TOKEN" in result.output
    assert not config_path().exists()
    api.create_bucket.assert_not_called()


@pytest.mark.parametrize("private", [False, None])
def test_init_rejects_nonprivate_bucket_without_overwriting_config(
    api: MagicMock, private: bool | None
) -> None:
    previous = Config("alice/old", "device-id")
    save_config(previous)
    api.bucket_info.return_value = SimpleNamespace(private=private)
    result = runner.invoke(cli.app, ["init", "--bucket", "alice/public"])
    assert result.exit_code == 1
    assert "private bucket" in result.output
    assert load_config() == previous
    api.update_bucket_settings.assert_not_called()


@pytest.mark.parametrize(
    "bucket", ["traces", "hf://buckets/alice/traces", "alice/traces/path"]
)
def test_init_rejects_invalid_bucket_before_creation(
    api: MagicMock, bucket: str
) -> None:
    result = runner.invoke(cli.app, ["init", "--bucket", bucket])
    assert result.exit_code == 1
    assert "namespace/name" in result.output
    api.create_bucket.assert_not_called()
    assert not config_path().exists()


def test_init_creation_failure_does_not_write_config(api: MagicMock) -> None:
    api.create_bucket.side_effect = OSError("Permission denied")
    result = runner.invoke(cli.app, ["init", "--bucket", "alice/traces"])
    assert result.exit_code == 1
    assert "Permission denied" in result.output
    assert not config_path().exists()


def test_init_save_failure_is_reported(
    api: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_save(config: Config) -> None:
        raise OSError("Disk full")

    monkeypatch.setattr(cli, "save_config", fail_save)
    result = runner.invoke(cli.app, ["init", "--bucket", "alice/traces"])
    assert result.exit_code == 1
    assert "Disk full" in result.output


def test_sync_requires_init(api: MagicMock) -> None:
    result = runner.invoke(cli.app, ["sync"])
    assert result.exit_code == 1
    assert "hftracer init" in result.output
    api.bucket_info.assert_not_called()
    api.sync_bucket.assert_not_called()


def test_sync_delegates_all_three_trees_unchanged(
    api: MagicMock, isolated_home: Path
) -> None:
    save_config(Config("alice/traces", "laptop-id"))
    files = {
        ".codex/sessions/2026/10/session.jsonl": b'{"native": true}\nnot parsed\n',
        ".codex/archived_sessions/old.jsonl": b"archived\r\n",
        ".claude/projects/-example/nested/support.bin": b"\x00\xff\x01",
        ".claude/projects/-example/.hidden": b"supporting file",
    }
    for relative, data in files.items():
        path = isolated_home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    result = runner.invoke(cli.app, ["sync"])
    assert result.exit_code == 0, result.output
    api.bucket_info.assert_called_once_with("alice/traces")
    api.sync_bucket.assert_has_calls(
        [
            call(
                str(isolated_home / local),
                f"hf://buckets/alice/traces/devices/laptop-id/{remote}/",
                delete=False,
                dry_run=False,
                quiet=False,
            )
            for local, remote in (
                (".codex/sessions", "codex/sessions"),
                (".codex/archived_sessions", "codex/archived_sessions"),
                (".claude/projects", "claude/projects"),
            )
        ]
    )
    assert api.sync_bucket.call_count == 3
    assert {
        relative: (isolated_home / relative).read_bytes() for relative in files
    } == files


def test_sync_rediscovers_sources_and_does_not_cache_transfers(
    api: MagicMock, isolated_home: Path
) -> None:
    result = runner.invoke(cli.app, ["init", "--bucket", "alice/traces"])
    assert result.exit_code == 0, result.output
    source = isolated_home / ".claude/projects"
    source.mkdir(parents=True)
    native_file = source / "session.jsonl"
    native_file.write_text("first version\n")
    for content in (None, "new version\n", None):
        if content is not None:
            native_file.write_text(content)
        result = runner.invoke(cli.app, ["sync"])
        assert result.exit_code == 0, result.output
    native_file.unlink()
    result = runner.invoke(cli.app, ["sync"])
    assert result.exit_code == 0, result.output
    assert api.sync_bucket.call_count == 4
    for invocation in api.sync_bucket.call_args_list:
        assert invocation.args[0] == str(source)
        assert invocation.kwargs == {"delete": False, "dry_run": False, "quiet": False}


def test_sync_no_sources_is_successful_noop(api: MagicMock) -> None:
    save_config(Config("alice/traces", "device-id"))
    result = runner.invoke(cli.app, ["sync"])
    assert result.exit_code == 0, result.output
    assert "Nothing to sync" in result.output
    api.sync_bucket.assert_not_called()


@pytest.mark.parametrize("flag", ["--dry-run", "--preview"])
def test_preview_delegates_to_hf_without_changing_files_or_config(
    api: MagicMock, isolated_home: Path, flag: str
) -> None:
    save_config(Config("alice/traces", "device-id"))
    original_config = config_path().read_bytes()
    source = isolated_home / ".codex/sessions"
    source.mkdir(parents=True)
    native_file = source / "session.jsonl"
    native_file.write_bytes(b"native session\n")
    result = runner.invoke(cli.app, ["sync", flag])
    assert result.exit_code == 0, result.output
    api.bucket_info.assert_called_once_with("alice/traces")
    api.sync_bucket.assert_called_once_with(
        str(source),
        "hf://buckets/alice/traces/devices/device-id/codex/sessions/",
        delete=False,
        dry_run=True,
        quiet=True,
    )
    assert "Preview: alice/traces" in result.output
    assert "No files uploaded." in result.output
    assert "Sync complete." not in result.output
    assert native_file.read_bytes() == b"native session\n"
    assert config_path().read_bytes() == original_config
    api.create_bucket.assert_not_called()


def test_preview_failures_keep_remaining_sources_in_preview_mode(
    api: MagicMock, isolated_home: Path
) -> None:
    save_config(Config("alice/traces", "device-id"))
    (isolated_home / ".codex/sessions").mkdir(parents=True)
    (isolated_home / ".claude/projects").mkdir(parents=True)
    api.sync_bucket.side_effect = [
        OSError("Cannot list bucket"),
        api.sync_bucket.return_value,
    ]
    result = runner.invoke(cli.app, ["sync", "--preview"])
    assert result.exit_code == 1
    assert "hftracer sync --dry-run" in result.output
    assert "Preview complete." not in result.output
    assert api.sync_bucket.call_count == 2
    assert all(
        invocation.kwargs == {"delete": False, "dry_run": True, "quiet": True}
        for invocation in api.sync_bucket.call_args_list
    )


@pytest.mark.parametrize("failure", ["public", "network"])
def test_sync_fails_closed_when_privacy_cannot_be_verified(
    api: MagicMock, isolated_home: Path, failure: str
) -> None:
    save_config(Config("alice/traces", "device-id"))
    (isolated_home / ".codex/sessions").mkdir(parents=True)
    if failure == "public":
        api.bucket_info.return_value = SimpleNamespace(private=False)
    else:
        api.bucket_info.side_effect = OSError("Network unavailable")
    result = runner.invoke(cli.app, ["sync"])
    assert result.exit_code == 1
    assert "Cannot verify private bucket" in result.output
    api.sync_bucket.assert_not_called()


def test_sync_attempts_remaining_sources_after_failure(
    api: MagicMock, isolated_home: Path
) -> None:
    save_config(Config("alice/traces", "device-id"))
    (isolated_home / ".codex/sessions").mkdir(parents=True)
    (isolated_home / ".claude/projects").mkdir(parents=True)
    api.sync_bucket.side_effect = [
        OSError("Transfer failed"),
        api.sync_bucket.return_value,
    ]
    result = runner.invoke(cli.app, ["sync"])
    assert result.exit_code == 1
    assert "Transfer failed" in result.output
    assert "again to retry" in result.output
    assert api.sync_bucket.call_count == 2
    assert api.sync_bucket.call_args_list[-1].args[0].endswith(".claude/projects")


def test_sync_uses_separate_device_namespaces(api: MagicMock) -> None:
    destinations = []
    source = Path.home() / ".codex/sessions"
    source.mkdir(parents=True)
    for _ in range(2):
        result = runner.invoke(cli.app, ["init", "--bucket", "alice/traces"])
        assert result.exit_code == 0, result.output
        result = runner.invoke(cli.app, ["sync"])
        assert result.exit_code == 0, result.output
        destinations.append(api.sync_bucket.call_args.args[1])
        config_path().unlink()
    assert destinations[0] != destinations[1]


@pytest.mark.parametrize("dry_run", [True, False])
def test_sync_prints_compact_summary_instead_of_sdk_output(
    api: MagicMock, isolated_home: Path, dry_run: bool
) -> None:
    save_config(Config("alice/traces", "device-id"))
    (isolated_home / ".codex/sessions").mkdir(parents=True)
    plan = SyncPlan(
        source="",
        dest="",
        timestamp="",
        operations=[
            SyncOperation(action="upload", path="session.jsonl", size=1024),
            SyncOperation(action="skip", path="unchanged.jsonl"),
        ],
    )

    def noisy_sync(*args: object, **kwargs: object) -> SyncPlan:
        print('{"action":"upload","path":"session.jsonl"}')
        if not kwargs["quiet"]:
            with tqdm(total=1, desc="Upload", disable=False) as progress:
                progress.update(1)
        return plan

    api.sync_bucket.side_effect = noisy_sync
    result = runner.invoke(cli.app, ["sync", *(["--dry-run"] if dry_run else [])])
    assert result.exit_code == 0, result.output
    mode, label = ("Preview", "to upload") if dry_run else ("Sync", "uploaded")
    ending = "No files uploaded." if dry_run else "Sync complete."
    assert result.stdout.splitlines() == [
        f"{mode}: alice/traces",
        f"codex/sessions: 1 {label}, 1 unchanged (1 KiB)",
        ending,
    ]
    if dry_run:
        assert result.stderr == ""
    else:
        assert "Upload" in result.stderr
        assert "100%" in result.stderr


@pytest.mark.parametrize("color", [True, False])
def test_color_output_follows_terminal_setting(api: MagicMock, color: bool) -> None:
    result = runner.invoke(cli.app, ["init", "--bucket", "alice/traces"], color=color)
    assert result.exit_code == 0, result.output
    assert ("\x1b[32mConfigured" in result.output) is color
    assert ("\x1b[33mNo agent directories" in result.output) is color
    config_path().unlink()
    result = runner.invoke(cli.app, ["sync"], color=color)
    assert result.exit_code == 1
    assert ("\x1b[31mError:" in result.output) is color


@pytest.mark.parametrize("command", [[], ["init"], ["sync"]])
def test_help(api: MagicMock, command: list[str]) -> None:
    result = runner.invoke(cli.app, [*command, "--help"])
    assert result.exit_code == 0
    api.whoami.assert_not_called()
    api.sync_bucket.assert_not_called()
