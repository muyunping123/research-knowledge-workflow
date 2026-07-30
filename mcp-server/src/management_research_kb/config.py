"""TOML configuration loading and safety validation."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path, PurePath
import tomllib
from urllib.parse import urlparse

from .errors import ConfigError


CONFIG_ENV = "RESEARCH_KNOWLEDGE_WORKFLOW_CONFIG"
LEGACY_CONFIG_ENV = "MANAGEMENT_RESEARCH_KB_CONFIG"


def _platform_config_path(app_name: str) -> Path:
    if os.name == "nt" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / app_name / "config.toml"
    return Path.home() / ".config" / app_name / "config.toml"


DEFAULT_CONFIG_PATH = _platform_config_path("research-knowledge-workflow")
LEGACY_DEFAULT_CONFIG_PATH = _platform_config_path("management-research-kb")


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _expand_path(value: str, base: Path) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(value.strip()))
    path = Path(expanded)
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _validate_notes_dir(value: str) -> str:
    value = value.strip().replace("\\", "/").strip("/")
    path = PurePath(value)
    if not value or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ConfigError("notes_dir must be a non-empty relative directory inside the vault")
    if ".obsidian" in {part.casefold() for part in path.parts}:
        raise ConfigError("notes_dir cannot be inside .obsidian")
    return "/".join(path.parts)


@dataclass(frozen=True, slots=True)
class Config:
    """Runtime configuration for the local server."""

    vault_path: Path
    cache_dir: Path
    manuscripts_root: Path | None = None
    notes_dir: str = "知识笔记"
    zotero_base_url: str = "http://127.0.0.1:23119"
    max_group_documents: int = 20
    max_chars: int = 120_000
    source_path: Path | None = None

    @property
    def database_path(self) -> Path:
        return self.cache_dir / "index.sqlite"

    @property
    def notes_path(self) -> Path:
        return self.vault_path.joinpath(*self.notes_dir.split("/"))

    def validate(self, *, require_vault: bool = True) -> "Config":
        vault = self.vault_path.resolve()
        cache = self.cache_dir.resolve()
        if require_vault and (not vault.exists() or not vault.is_dir()):
            raise ConfigError(f"vault_path does not exist or is not a directory: {vault}")
        if cache == vault or _is_within(cache, vault):
            raise ConfigError("cache_dir must be outside vault_path")
        if self.manuscripts_root is not None:
            manuscripts = self.manuscripts_root.resolve()
            if manuscripts == vault or _is_within(manuscripts, vault):
                raise ConfigError("manuscripts_root must not be inside vault_path")
        _validate_notes_dir(self.notes_dir)
        zotero_url = urlparse(self.zotero_base_url)
        if (
            zotero_url.scheme != "http"
            or zotero_url.hostname not in {"127.0.0.1", "localhost", "::1"}
            or zotero_url.username is not None
            or zotero_url.password is not None
        ):
            raise ConfigError("zotero_base_url must use an HTTP loopback interface")
        if self.max_group_documents <= 0:
            raise ConfigError("max_group_documents must be positive")
        if self.max_chars <= 0:
            raise ConfigError("max_chars must be positive")
        return self


def resolve_config_path(path: str | Path | None = None) -> Path:
    """Resolve explicit, current, then legacy configuration locations."""

    candidate = path or os.environ.get(CONFIG_ENV) or os.environ.get(LEGACY_CONFIG_ENV)
    if candidate is None:
        candidate = (
            DEFAULT_CONFIG_PATH
            if DEFAULT_CONFIG_PATH.is_file() or not LEGACY_DEFAULT_CONFIG_PATH.is_file()
            else LEGACY_DEFAULT_CONFIG_PATH
        )
    resolved = Path(os.path.expandvars(os.path.expanduser(str(candidate)))).resolve()
    if not resolved.is_file():
        raise ConfigError(
            f"Configuration file not found: {resolved}. Set {CONFIG_ENV}, "
            f"legacy {LEGACY_CONFIG_ENV}, or pass --config."
        )
    return resolved


def load_config(path: str | Path | None = None, *, require_vault: bool = True) -> Config:
    """Load a flat TOML configuration file."""

    config_path = resolve_config_path(path)
    try:
        with config_path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"Unable to read TOML configuration {config_path}: {exc}") from exc

    missing = [name for name in ("vault_path", "cache_dir") if not data.get(name)]
    if missing:
        raise ConfigError(f"Missing required configuration field(s): {', '.join(missing)}")

    base = config_path.parent
    manuscripts_value = data.get("manuscripts_root")
    config = Config(
        vault_path=_expand_path(str(data["vault_path"]), base),
        cache_dir=_expand_path(str(data["cache_dir"]), base),
        manuscripts_root=(
            _expand_path(str(manuscripts_value), base) if manuscripts_value else None
        ),
        notes_dir=_validate_notes_dir(str(data.get("notes_dir", "知识笔记"))),
        zotero_base_url=str(
            data.get("zotero_base_url", "http://127.0.0.1:23119")
        ).rstrip("/"),
        max_group_documents=int(data.get("max_group_documents", 20)),
        max_chars=int(data.get("max_chars", 120_000)),
        source_path=config_path,
    )
    return config.validate(require_vault=require_vault)
