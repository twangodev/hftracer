# hftracer

[![Python](https://img.shields.io/badge/python-3.14%2B-blue?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Hugging Face](https://img.shields.io/badge/storage-Hugging_Face-yellow?logo=huggingface)](https://huggingface.co/docs/huggingface_hub/guides/buckets)

Codex + Claude Code → private Hugging Face bucket.

## Quick start

```sh
uv tool install hftracer
uvx --from huggingface-hub hf auth login
hftracer init
hftracer sync --dry-run
hftracer sync
```

| Agent | Sources |
| --- | --- |
| Codex | `~/.codex/sessions`, `~/.codex/archived_sessions` |
| Claude Code | `~/.claude/projects` |

- Incremental uploads with progress bars
- Original files and directory structure preserved
- Separate device namespaces; no remote deletions

[Usage & development](CONTRIBUTING.md)
