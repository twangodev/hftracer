# Usage & development

## Usage

| Command | Behavior |
| --- | --- |
| `hftracer init` | Prompt for a private bucket; default: `<username>/traces` |
| `hftracer init --bucket namespace/name` | Configure without prompting |
| `hftracer sync` | Upload new and changed files with HF progress bars |
| `hftracer sync --dry-run` | Preview counts and transfer sizes |
| `hftracer sync --preview` | Alias for `--dry-run` |

- Authentication: existing HF login or `HF_TOKEN`.
- Configuration: `$XDG_CONFIG_HOME/hftracer/config.json`; default: `~/.config/hftracer/config.json`.
- Remote paths: `devices/<device>/codex/{sessions,archived_sessions}/` and `devices/<device>/claude/projects/`.
- Device identity persists across setup runs. Keep each device's config separate.
- All files, including hidden and supporting files, are included unchanged.
- HF compares size and modification time. Same-size changes with unchanged timestamps may be skipped.
- Uploads finalize in batches. Ctrl+C preserves finalized files; the current batch may need retrying.
- Re-run after active sessions finish for a settled copy.
- Missing sources are skipped. Transfer failures return a nonzero exit code.
- Schedule externally with cron, systemd timers, or a Docker scheduler.

## Development

```sh
uv sync --locked
uv run pytest
uv run ty check
uv run ruff check .
uv run ruff format --check .
uv build
```

Tests use synthetic files and mocked HF calls. Live checks are described in
[manual integration](tests/manual-integration.md).

Use focused Conventional Commits, such as `feat: ...`, `fix: ...`, `docs: ...`,
and `ci: ...`.
