"""Path, filename, and text normalization helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import unicodedata

from .errors import PathSafetyError


YEAR_TITLE_RE = re.compile(r"^(?P<year>(?:18|19|20|21)\d{2})[\s_\-—]+(?P<title>.+)$")
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
WINDOWS_UNSAFE_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_within(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    allowed = root.resolve()
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise PathSafetyError(f"Path escapes allowed root: {path}") from exc
    return resolved


def normalize_group_path(group_path: str | None) -> str:
    if group_path is None:
        return ""
    raw = group_path.strip().replace("\\", "/").strip("/")
    if raw in {"", "."}:
        return ""
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise PathSafetyError(f"Unsafe group path: {group_path}")
    if any(part.casefold() == ".obsidian" for part in path.parts):
        raise PathSafetyError("The .obsidian directory cannot be used as a group")
    return path.as_posix()


def _safe_filename_component(component: str) -> str:
    value = WINDOWS_UNSAFE_RE.sub("_", component).strip().rstrip(".")
    return value or "未命名"


def knowledge_note_filename(group_path: str) -> str:
    normalized = normalize_group_path(group_path)
    if not normalized:
        return "根目录.md"
    components = [_safe_filename_component(part) for part in PurePosixPath(normalized).parts]
    return "_".join(components) + ".md"


def infer_year_title(filename: str) -> tuple[int | None, str]:
    stem = Path(filename).stem.strip()
    match = YEAR_TITLE_RE.match(stem)
    if not match:
        return None, stem.replace("_", " ").strip()
    return int(match.group("year")), match.group("title").replace("_", " ").strip()


def normalize_title(title: str) -> str:
    value = unicodedata.normalize("NFKC", title).casefold()
    return "".join(character for character in value if character.isalnum())


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip()
    match = DOI_RE.search(cleaned)
    return match.group(0).rstrip(".,;)").lower() if match else None


def find_doi(text: str) -> str | None:
    match = DOI_RE.search(text[:100_000])
    return normalize_doi(match.group(0)) if match else None


def parse_year(value: str | int | None) -> int | None:
    if value is None:
        return None
    match = re.search(r"(?:18|19|20|21)\d{2}", str(value))
    return int(match.group(0)) if match else None


def canonical_hash(value: object, *, prefix: str = "") -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return prefix + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def yaml_scalar(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def tokenize_for_similarity(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    latin = set(re.findall(r"[a-z0-9]{3,}", normalized))
    cjk_runs = re.findall(r"[\u3400-\u9fff]+", normalized)
    cjk: set[str] = set()
    for run in cjk_runs:
        if len(run) <= 3:
            cjk.add(run)
        else:
            cjk.update(run[index : index + 2] for index in range(len(run) - 1))
    return latin | cjk
