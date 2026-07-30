"""Incremental, read-only PDF discovery and per-page extraction."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
from typing import Callable, Iterable, Sequence

from .config import Config
from .database import Database
from .utils import (
    ensure_within,
    find_doi,
    infer_year_title,
    normalize_group_path,
    normalize_title,
    utc_now,
)


@dataclass(slots=True)
class ExtractedPdf:
    pages: list[str]
    metadata: dict[str, str] = field(default_factory=dict)


PdfExtractor = Callable[[Path], ExtractedPdf | Sequence[str]]


def extract_pdf(path: Path) -> ExtractedPdf:
    """Extract page text and non-authoritative PDF metadata with pypdf."""

    from pypdf import PdfReader

    reader = PdfReader(str(path), strict=False)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            pass
    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append((page.extract_text() or "").replace("\x00", ""))
        except Exception:
            pages.append("")
    raw_metadata = reader.metadata or {}
    metadata = {
        str(key).lstrip("/"): str(value)
        for key, value in raw_metadata.items()
        if value is not None
    }
    return ExtractedPdf(pages=pages, metadata=metadata)


def _path_is_inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def discover_pdfs(config: Config, group_path: str | None = None) -> list[Path]:
    """Find PDFs, optionally beneath one relative directory group."""

    vault = config.vault_path.resolve()
    notes_root = config.notes_path.resolve()
    normalized_group = (
        normalize_group_path(group_path) if group_path is not None else None
    ) or None
    scan_root = vault
    if normalized_group:
        scan_root = ensure_within(
            vault.joinpath(*normalized_group.split("/")), vault
        )
    if not scan_root.is_dir():
        return []
    discovered: list[Path] = []
    for root, directories, filenames in os.walk(scan_root):
        root_path = Path(root)
        kept: list[str] = []
        for directory in directories:
            candidate = (root_path / directory).resolve()
            if directory.casefold() == ".obsidian":
                continue
            if candidate == notes_root or _path_is_inside(candidate, notes_root):
                continue
            kept.append(directory)
        directories[:] = kept
        for filename in filenames:
            if not filename.casefold().endswith(".pdf"):
                continue
            candidate = (root_path / filename).resolve()
            if not _path_is_inside(candidate, vault):
                continue
            if _path_is_inside(candidate, notes_root):
                continue
            discovered.append(candidate)
    return sorted(discovered, key=lambda item: item.relative_to(vault).as_posix().casefold())


class PdfIndexer:
    def __init__(
        self,
        config: Config,
        database: Database,
        *,
        extractor: PdfExtractor | None = None,
    ):
        self.config = config
        self.database = database
        self.extractor = extractor or extract_pdf

    def sync(self, *, group_path: str | None = None) -> dict[str, object]:
        """Incrementally index changed PDFs by size and nanosecond mtime."""

        normalized_group = (
            normalize_group_path(group_path) if group_path is not None else None
        ) or None
        indexed: list[str] = []
        skipped: list[str] = []
        errors: list[dict[str, str]] = []
        current_paths: set[str] = set()

        for path in discover_pdfs(self.config, normalized_group):
            relative_path = path.relative_to(self.config.vault_path).as_posix()
            current_paths.add(relative_path)
            stat = path.stat()
            existing = self.database.get_by_relative_path(relative_path)
            if (
                existing
                and int(existing["size"]) == stat.st_size
                and int(existing["mtime_ns"]) == stat.st_mtime_ns
            ):
                skipped.append(relative_path)
                continue

            extraction_error: str | None = None
            pdf_metadata: dict[str, str] = {}
            try:
                extracted = self.extractor(path)
                if isinstance(extracted, ExtractedPdf):
                    pages = [str(page or "") for page in extracted.pages]
                    pdf_metadata = extracted.metadata
                else:
                    pages = [str(page or "") for page in extracted]
            except Exception as exc:
                pages = []
                extraction_error = f"{type(exc).__name__}: {exc}"
                errors.append({"relative_path": relative_path, "error": extraction_error})

            year, title = infer_year_title(path.name)
            if not title and pdf_metadata.get("Title"):
                title = pdf_metadata["Title"].strip()
            compact_chars = sum(len(re.sub(r"\s+", "", page)) for page in pages)
            minimum_useful_chars = max(80, len(pages) * 20)
            evidence_level = (
                "fulltext" if compact_chars >= minimum_useful_chars else "needs_ocr"
            )
            doi = find_doi("\n".join(pages[:3]))
            if not doi:
                doi = find_doi("\n".join(pdf_metadata.values()))

            group_path = path.parent.relative_to(self.config.vault_path).as_posix()
            if group_path == ".":
                group_path = ""
            metadata = {
                "relative_path": relative_path,
                "absolute_path": str(path),
                "group_path": group_path,
                "filename": path.name,
                "inferred_title": title,
                "normalized_title": normalize_title(title),
                "year": year,
                "doi": doi,
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "page_count": len(pages),
                "extracted_chars": sum(len(page) for page in pages),
                "evidence_level": evidence_level,
                "extraction_error": extraction_error,
                "indexed_at": utc_now(),
            }
            self.database.upsert_document(metadata, pages)
            indexed.append(relative_path)

        removed = self.database.remove_missing(
            current_paths, group_prefix=normalized_group
        )
        return {
            "status": "ok" if not errors else "partial",
            "scope": normalized_group,
            "indexed": indexed,
            "skipped": skipped,
            "removed": removed,
            "errors": errors,
            "counts": {
                "discovered": len(current_paths),
                "indexed": len(indexed),
                "skipped": len(skipped),
                "removed": len(removed),
                "errors": len(errors),
            },
            "cache": self.database.stats(),
        }
