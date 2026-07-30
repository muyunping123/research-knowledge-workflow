"""Official Python MCP SDK stdio adapter for the core service."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import load_config
from .service import KnowledgeBaseService


logging.basicConfig(
    level=logging.WARNING,
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
LOGGER = logging.getLogger(__name__)

mcp = FastMCP(
    "research-knowledge-workflow",
    instructions=(
        "Read-first access to local Obsidian PDFs, derived page evidence, Zotero metadata, "
        "and explicitly approved group knowledge-note writes. Metadata-only records are leads, "
        "not claim evidence."
    ),
    json_response=True,
)

_config_path: Path | None = None
_service: KnowledgeBaseService | None = None


def configure(config_path: str | Path | None = None) -> None:
    """Set an explicit config path before the first tool invocation."""

    global _config_path, _service
    _config_path = Path(config_path).resolve() if config_path else None
    _service = None


def get_service() -> KnowledgeBaseService:
    global _service
    if _service is None:
        _service = KnowledgeBaseService(load_config(_config_path))
    return _service


@mcp.tool()
def kb_status(check_zotero: bool = True) -> dict[str, Any]:
    """Report configuration, cache, vault, FTS, and optional Zotero status."""

    return get_service().kb_status(check_zotero=check_zotero)


@mcp.tool()
def kb_sync(group_path: str | None = None) -> dict[str, Any]:
    """Incrementally index all PDFs or one selected relative directory subtree."""

    return get_service().kb_sync(group_path=group_path)


@mcp.tool()
def kb_list_groups() -> dict[str, Any]:
    """List indexed relative parent-directory groups and knowledge-note status."""

    return get_service().kb_list_groups()


@mcp.tool()
def kb_get_knowledge_note(
    group_path: str, max_chars: int | None = None
) -> dict[str, Any]:
    """Read one group note as a non-evidentiary reasoning lead."""

    return get_service().kb_get_knowledge_note(group_path, max_chars=max_chars)


@mcp.tool()
def kb_search_notes(
    query: str,
    limit: int = 20,
    max_chars_per_note: int = 2_000,
) -> dict[str, Any]:
    """Search linked Obsidian group notes without treating them as source evidence."""

    return get_service().kb_search_notes(
        query, limit=limit, max_chars_per_note=max_chars_per_note
    )


@mcp.tool()
def kb_search(
    query: str,
    group_path: str | None = None,
    evidence_levels: list[str] | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Search PDF metadata and per-page text with page-level locators."""

    return get_service().kb_search(
        query,
        group_path=group_path,
        evidence_levels=evidence_levels,
        limit=limit,
    )


@mcp.tool()
def kb_get_document(
    document_id: int | None = None,
    relative_path: str | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
    max_chars: int | None = None,
) -> dict[str, Any]:
    """Read indexed page text for one PDF by cache ID or vault-relative path."""

    return get_service().kb_get_document(
        document_id=document_id,
        relative_path=relative_path,
        page_start=page_start,
        page_end=page_end,
        max_chars=max_chars,
    )


@mcp.tool()
def kb_get_group_context(
    group_path: str,
    cursor: str | None = None,
    max_documents: int | None = None,
    max_chars: int | None = None,
) -> dict[str, Any]:
    """Return a bounded PDF-reading batch; follow next_cursor until done."""

    return get_service().kb_get_group_context(
        group_path,
        cursor=cursor,
        max_documents=max_documents,
        max_chars=max_chars,
    )


@mcp.tool()
def kb_related_groups(group_path: str, limit: int = 8) -> dict[str, Any]:
    """Rank other PDF directory groups by lightweight lexical similarity."""

    return get_service().kb_related_groups(group_path, limit=limit)


@mcp.tool()
def kb_write_knowledge_note(
    group_path: str,
    analytical_body: str,
    related_groups: list[str] | None = None,
    apply: bool = False,
    overwrite: bool = False,
    expected_existing_digest: str | None = None,
    source_annotations: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Preview or explicitly write a deterministic, linked group Markdown note."""

    return get_service().kb_write_knowledge_note(
        group_path,
        analytical_body,
        related_groups=related_groups,
        apply=apply,
        overwrite=overwrite,
        expected_existing_digest=expected_existing_digest,
        source_annotations=source_annotations,
    )


@mcp.tool()
def kb_zotero_search(
    query: str,
    limit: int = 20,
    include_children: bool = True,
    include_citekeys: bool = True,
) -> dict[str, Any]:
    """Search Zotero read-only metadata, attachment state, citekeys, and local matches."""

    return get_service().kb_zotero_search(
        query,
        limit=limit,
        include_children=include_children,
        include_citekeys=include_citekeys,
    )


@mcp.tool()
def kb_build_evidence_pack(
    query: str,
    group_paths: list[str] | None = None,
    include_zotero: bool = True,
    include_notes: bool = True,
    local_limit: int = 20,
    zotero_limit: int = 20,
    notes_limit: int = 10,
) -> dict[str, Any]:
    """Build a frozen, provenance-rich evidence pack without calling GS."""

    return get_service().kb_build_evidence_pack(
        query,
        group_paths=group_paths,
        include_zotero=include_zotero,
        include_notes=include_notes,
        local_limit=local_limit,
        zotero_limit=zotero_limit,
        notes_limit=notes_limit,
    )


@mcp.tool()
def kb_project_context(
    project_path: str = "",
    files: list[str] | None = None,
    max_chars: int | None = None,
) -> dict[str, Any]:
    """Read bounded Word/LaTeX/Markdown project context under manuscripts_root."""

    return get_service().kb_project_context(
        project_path,
        files=files,
        max_chars=max_chars,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Research Knowledge Workflow MCP stdio server")
    parser.add_argument("--config", help="Path to the TOML configuration file")
    arguments = parser.parse_args()
    configure(arguments.config)
    LOGGER.info("Starting research-knowledge-workflow over stdio")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
