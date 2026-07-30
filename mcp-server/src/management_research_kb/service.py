"""Independently testable knowledge-base service used by MCP tools."""

from __future__ import annotations

from difflib import SequenceMatcher
import math
from pathlib import Path
import re
import tempfile
from typing import Any, Callable, Sequence
import zipfile
from xml.etree import ElementTree

from .config import Config
from .database import Database, EVIDENCE_LEVELS
from .errors import KnowledgeBaseError, PathSafetyError, ZoteroUnavailable
from .indexer import PdfExtractor, PdfIndexer, discover_pdfs
from .utils import (
    canonical_hash,
    ensure_within,
    infer_year_title,
    knowledge_note_filename,
    normalize_group_path,
    normalize_title,
    tokenize_for_similarity,
    utc_now,
    yaml_scalar,
)
from .zotero import ZoteroClient


TEXT_PROJECT_SUFFIXES = {
    ".bib",
    ".cfg",
    ".csv",
    ".json",
    ".md",
    ".rst",
    ".tex",
    ".txt",
    ".yaml",
    ".yml",
}
PROJECT_SUFFIXES = TEXT_PROJECT_SUFFIXES | {".docx"}
IGNORED_PROJECT_DIRS = {".git", ".obsidian", ".venv", "node_modules", "__pycache__"}
CURSOR_RE = re.compile(r"^(\d+):(\d+):(\d+)$")
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
GENERATED_BEGIN = "<!-- MRKB:BEGIN GENERATED -->"
GENERATED_END = "<!-- MRKB:END GENERATED -->"
LITERATURE_TYPES = {
    "review_or_meta_analysis",
    "theoretical_or_conceptual",
    "empirical_quantitative",
    "empirical_qualitative_or_case",
    "method_model_algorithm_or_optimization",
    "dataset_system_or_application",
    "unknown",
}


def _document_view(document: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "relative_path",
        "absolute_path",
        "group_path",
        "filename",
        "inferred_title",
        "year",
        "doi",
        "size",
        "mtime_ns",
        "page_count",
        "extracted_chars",
        "evidence_level",
        "extraction_error",
        "indexed_at",
    )
    return {key: document.get(key) for key in keys}


class KnowledgeBaseService:
    """Core implementation with no dependency on the MCP runtime."""

    def __init__(
        self,
        config: Config,
        *,
        extractor: PdfExtractor | None = None,
        zotero_client: ZoteroClient | None = None,
    ):
        self.config = config.validate()
        self.config.cache_dir.mkdir(parents=True, exist_ok=True)
        self.database = Database(self.config.database_path)
        self.indexer = PdfIndexer(config, self.database, extractor=extractor)
        self.zotero = zotero_client or ZoteroClient(config.zotero_base_url)

    def kb_status(self, *, check_zotero: bool = True) -> dict[str, Any]:
        zotero: dict[str, Any]
        if not check_zotero:
            zotero = {"available": None, "checked": False}
        else:
            try:
                zotero = {**self.zotero.status(), "checked": True}
            except ZoteroUnavailable as exc:
                zotero = {"available": False, "checked": True, "error": str(exc)}
        return {
            "status": "ok",
            "config": {
                "source_path": str(self.config.source_path) if self.config.source_path else None,
                "vault_path": str(self.config.vault_path),
                "notes_dir": self.config.notes_dir,
                "notes_path": str(self.config.notes_path),
                "cache_dir": str(self.config.cache_dir),
                "database_path": str(self.config.database_path),
                "manuscripts_root": (
                    str(self.config.manuscripts_root)
                    if self.config.manuscripts_root is not None
                    else None
                ),
                "max_group_documents": self.config.max_group_documents,
                "max_chars": self.config.max_chars,
            },
            "vault": {
                "exists": self.config.vault_path.is_dir(),
                "notes_exists": self.config.notes_path.is_dir(),
            },
            "cache": self.database.stats(),
            "zotero": zotero,
        }

    def kb_sync(self, *, group_path: str | None = None) -> dict[str, object]:
        """Index the whole vault or one selected relative directory subtree."""

        return self.indexer.sync(group_path=group_path)

    def kb_list_groups(self) -> dict[str, Any]:
        groups: list[dict[str, Any]] = []
        for row in self.database.list_groups():
            group = str(row["group_path"])
            note_name = knowledge_note_filename(group)
            note_path = self.config.notes_path / note_name
            groups.append(
                {
                    **row,
                    "display_name": group or "根目录",
                    "knowledge_note": note_name,
                    "knowledge_note_path": str(note_path),
                    "knowledge_note_exists": note_path.is_file(),
                }
            )
        return {"status": "ok", "count": len(groups), "groups": groups}

    def kb_prepare_topic(
        self,
        query: str,
        *,
        search_terms: Sequence[str] | None = None,
        required_terms: Sequence[str] | None = None,
        max_groups: int = 3,
        max_matches_per_group: int = 10,
        max_chars_per_group: int = 20_000,
    ) -> dict[str, Any]:
        """Discover unindexed topic PDFs, selectively index groups, and stage note evidence."""

        clean_query = query.strip()
        if not clean_query:
            raise KnowledgeBaseError("query cannot be empty")
        group_limit = max(1, min(int(max_groups), 8))
        match_limit = max(1, min(int(max_matches_per_group), 50))
        context_limit = max(
            1, min(int(max_chars_per_group), self.config.max_chars)
        )

        terms: list[str] = []
        for value in [clean_query, *(search_terms or [])]:
            term = str(value).strip()
            if term and term.casefold() not in {item.casefold() for item in terms}:
                terms.append(term)
            if len(terms) >= 20:
                break
        term_tokens = {
            term: tokenize_for_similarity(term)
            for term in terms
            if tokenize_for_similarity(term)
        }
        required: list[str] = []
        for value in required_terms or []:
            term = str(value).strip()
            if term and term.casefold() not in {item.casefold() for item in required}:
                required.append(term)
            if len(required) >= 20:
                break
        required_tokens = {
            term: tokenize_for_similarity(term)
            for term in required
            if tokenize_for_similarity(term)
        }
        query_tokens = tokenize_for_similarity(clean_query)
        all_tokens = set().union(*term_tokens.values()) if term_tokens else set()
        vault = self.config.vault_path.resolve()
        discovered = discover_pdfs(self.config)
        grouped: dict[str, dict[str, Any]] = {}

        for path in discovered:
            relative_path = path.relative_to(vault).as_posix()
            group_path = path.parent.relative_to(vault).as_posix()
            if group_path == ".":
                group_path = ""
            year, title = infer_year_title(path.name)
            searchable = f"{group_path} {path.name} {title}"
            candidate_tokens = tokenize_for_similarity(searchable)
            shared = all_tokens & candidate_tokens
            primary_shared = query_tokens & candidate_tokens
            matched_terms: list[str] = []
            matched_required_terms: list[str] = []
            best_term_coverage = 0.0
            normalized_searchable = searchable.casefold()
            for term, tokens in term_tokens.items():
                overlap = tokens & candidate_tokens
                coverage = len(overlap) / max(1, len(tokens))
                best_term_coverage = max(best_term_coverage, coverage)
                if term.casefold() in normalized_searchable or coverage >= 0.5:
                    matched_terms.append(term)
            for term, tokens in required_tokens.items():
                overlap = tokens & candidate_tokens
                coverage = len(overlap) / max(1, len(tokens))
                if term.casefold() in normalized_searchable or coverage >= 0.5:
                    matched_required_terms.append(term)
            if required_tokens and not matched_required_terms:
                continue
            if not shared and not matched_terms:
                continue

            primary_coverage = len(primary_shared) / max(1, len(query_tokens))
            similarity = len(shared) / math.sqrt(
                max(1, len(all_tokens)) * max(1, len(candidate_tokens))
            )
            term_coverage = len(matched_terms) / max(1, len(term_tokens))
            score = (
                0.20 * primary_coverage
                + 0.25 * best_term_coverage
                + 0.40 * term_coverage
                + 0.15 * similarity
            )
            record = {
                "relative_path": relative_path,
                "filename": path.name,
                "inferred_title": title,
                "year": year,
                "score": round(score, 6),
                "matched_terms": matched_terms,
                "matched_required_terms": matched_required_terms,
                "shared_terms": sorted(shared, key=lambda value: (len(value), value))[:16],
            }
            group = grouped.setdefault(
                group_path,
                {
                    "group_path": group_path,
                    "knowledge_note": knowledge_note_filename(group_path),
                    "knowledge_note_exists": (
                        self.config.notes_path / knowledge_note_filename(group_path)
                    ).is_file(),
                    "score": 0.0,
                    "matched_pdf_count": 0,
                    "matched_pdfs": [],
                },
            )
            group["score"] = max(float(group["score"]), score)
            group["matched_pdf_count"] = int(group["matched_pdf_count"]) + 1
            group["matched_pdfs"].append(record)

        candidates: list[dict[str, Any]] = []
        for group in grouped.values():
            group["score"] = round(
                float(group["score"])
                + min(0.05, 0.005 * max(0, int(group["matched_pdf_count"]) - 1)),
                6,
            )
            group["matched_pdfs"].sort(
                key=lambda item: (-float(item["score"]), str(item["relative_path"]))
            )
            group["matched_pdfs"] = group["matched_pdfs"][:match_limit]
            candidates.append(group)
        candidates.sort(
            key=lambda item: (-float(item["score"]), str(item["group_path"]))
        )

        selected = candidates[:group_limit]
        prepared_groups: list[dict[str, Any]] = []
        partial = False
        for candidate in selected:
            group_path = str(candidate["group_path"])
            sync = self.kb_sync(group_path=group_path)
            partial = partial or sync["status"] != "ok"
            context = self.kb_get_group_context(
                group_path,
                max_chars=context_limit,
            )
            note = self.kb_get_knowledge_note(group_path, max_chars=2_000)
            searches: list[dict[str, Any]] = []
            for term in terms[:8]:
                result = self.kb_search(term, group_path=group_path, limit=10)
                searches.append(
                    {
                        "query": term,
                        "count": result["count"],
                        "hits": result["hits"],
                    }
                )
            prepared_groups.append(
                {
                    **candidate,
                    "sync": sync,
                    "knowledge_note_status": note["status"],
                    "knowledge_note_digest": note["digest"],
                    "knowledge_note_wikilinks": note["wikilinks"],
                    "searches": searches,
                    "context": context,
                    "requires_note_synthesis": note["status"] == "missing",
                }
            )

        status = "no_match" if not selected else ("partial" if partial else "ok")
        return {
            "status": status,
            "query": clean_query,
            "search_terms": terms,
            "required_terms": required,
            "scanned_pdf_count": len(discovered),
            "candidate_group_count": len(candidates),
            "selected_group_count": len(selected),
            "candidate_groups": candidates[:50],
            "prepared_groups": prepared_groups,
            "pending_knowledge_notes": [
                item["knowledge_note"]
                for item in prepared_groups
                if item["requires_note_synthesis"]
            ],
            "next_action": (
                "Synthesize each prepared group from page-located context with the two "
                "workflow agents, then call kb_write_knowledge_note with apply=false."
                if selected
                else "Refine search_terms or verify the configured vault path."
            ),
            "rules": {
                "whole_vault_fulltext_sync_performed": False,
                "selected_groups_synced": True,
                "knowledge_notes_written": False,
                "preview_required_before_write": True,
            },
        }

    def _knowledge_note_path(self, group_path: str) -> tuple[str, Path]:
        group = normalize_group_path(group_path)
        notes_root = ensure_within(self.config.notes_path, self.config.vault_path)
        note_path = ensure_within(
            notes_root / knowledge_note_filename(group), notes_root
        )
        return group, note_path

    @staticmethod
    def _read_note(path: Path) -> str:
        return path.read_text(encoding="utf-8-sig", errors="replace")

    def kb_get_knowledge_note(
        self, group_path: str, *, max_chars: int | None = None
    ) -> dict[str, Any]:
        """Read one deterministic group note as a non-evidentiary reasoning lead."""

        group, note_path = self._knowledge_note_path(group_path)
        budget = min(max_chars or self.config.max_chars, self.config.max_chars)
        if budget <= 0:
            raise KnowledgeBaseError("max_chars must be positive")
        if not note_path.exists():
            return {
                "status": "missing",
                "group_path": group,
                "note_name": note_path.name,
                "note_path": str(note_path),
                "evidence_level": "lead_only",
                "content": "",
                "digest": None,
                "wikilinks": [],
                "truncated": False,
            }
        if not note_path.is_file():
            raise KnowledgeBaseError(f"Knowledge-note target is not a file: {note_path}")
        content = self._read_note(note_path)
        excerpt = content[:budget]
        return {
            "status": "ok",
            "group_path": group,
            "note_name": note_path.name,
            "note_path": str(note_path),
            "evidence_level": "lead_only",
            "content": excerpt,
            "digest": canonical_hash(content, prefix="note_"),
            "wikilinks": sorted(set(WIKILINK_RE.findall(content))),
            "truncated": len(excerpt) < len(content),
        }

    def kb_search_notes(
        self,
        query: str,
        *,
        limit: int = 20,
        max_chars_per_note: int = 2_000,
    ) -> dict[str, Any]:
        """Search generated group notes live; note text remains a lead, not evidence."""

        needle = query.strip().casefold()
        if not needle:
            return {"status": "ok", "query": query, "count": 0, "hits": []}
        capped_limit = max(1, min(int(limit), 100))
        snippet_limit = max(200, min(int(max_chars_per_note), 10_000))
        notes_root = ensure_within(self.config.notes_path, self.config.vault_path)
        if not notes_root.is_dir():
            return {"status": "ok", "query": query, "count": 0, "hits": []}

        hits: list[dict[str, Any]] = []
        for candidate in sorted(notes_root.glob("*.md"), key=lambda path: path.name.casefold()):
            note_path = ensure_within(candidate, notes_root)
            if not note_path.is_file():
                continue
            content = self._read_note(note_path)
            haystack = f"{note_path.stem}\n{content}".casefold()
            position = haystack.find(needle)
            if position < 0:
                continue
            content_position = content.casefold().find(needle)
            if content_position < 0:
                start = 0
            else:
                start = max(0, content_position - 240)
            snippet = content[start : start + snippet_limit]
            hits.append(
                {
                    "note_name": note_path.name,
                    "note_path": str(note_path),
                    "evidence_level": "lead_only",
                    "digest": canonical_hash(content, prefix="note_"),
                    "snippet": snippet,
                    "wikilinks": sorted(set(WIKILINK_RE.findall(content))),
                    "truncated": start > 0 or start + len(snippet) < len(content),
                }
            )
            if len(hits) >= capped_limit:
                break
        return {"status": "ok", "query": query, "count": len(hits), "hits": hits}

    def kb_search(
        self,
        query: str,
        *,
        group_path: str | None = None,
        evidence_levels: Sequence[str] | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        normalized_group = (
            normalize_group_path(group_path) if group_path is not None else None
        )
        clean_levels = list(evidence_levels or [])
        invalid = sorted(set(clean_levels) - EVIDENCE_LEVELS)
        if invalid:
            raise KnowledgeBaseError(f"Unsupported evidence levels: {', '.join(invalid)}")
        capped_limit = max(1, min(int(limit), 100))
        hits = self.database.search(
            query,
            group_path=normalized_group,
            evidence_levels=clean_levels,
            limit=capped_limit,
        )
        return {
            "status": "ok",
            "query": query,
            "group_path": normalized_group,
            "count": len(hits),
            "hits": [
                {
                    **{key: value for key, value in hit.items() if key != "document"},
                    "document": _document_view(hit["document"]),
                    "evidence_level": hit["document"]["evidence_level"],
                }
                for hit in hits
            ],
        }

    def kb_get_document(
        self,
        *,
        document_id: int | None = None,
        relative_path: str | None = None,
        page_start: int | None = None,
        page_end: int | None = None,
        max_chars: int | None = None,
    ) -> dict[str, Any]:
        if relative_path is not None:
            relative_path = relative_path.replace("\\", "/").lstrip("/")
            if ".." in Path(relative_path).parts:
                raise PathSafetyError("relative_path cannot contain '..'")
        document = self.database.get_document(
            document_id=document_id, relative_path=relative_path
        )
        if document is None:
            raise KnowledgeBaseError("Document not found in the derived cache")
        if page_start is not None and page_start < 1:
            raise KnowledgeBaseError("page_start must be at least 1")
        if page_end is not None and page_end < 1:
            raise KnowledgeBaseError("page_end must be at least 1")
        if page_start and page_end and page_start > page_end:
            raise KnowledgeBaseError("page_start cannot exceed page_end")
        budget = min(max_chars or self.config.max_chars, self.config.max_chars)
        if budget <= 0:
            raise KnowledgeBaseError("max_chars must be positive")
        output_pages: list[dict[str, Any]] = []
        used = 0
        truncated = False
        for page in self.database.get_pages(
            int(document["id"]), page_start=page_start, page_end=page_end
        ):
            text = str(page["text"])
            remaining = budget - used
            if remaining <= 0:
                truncated = True
                break
            excerpt = text[:remaining]
            output_pages.append(
                {
                    "page": int(page["page_number"]),
                    "locator": f"p. {int(page['page_number'])}",
                    "text": excerpt,
                    "truncated": len(excerpt) < len(text),
                }
            )
            used += len(excerpt)
            if len(excerpt) < len(text):
                truncated = True
                break
        return {
            "status": "ok",
            "document": _document_view(document),
            "evidence_level": document["evidence_level"],
            "pages": output_pages,
            "returned_chars": used,
            "truncated": truncated,
        }

    @staticmethod
    def _decode_cursor(cursor: str | None) -> tuple[int, int, int]:
        if cursor is None or cursor == "":
            return 0, 0, 0
        match = CURSOR_RE.fullmatch(cursor)
        if not match:
            raise KnowledgeBaseError("Invalid group-context cursor")
        return tuple(int(value) for value in match.groups())  # type: ignore[return-value]

    def kb_get_group_context(
        self,
        group_path: str,
        *,
        cursor: str | None = None,
        max_documents: int | None = None,
        max_chars: int | None = None,
    ) -> dict[str, Any]:
        group = normalize_group_path(group_path)
        documents = self.database.list_documents(group)
        if not documents:
            raise KnowledgeBaseError(f"No indexed documents in group: {group or '根目录'}")
        document_limit = min(
            max_documents or self.config.max_group_documents,
            self.config.max_group_documents,
        )
        char_limit = min(max_chars or self.config.max_chars, self.config.max_chars)
        if document_limit <= 0 or char_limit <= 0:
            raise KnowledgeBaseError("Batch limits must be positive")

        document_index, page_index, char_offset = self._decode_cursor(cursor)
        if document_index >= len(documents):
            raise KnowledgeBaseError("Group-context cursor is beyond the group")

        touched: list[dict[str, Any]] = []
        touched_ids: set[int] = set()
        page_entries: list[dict[str, Any]] = []
        used_chars = 0

        while document_index < len(documents):
            document = documents[document_index]
            doc_id = int(document["id"])
            if doc_id not in touched_ids:
                if len(touched_ids) >= document_limit:
                    break
                touched_ids.add(doc_id)
                touched.append(_document_view(document))

            pages = self.database.get_pages(doc_id)
            if not pages:
                document_index += 1
                page_index = 0
                char_offset = 0
                continue
            if page_index >= len(pages):
                document_index += 1
                page_index = 0
                char_offset = 0
                continue

            page = pages[page_index]
            text = str(page["text"])
            if char_offset >= len(text):
                page_index += 1
                char_offset = 0
                continue
            remaining = char_limit - used_chars
            if remaining <= 0:
                break
            excerpt = text[char_offset : char_offset + remaining]
            end_offset = char_offset + len(excerpt)
            page_entries.append(
                {
                    "document_id": doc_id,
                    "relative_path": document["relative_path"],
                    "filename": document["filename"],
                    "page": int(page["page_number"]),
                    "locator": f"p. {int(page['page_number'])}",
                    "char_start": char_offset,
                    "char_end": end_offset,
                    "text": excerpt,
                    "truncated": end_offset < len(text),
                    "evidence_level": document["evidence_level"],
                }
            )
            used_chars += len(excerpt)
            if end_offset < len(text):
                char_offset = end_offset
                break
            page_index += 1
            char_offset = 0
            if page_index >= len(pages):
                document_index += 1
                page_index = 0

        done = document_index >= len(documents)
        next_cursor = None if done else f"{document_index}:{page_index}:{char_offset}"
        rendered: list[str] = []
        last_document: int | None = None
        for entry in page_entries:
            if entry["document_id"] != last_document:
                rendered.append(f"### {entry['filename']}")
                last_document = int(entry["document_id"])
            rendered.append(f"#### {entry['locator']}\n{entry['text']}")
        return {
            "status": "ok",
            "group_path": group,
            "knowledge_note": knowledge_note_filename(group),
            "document_count": len(documents),
            "documents": touched,
            "pages": page_entries,
            "rendered_context": "\n\n".join(rendered),
            "returned_chars": used_chars,
            "cursor": cursor,
            "next_cursor": next_cursor,
            "done": done,
            "limits": {"max_documents": document_limit, "max_chars": char_limit},
        }

    def kb_related_groups(self, group_path: str, *, limit: int = 8) -> dict[str, Any]:
        group = normalize_group_path(group_path)
        groups = [str(row["group_path"]) for row in self.database.list_groups()]
        if group not in groups:
            raise KnowledgeBaseError(f"Unknown indexed group: {group or '根目录'}")
        source_tokens = tokenize_for_similarity(self.database.sample_group_text(group))
        related: list[dict[str, Any]] = []
        for candidate in groups:
            if candidate == group:
                continue
            candidate_tokens = tokenize_for_similarity(
                self.database.sample_group_text(candidate)
            )
            shared = source_tokens & candidate_tokens
            if not shared:
                continue
            denominator = math.sqrt(max(1, len(source_tokens)) * max(1, len(candidate_tokens)))
            score = len(shared) / denominator
            related.append(
                {
                    "group_path": candidate,
                    "knowledge_note": knowledge_note_filename(candidate),
                    "score": round(score, 6),
                    "shared_terms": sorted(shared, key=lambda value: (len(value), value))[:12],
                }
            )
        related.sort(key=lambda item: (-float(item["score"]), str(item["group_path"])))
        return {
            "status": "ok",
            "group_path": group,
            "related": related[: max(1, min(int(limit), 50))],
        }

    def kb_write_knowledge_note(
        self,
        group_path: str,
        analytical_body: str,
        *,
        related_groups: Sequence[str] | None = None,
        apply: bool = False,
        overwrite: bool = False,
        expected_existing_digest: str | None = None,
        source_annotations: dict[str, dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        group = normalize_group_path(group_path)
        documents = self.database.list_documents(group)
        if not documents:
            raise KnowledgeBaseError(f"Cannot write a note for an unknown group: {group}")
        body = analytical_body.replace("\r\n", "\n").strip()
        if not body:
            raise KnowledgeBaseError("analytical_body cannot be empty")

        known_groups = {str(row["group_path"]) for row in self.database.list_groups()}
        related: list[str] = []
        for value in related_groups or []:
            normalized = normalize_group_path(value)
            if normalized == group:
                continue
            if normalized not in known_groups:
                raise KnowledgeBaseError(f"Unknown related group: {normalized}")
            if normalized not in related:
                related.append(normalized)
        related.sort()

        note_name = knowledge_note_filename(group)
        notes_root = ensure_within(self.config.notes_path, self.config.vault_path)
        note_path = ensure_within(notes_root / note_name, notes_root)
        if note_path.exists() and not note_path.is_file():
            raise KnowledgeBaseError(f"Knowledge-note target is not a file: {note_path}")
        existing_content = self._read_note(note_path) if note_path.is_file() else None
        existing_digest = (
            canonical_hash(existing_content, prefix="note_")
            if existing_content is not None
            else None
        )
        source_paths = sorted(str(doc["relative_path"]) for doc in documents)
        related_note_stems = [Path(knowledge_note_filename(item)).stem for item in related]
        annotations: dict[str, dict[str, str]] = {}
        for raw_path, raw_annotation in (source_annotations or {}).items():
            normalized_path = str(raw_path).replace("\\", "/").lstrip("/")
            if normalized_path not in source_paths:
                raise KnowledgeBaseError(
                    f"source_annotations contains an unknown PDF: {normalized_path}"
                )
            annotation = {str(key): str(value) for key, value in raw_annotation.items()}
            literature_type = annotation.get("literature_type", "unknown")
            if literature_type not in LITERATURE_TYPES:
                raise KnowledgeBaseError(
                    f"Unsupported literature type for {normalized_path}: {literature_type}"
                )
            annotation["literature_type"] = literature_type
            annotations[normalized_path] = annotation

        source_snapshot = canonical_hash(
            [
                {
                    "relative_path": document["relative_path"],
                    "size": document["size"],
                    "mtime_ns": document["mtime_ns"],
                    "doi": document["doi"],
                }
                for document in documents
            ],
            prefix="snapshot_",
        )
        indexed_at = max(str(document["indexed_at"]) for document in documents)
        category_key = Path(note_name).stem
        root_id = canonical_hash(str(self.config.vault_path), prefix="root_")

        header = [
            "---",
            "type: category-knowledge",
            "schema_version: 1",
            f"category_path: {yaml_scalar(group)}",
            f"category_key: {yaml_scalar(category_key)}",
            f"source_root_id: {yaml_scalar(root_id)}",
            f"source_count: {len(source_paths)}",
            f"source_snapshot: {yaml_scalar(source_snapshot)}",
            "status: reviewed",
            f"generated_at: {yaml_scalar(indexed_at)}",
            f"updated_at: {yaml_scalar(indexed_at)}",
            "generated_by: research-knowledge-workflow",
            "aliases: []",
            "tags: []",
            "source_pdfs:",
        ]
        header.extend(f"  - {yaml_scalar(path)}" for path in source_paths)
        if related_note_stems:
            header.append("related_notes:")
            header.extend(f"  - {yaml_scalar(name)}" for name in related_note_stems)
        else:
            header.append("related_notes: []")
        header.extend(["---", ""])

        generated = [
            GENERATED_BEGIN,
            f"# {group or '根目录'}",
            "",
            body,
            "",
            "## 关联知识笔记",
            "",
        ]
        if related_note_stems:
            generated.extend(f"- [[{name}]]" for name in related_note_stems)
        else:
            generated.append("- 暂无")
        generated.extend(
            [
                "",
                "## 来源清单",
                "",
                "| Source ID | Paper | Type | Local PDF | Evidence coverage | Zotero reference |",
                "|---|---|---|---|---|---|",
            ]
        )
        for index, document in enumerate(documents, start=1):
            relative_path = str(document["relative_path"])
            annotation = annotations.get(relative_path, {})
            literature_type = annotation.get("literature_type", "unknown")
            citekey = annotation.get("citekey", "")
            title = str(document["inferred_title"]).replace("|", "\\|")
            link_label = Path(relative_path).name.replace("|", "\\|")
            reference = f"`@{citekey}`" if citekey else "unmatched"
            coverage = f"{document['page_count']} pages; {document['evidence_level']}"
            generated.append(
                f"| S{index:03d} | {title} | `{literature_type}` | "
                f"[[{relative_path}|{link_label}]] | {coverage} | {reference} |"
            )
        generated.extend(["", GENERATED_END])

        default_manual_tail = (
            "\n\n## My Notes\n\n"
            "<!-- User-authored content; never replace automatically. -->\n"
        )
        update_mode = "create"
        managed_existing = False
        manual_tail = default_manual_tail
        if existing_content is not None:
            if (
                existing_content.count(GENERATED_BEGIN) == 1
                and existing_content.count(GENERATED_END) == 1
            ):
                managed_existing = True
                update_mode = "replace_generated_block"
                manual_tail = existing_content.split(GENERATED_END, 1)[1]
                if not manual_tail.strip():
                    manual_tail = default_manual_tail
            else:
                update_mode = "adoption_required"

        content = "\n".join(header + generated) + manual_tail

        result = {
            "status": "preview" if not apply else "written",
            "apply": apply,
            "overwrite": overwrite,
            "group_path": group,
            "note_name": note_name,
            "note_path": str(note_path),
            "exists": note_path.exists(),
            "existing_digest": existing_digest,
            "existing_content": existing_content,
            "source_pdf_count": len(source_paths),
            "source_snapshot": source_snapshot,
            "related_notes": related_note_stems,
            "update_mode": update_mode,
            "managed_existing": managed_existing,
            "content": content,
        }
        if not apply:
            result["would_overwrite"] = note_path.exists()
            return result
        if note_path.exists() and not overwrite:
            result.update(
                {
                    "status": "conflict",
                    "written": False,
                    "error": "Knowledge note already exists; set overwrite=true explicitly",
                }
            )
            return result
        if note_path.exists() and overwrite:
            if not managed_existing:
                result.update(
                    {
                        "status": "conflict",
                        "written": False,
                        "error": (
                            "Existing note has no valid managed-block markers; preview a "
                            "non-destructive adoption before applying"
                        ),
                    }
                )
                return result
            if expected_existing_digest is None:
                result.update(
                    {
                        "status": "conflict",
                        "written": False,
                        "error": (
                            "expected_existing_digest is required when overwriting an "
                            "existing knowledge note"
                        ),
                    }
                )
                return result
            if expected_existing_digest != existing_digest:
                result.update(
                    {
                        "status": "conflict",
                        "written": False,
                        "error": "Knowledge note changed after preview",
                    }
                )
                return result
        elif expected_existing_digest is not None:
            result.update(
                {
                    "status": "conflict",
                    "written": False,
                    "error": "Knowledge note no longer exists as it did at preview time",
                }
            )
            return result

        notes_root.mkdir(parents=True, exist_ok=True)
        ensure_within(notes_root.resolve(), self.config.vault_path)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=notes_root, delete=False, suffix=".tmp"
        ) as handle:
            handle.write(content)
            temporary_path = Path(handle.name)
        try:
            current_content = self._read_note(note_path) if note_path.is_file() else None
            current_digest = (
                canonical_hash(current_content, prefix="note_")
                if current_content is not None
                else None
            )
            if current_digest != existing_digest:
                raise KnowledgeBaseError("Knowledge note changed during the apply operation")
            temporary_path.replace(note_path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
        result.update({"written": True, "exists": True})
        return result

    def _match_zotero_item(self, item: dict[str, Any]) -> dict[str, Any]:
        documents = self.database.list_documents()
        doi = item.get("doi")
        if doi:
            doi_matches = [doc for doc in documents if doc.get("doi") == doi]
            if len(doi_matches) == 1:
                return {
                    "status": "exact",
                    "basis": "doi",
                    "documents": [_document_view(doi_matches[0])],
                }
            if len(doi_matches) > 1:
                return {
                    "status": "conflict",
                    "basis": "duplicate_doi",
                    "documents": [_document_view(doc) for doc in doi_matches],
                }

        target_title = normalize_title(str(item.get("title", "")))
        target_year = item.get("year")
        candidates: list[tuple[float, dict[str, Any]]] = []
        if target_title and target_year:
            for document in documents:
                if document.get("year") != target_year:
                    continue
                local_title = str(document.get("normalized_title") or "")
                if not local_title:
                    continue
                ratio = SequenceMatcher(None, target_title, local_title).ratio()
                if local_title == target_title or (
                    min(len(local_title), len(target_title)) >= 12 and ratio >= 0.95
                ):
                    candidates.append((ratio, document))
        candidates.sort(key=lambda pair: (-pair[0], str(pair[1]["relative_path"])))
        if candidates:
            best_score = candidates[0][0]
            best = [doc for score, doc in candidates if abs(score - best_score) < 0.005]
            conflicting_doi = [doc for doc in best if doi and doc.get("doi") and doc["doi"] != doi]
            if len(best) > 1 or conflicting_doi:
                return {
                    "status": "conflict",
                    "basis": "title_year_ambiguous",
                    "score": round(best_score, 4),
                    "documents": [_document_view(doc) for doc in best],
                }
            return {
                "status": "probable",
                "basis": "normalized_title_year",
                "score": round(best_score, 4),
                "documents": [_document_view(best[0])],
            }
        return {"status": "unmatched", "basis": None, "documents": []}

    def kb_zotero_search(
        self,
        query: str,
        *,
        limit: int = 20,
        include_children: bool = True,
        include_citekeys: bool = True,
    ) -> dict[str, Any]:
        result = self.zotero.search(
            query,
            limit=limit,
            include_children=include_children,
            include_citekeys=include_citekeys,
        )
        summary_needed: list[dict[str, Any]] = []
        for item in result["items"]:
            match = self._match_zotero_item(item)
            item["local_match"] = match
            item["effective_evidence_source"] = "zotero"
            if match["status"] in {"exact", "probable"} and match["documents"]:
                local_level = match["documents"][0]["evidence_level"]
                if local_level == "fulltext":
                    item["effective_evidence_level"] = "fulltext"
                    item["effective_evidence_source"] = "matched_local_pdf"
                    item["summary_needed"] = False
                else:
                    item["effective_evidence_level"] = item["evidence_level"]
            else:
                item["effective_evidence_level"] = item["evidence_level"]
            if item["summary_needed"]:
                summary_needed.append(
                    {
                        "item_key": item["item_key"],
                        "title": item["title"],
                        "year": item["year"],
                        "doi": item["doi"],
                        "citekey": item["citekey"],
                        "reason": "metadata_only",
                        "recommended_action": "invoke gs-skill on demand to verify the abstract",
                    }
                )
        result["summary_needed"] = summary_needed
        return result

    def kb_build_evidence_pack(
        self,
        query: str,
        *,
        group_paths: Sequence[str] | None = None,
        include_zotero: bool = True,
        include_notes: bool = True,
        local_limit: int = 20,
        zotero_limit: int = 20,
        notes_limit: int = 10,
    ) -> dict[str, Any]:
        local = self.kb_search(query, limit=local_limit)
        notes = self.kb_search_notes(query, limit=notes_limit) if include_notes else None
        normalized_groups = [normalize_group_path(group) for group in (group_paths or [])]
        group_contexts: list[dict[str, Any]] = []
        if normalized_groups:
            per_group_chars = max(1, self.config.max_chars // len(normalized_groups))
            for group in normalized_groups:
                group_contexts.append(
                    self.kb_get_group_context(group, max_chars=per_group_chars)
                )

        limitations: list[str] = []
        zotero: dict[str, Any] | None = None
        if include_zotero:
            try:
                zotero = self.kb_zotero_search(query, limit=zotero_limit)
            except ZoteroUnavailable as exc:
                limitations.append(str(exc))

        evidence: list[dict[str, Any]] = []
        sequence = 1
        for context in group_contexts:
            documents_by_id = {
                int(document["id"]): document for document in context["documents"]
            }
            for page in context["pages"]:
                document = documents_by_id.get(int(page["document_id"]))
                if document is None:
                    document = _document_view(
                        self.database.get_document(document_id=int(page["document_id"])) or {}
                    )
                evidence.append(
                    {
                        "evidence_id": f"E{sequence:03d}",
                        "scope": "local_pdf",
                        "level": page["evidence_level"],
                        "title": document.get("inferred_title"),
                        "year": document.get("year"),
                        "locator": {
                            "document_id": page["document_id"],
                            "path": document.get("absolute_path"),
                            "relative_path": page["relative_path"],
                            "page": page["page"],
                            "page_label": page["locator"],
                            "char_start": page["char_start"],
                            "char_end": page["char_end"],
                        },
                        "retrieved_text": page["text"],
                        "match_scope": "selected_group_context",
                    }
                )
                sequence += 1
        for hit in local["hits"]:
            document = hit["document"]
            evidence.append(
                {
                    "evidence_id": f"E{sequence:03d}",
                    "scope": "local_pdf",
                    "level": (
                        document["evidence_level"]
                        if hit["page"] is not None
                        else "metadata_only"
                    ),
                    "source_evidence_level": document["evidence_level"],
                    "title": document["inferred_title"],
                    "year": document["year"],
                    "locator": {
                        "document_id": document["id"],
                        "path": document["absolute_path"],
                        "relative_path": document["relative_path"],
                        "page": hit["page"],
                        "page_label": hit["locator"],
                    },
                    "retrieved_text": hit["snippet"],
                    "match_scope": hit["match_scope"],
                }
            )
            sequence += 1
        if notes:
            for note in notes["hits"]:
                evidence.append(
                    {
                        "evidence_id": f"E{sequence:03d}",
                        "scope": "knowledge_note",
                        "level": "lead_only",
                        "title": Path(note["note_name"]).stem,
                        "year": None,
                        "locator": {
                            "note_name": note["note_name"],
                            "path": note["note_path"],
                            "digest": note["digest"],
                        },
                        "retrieved_text": note["snippet"],
                        "wikilinks": note["wikilinks"],
                    }
                )
                sequence += 1
        if zotero:
            for item in zotero["items"]:
                evidence.append(
                    {
                        "evidence_id": f"E{sequence:03d}",
                        "scope": "zotero",
                        "level": item["evidence_level"],
                        "effective_evidence_level": item["effective_evidence_level"],
                        "effective_evidence_source": item["effective_evidence_source"],
                        "title": item["title"],
                        "year": item["year"],
                        "locator": {
                            "item_key": item["item_key"],
                            "citekey": item["citekey"],
                            "doi": item["doi"],
                            "zotero_uri": item["zotero_uri"],
                        },
                        "retrieved_text": item["abstract"] or None,
                        "local_match": item["local_match"],
                    }
                )
                sequence += 1

        stable_payload = {
            "query": query,
            "groups": normalized_groups,
            "evidence": evidence,
            "summary_needed": zotero["summary_needed"] if zotero else [],
        }
        retrieval_trace = [
            {
                "trace_id": "R001",
                "source": "local_pdf_index",
                "query": query,
                "groups": normalized_groups,
                "hit_count": local["count"],
            },
            {
                "trace_id": "R002",
                "source": "obsidian_knowledge_notes",
                "query": query,
                "enabled": include_notes,
                "hit_count": notes["count"] if notes else 0,
            },
            {
                "trace_id": "R003",
                "source": "zotero_local_api",
                "query": query,
                "enabled": include_zotero,
                "hit_count": zotero["count"] if zotero else 0,
                "status": "partial" if include_zotero and zotero is None else "ok",
            },
        ]
        return {
            "status": "ok" if not limitations else "partial",
            "pack_id": canonical_hash(stable_payload, prefix="ep_"),
            "version": 1,
            "created_at": utc_now(),
            "query": query,
            "groups": normalized_groups,
            "evidence": evidence,
            "group_contexts": group_contexts,
            "summary_needed": zotero["summary_needed"] if zotero else [],
            "retrieval_trace": retrieval_trace,
            "coverage_limitations": limitations,
            "rules": {
                "obsidian_notes_are_leads": True,
                "metadata_only_cannot_support_claims": True,
                "gs_skill_called_inside_mcp": False,
                "page_locators_required_for_local_fulltext_claims": True,
            },
        }

    def kb_project_context(
        self,
        project_path: str = "",
        *,
        files: Sequence[str] | None = None,
        max_chars: int | None = None,
    ) -> dict[str, Any]:
        root = self.config.manuscripts_root
        if root is None:
            return {
                "status": "not_configured",
                "error": "manuscripts_root is not configured",
                "files": [],
            }
        root = root.resolve()
        if not root.is_dir():
            return {
                "status": "unavailable",
                "error": f"manuscripts_root does not exist: {root}",
                "files": [],
            }
        project = ensure_within(root / project_path, root)
        if not project.exists():
            raise KnowledgeBaseError(f"Project path does not exist: {project_path}")
        budget = min(max_chars or self.config.max_chars, self.config.max_chars)
        if budget <= 0:
            raise KnowledgeBaseError("max_chars must be positive")

        candidates: list[Path] = []
        if files:
            base = project if project.is_dir() else project.parent
            for value in files:
                candidate = ensure_within(base / value, project if project.is_dir() else base)
                if candidate.is_file() and candidate.suffix.casefold() in PROJECT_SUFFIXES:
                    candidates.append(candidate)
        elif project.is_file():
            if project.suffix.casefold() in PROJECT_SUFFIXES:
                candidates = [project]
        else:
            for candidate in project.rglob("*"):
                if not candidate.is_file() or candidate.suffix.casefold() not in PROJECT_SUFFIXES:
                    continue
                relative_parts = candidate.relative_to(project).parts
                if any(part.casefold() in IGNORED_PROJECT_DIRS for part in relative_parts):
                    continue
                candidates.append(candidate)
        candidates = sorted(set(candidates), key=lambda path: path.as_posix().casefold())[:100]

        outputs: list[dict[str, Any]] = []
        used = 0
        for candidate in candidates:
            if used >= budget:
                break
            try:
                text = self._read_project_file(candidate)
                error = None
            except Exception as exc:
                text = ""
                error = f"{type(exc).__name__}: {exc}"
            excerpt = text[: budget - used]
            used += len(excerpt)
            outputs.append(
                {
                    "path": str(candidate),
                    "relative_path": candidate.relative_to(root).as_posix(),
                    "suffix": candidate.suffix.casefold(),
                    "text": excerpt,
                    "truncated": len(excerpt) < len(text),
                    "error": error,
                }
            )
        return {
            "status": "ok",
            "project_path": str(project),
            "files": outputs,
            "returned_chars": used,
            "truncated": len(outputs) < len(candidates)
            or any(bool(item["truncated"]) for item in outputs),
        }

    @staticmethod
    def _read_project_file(path: Path) -> str:
        if path.suffix.casefold() == ".docx":
            with zipfile.ZipFile(path) as archive:
                xml = archive.read("word/document.xml")
            root = ElementTree.fromstring(xml)
            namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            paragraphs: list[str] = []
            for paragraph in root.iter(namespace + "p"):
                text = "".join(node.text or "" for node in paragraph.iter(namespace + "t"))
                if text:
                    paragraphs.append(text)
            return "\n".join(paragraphs)
        raw = path.read_bytes()
        for encoding in ("utf-8", "utf-8-sig", "gb18030"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")
