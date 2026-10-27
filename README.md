# hftracer

[![Python](https://img.shields.io/badge/python-3.14%2B-blue?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Hugging Face](https://img.shields.io/badge/Hugging_Face-Storage_Buckets-yellow?logo=huggingface)](https://huggingface.co/docs/huggingface_hub/guides/buckets)

Sync Codex and Claude Code sessions to a private Hugging Face Storage Bucket.

```sh
uv tool install .
uvx --from huggingface-hub hf auth login
hftracer init
hftracer sync --dry-run
hftracer sync
```

`init` prompts for a bucket, defaulting to `<username>/traces`.
Use `--bucket namespace/name` to skip the prompt.
`sync --preview` is an alias for `sync --dry-run`.

Syncs everything under `~/.codex/sessions`, `~/.codex/archived_sessions`, and
`~/.claude/projects` into `devices/<device>/` in your bucket. File contents and
directory structures stay intact. Each device has its own namespace.

Hugging Face handles incremental transfers and progress bars. Unchanged files are
skipped; remote files are never deleted. Uploads are finalized in batches, so
interrupting a transfer may require retrying the current batch.

Configuration: `$XDG_CONFIG_HOME/hftracer/config.json` (default:
`~/.config/hftracer/config.json`). Schedule sync externally with cron or systemd.

Development: `uv sync`, `uv run pytest`, `uv run ty check`, `uv run ruff check .`,
`uv run ruff format --check .`, `uv build`.
See [manual integration checks](tests/manual-integration.md).
