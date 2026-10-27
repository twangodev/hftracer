"""Discover local agent directories and delegate transfers to Hugging Face."""

import os
from contextlib import redirect_stdout
from typing import Annotated, NoReturn

import typer
from huggingface_hub import HfApi

from hftracer.config import (
    Config,
    config_path,
    discover_sources,
    load_config,
    new_device_id,
    save_config,
    validate_bucket_id,
)

app = typer.Typer(
    help="Sync Codex and Claude Code sessions to a private Hugging Face bucket.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)


def fail(message: str) -> NoReturn:
    typer.secho(f"Error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(1)


def read_config() -> Config | None:
    try:
        return load_config()
    except (OSError, ValueError) as exc:
        fail(f"Cannot read configuration at {config_path()}: {exc}")


def require_private(api: HfApi, bucket_id: str) -> None:
    if api.bucket_info(bucket_id).private is not True:
        raise ValueError(f"Bucket {bucket_id} is public; select a private bucket.")


def format_size(size: int) -> str:
    amount = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if amount < 1024:
            return f"{amount:.3g} {unit}"
        amount /= 1024
    return f"{amount:.3g} TiB"


@app.command()
def init(
    bucket: Annotated[
        str | None,
        typer.Option(
            "--bucket", help="Create or select namespace/name without prompting."
        ),
    ] = None,
) -> None:
    """Configure a private bucket and a persistent namespace for this device."""
    previous = read_config()
    api = HfApi()
    try:
        username = api.whoami()["name"]
    except Exception as exc:
        fail(
            "Cannot authenticate with Hugging Face. "
            f"Run `hf auth login` or set HF_TOKEN. {exc}"
        )

    if bucket is None:
        default = previous.bucket_id if previous else f"{username}/traces"
        bucket = typer.prompt("Bucket (namespace/name)", default=default)
    try:
        validate_bucket_id(bucket)
        api.create_bucket(bucket, private=True, exist_ok=True)
        require_private(api, bucket)
    except Exception as exc:
        fail(f"Cannot configure bucket: {exc}")

    config = Config(bucket, previous.device_id if previous else new_device_id())
    try:
        sources = discover_sources()
        save_config(config)
    except OSError as exc:
        fail(f"Cannot finish setup: {exc}")
    typer.secho(f"Configured {config.bucket_id}", fg=typer.colors.GREEN)
    if sources:
        typer.secho(
            f"Sources: {', '.join(remote for _, remote in sources)}",
            fg=typer.colors.CYAN,
        )
    else:
        typer.secho("No agent directories found yet.", fg=typer.colors.YELLOW)


@app.command()
def sync(
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", "--preview", help="Preview planned changes without uploading."
        ),
    ] = False,
) -> None:
    """Upload new and modified files; never delete remote files."""
    config = read_config()
    if config is None:
        fail("No configuration found. Run `hftracer init` first.")
    api = HfApi()
    try:
        require_private(api, config.bucket_id)
    except Exception as exc:
        fail(f"Cannot verify private bucket: {exc}")
    try:
        sources = discover_sources()
    except OSError as exc:
        fail(f"Cannot discover agent directories: {exc}")
    if not sources:
        typer.secho(
            "No agent directories found. Nothing to sync.", fg=typer.colors.YELLOW
        )
        return

    mode = "Preview" if dry_run else "Sync"
    upload_label = "to upload" if dry_run else "uploaded"
    typer.secho(f"{mode}: {config.bucket_id}", fg=typer.colors.CYAN)
    failed = False
    for source, remote in sources:
        destination = (
            f"hf://buckets/{config.bucket_id}/devices/{config.device_id}/{remote}/"
        )
        try:
            with open(os.devnull, "w") as sink, redirect_stdout(sink):
                plan = api.sync_bucket(
                    str(source),
                    destination,
                    delete=False,
                    dry_run=dry_run,
                    quiet=dry_run,
                )
            summary = plan.summary()
            size = format_size(int(summary["total_size"]))
            typer.echo(
                f"{remote}: {summary['uploads']} {upload_label}, "
                f"{summary['skips']} unchanged ({size})"
            )
        except Exception as exc:
            typer.secho(f"Error for {remote}: {exc}", fg=typer.colors.RED, err=True)
            failed = True
    if failed:
        command = "hftracer sync --dry-run" if dry_run else "hftracer sync"
        fail(f"Some sources failed. Run `{command}` again to retry.")
    if dry_run:
        typer.secho("No files uploaded.", fg=typer.colors.YELLOW)
    else:
        typer.secho("Sync complete.", fg=typer.colors.GREEN)
