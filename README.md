# hftracer

[![Python](https://img.shields.io/badge/python-3.14%2B-blue?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Hugging Face](https://img.shields.io/badge/storage-Hugging_Face-yellow?logo=huggingface)](https://huggingface.co/docs/huggingface_hub/guides/buckets)

Synchronize agent traces to Hugging Face buckets.

## Installation

```sh
uv tool install hftracer
```

## Usage

```sh
uvx --from huggingface-hub hf auth login
hftracer init
hftracer sync --dry-run
hftracer sync
```

## Supported agents

| Agent | Sources |
| --- | --- |
| Codex | `~/.codex/sessions`, `~/.codex/archived_sessions` |
| Claude Code | `~/.claude/projects` |

## Features

- Incremental uploads with progress bars
- Original files and directory structure preserved
- Separate device namespaces; no remote deletions

## Development

[Usage & development](CONTRIBUTING.md)
