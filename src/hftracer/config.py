"""Small, local configuration and fixed agent-directory discovery."""

import json
import os
import re
import socket
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

SOURCES = (
    (".codex/sessions", "codex/sessions"),
    (".codex/archived_sessions", "codex/archived_sessions"),
    (".claude/projects", "claude/projects"),
)


def validate_bucket_id(bucket_id: str) -> None:
    """Require a bucket ID, rather than a URL or a bucket subdirectory."""
    if not re.fullmatch(
        r"[A-Za-z0-9_][A-Za-z0-9_.-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*", bucket_id
    ):
        raise ValueError("Bucket must be in namespace/name format.")


@dataclass(frozen=True)
class Config:
    bucket_id: str
    device_id: str

    def __post_init__(self) -> None:
        validate_bucket_id(self.bucket_id)
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", self.device_id):
            raise ValueError("Invalid device namespace in configuration.")


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    return (
        (Path(base) if base else Path.home() / ".config") / "hftracer" / "config.json"
    )


def load_config() -> Config | None:
    try:
        content = config_path().read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("Configuration must be a JSON object.")
    bucket_id, device_id = data.get("bucket_id"), data.get("device_id")
    if not isinstance(bucket_id, str) or not isinstance(device_id, str):
        raise ValueError("Configuration requires bucket_id and device_id strings.")
    return Config(bucket_id=bucket_id, device_id=device_id)


def save_config(config: Config) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as stream:
            temporary_path = Path(stream.name)
            json.dump(asdict(config), stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def new_device_id() -> str:
    hostname = re.sub(r"[^a-z0-9-]+", "-", socket.gethostname().lower()).strip("-")
    return f"{hostname or 'device'}-{uuid4().hex}"


def discover_sources() -> list[tuple[Path, str]]:
    home = Path.home()
    return [
        (home / local, remote) for local, remote in SOURCES if (home / local).is_dir()
    ]
