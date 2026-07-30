"""SQLite derived cache with optional FTS5 page search."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Any, Iterator, Sequence


SCHEMA_VERSION = 1
EVIDENCE_LEVELS = {"fulltext", "abstract_only", "metadata_only", "needs_ocr"}


class Database:
    """Small connection-per-operation wrapper around the derived index."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS cache_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY,
                    relative_path TEXT NOT NULL UNIQUE,
                    absolute_path TEXT NOT NULL,
                    group_path TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    inferred_title TEXT NOT NULL,
                    normalized_title TEXT NOT NULL,
                    year INTEGER,
                    doi TEXT,
                    size INTEGER NOT NULL,
                    mtime_ns INTEGER NOT NULL,
                    page_count INTEGER NOT NULL DEFAULT 0,
                    extracted_chars INTEGER NOT NULL DEFAULT 0,
                    evidence_level TEXT NOT NULL,
                    extraction_error TEXT,
                    indexed_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_documents_group
                    ON documents(group_path, relative_path);
                CREATE INDEX IF NOT EXISTS idx_documents_title_year
                    ON documents(normalized_title, year);
                CREATE INDEX IF NOT EXISTS idx_documents_doi
                    ON documents(doi);

                CREATE TABLE IF NOT EXISTS page_chunks (
                    id INTEGER PRIMARY KEY,
                    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    page_number INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    char_count INTEGER NOT NULL,
                    UNIQUE(document_id, page_number)
                );

                CREATE INDEX IF NOT EXISTS idx_page_chunks_document
                    ON page_chunks(document_id, page_number);
                """
            )
            current = connection.execute("PRAGMA user_version").fetchone()[0]
            if current not in (0, SCHEMA_VERSION):
                raise RuntimeError(
                    f"Unsupported cache schema {current}; expected {SCHEMA_VERSION}. "
                    "The cache is derived and can be removed and rebuilt."
                )
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            if self._meta(connection, "fts_mode") is None:
                self._initialize_fts(connection)

    @staticmethod
    def _meta(connection: sqlite3.Connection, key: str) -> str | None:
        row = connection.execute(
            "SELECT value FROM cache_meta WHERE key = ?", (key,)
        ).fetchone()
        return str(row[0]) if row else None

    @staticmethod
    def _set_meta(connection: sqlite3.Connection, key: str, value: str) -> None:
        connection.execute(
            """
            INSERT INTO cache_meta(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )

    def _initialize_fts(self, connection: sqlite3.Connection) -> None:
        for mode, tokenizer in (("trigram", "trigram"), ("unicode61", "unicode61")):
            try:
                connection.execute(
                    "CREATE VIRTUAL TABLE page_chunks_fts "
                    f"USING fts5(text, document_id UNINDEXED, page_number UNINDEXED, tokenize='{tokenizer}')"
                )
                self._set_meta(connection, "fts_mode", mode)
                return
            except sqlite3.OperationalError:
                try:
                    connection.execute("DROP TABLE IF EXISTS page_chunks_fts")
                except sqlite3.OperationalError:
                    pass
        self._set_meta(connection, "fts_mode", "none")

    @property
    def fts_mode(self) -> str:
        with self.connect() as connection:
            return self._meta(connection, "fts_mode") or "none"

    def get_by_relative_path(self, relative_path: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM documents WHERE relative_path = ?", (relative_path,)
            ).fetchone()
            return dict(row) if row else None

    def upsert_document(
        self,
        metadata: dict[str, Any],
        pages: Sequence[str],
    ) -> int:
        evidence_level = str(metadata["evidence_level"])
        if evidence_level not in EVIDENCE_LEVELS:
            raise ValueError(f"Unsupported evidence level: {evidence_level}")
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT id FROM documents WHERE relative_path = ?",
                (metadata["relative_path"],),
            ).fetchone()
            if existing:
                document_id = int(existing["id"])
                self._delete_page_rows(connection, document_id)
                connection.execute(
                    """
                    UPDATE documents SET
                        absolute_path = :absolute_path,
                        group_path = :group_path,
                        filename = :filename,
                        inferred_title = :inferred_title,
                        normalized_title = :normalized_title,
                        year = :year,
                        doi = :doi,
                        size = :size,
                        mtime_ns = :mtime_ns,
                        page_count = :page_count,
                        extracted_chars = :extracted_chars,
                        evidence_level = :evidence_level,
                        extraction_error = :extraction_error,
                        indexed_at = :indexed_at
                    WHERE relative_path = :relative_path
                    """,
                    metadata,
                )
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO documents(
                        relative_path, absolute_path, group_path, filename,
                        inferred_title, normalized_title, year, doi, size, mtime_ns,
                        page_count, extracted_chars, evidence_level, extraction_error,
                        indexed_at
                    ) VALUES (
                        :relative_path, :absolute_path, :group_path, :filename,
                        :inferred_title, :normalized_title, :year, :doi, :size, :mtime_ns,
                        :page_count, :extracted_chars, :evidence_level, :extraction_error,
                        :indexed_at
                    )
                    """,
                    metadata,
                )
                document_id = int(cursor.lastrowid)

            fts_enabled = self._meta(connection, "fts_mode") != "none"
            for page_number, text in enumerate(pages, start=1):
                cursor = connection.execute(
                    """
                    INSERT INTO page_chunks(document_id, page_number, text, char_count)
                    VALUES (?, ?, ?, ?)
                    """,
                    (document_id, page_number, text, len(text)),
                )
                if fts_enabled and text.strip():
                    connection.execute(
                        """
                        INSERT INTO page_chunks_fts(rowid, text, document_id, page_number)
                        VALUES (?, ?, ?, ?)
                        """,
                        (int(cursor.lastrowid), text, document_id, page_number),
                    )
            return document_id

    def _delete_page_rows(self, connection: sqlite3.Connection, document_id: int) -> None:
        if self._meta(connection, "fts_mode") != "none":
            connection.execute(
                "DELETE FROM page_chunks_fts WHERE document_id = ?", (document_id,)
            )
        connection.execute("DELETE FROM page_chunks WHERE document_id = ?", (document_id,))

    def remove_missing(
        self,
        current_relative_paths: set[str],
        *,
        group_prefix: str | None = None,
    ) -> list[str]:
        removed: list[str] = []
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT id, relative_path, group_path FROM documents"
            ).fetchall()
            for row in rows:
                relative_path = str(row["relative_path"])
                group_path = str(row["group_path"])
                if group_prefix is not None and not (
                    group_path == group_prefix
                    or group_path.startswith(group_prefix + "/")
                ):
                    continue
                if relative_path in current_relative_paths:
                    continue
                document_id = int(row["id"])
                self._delete_page_rows(connection, document_id)
                connection.execute("DELETE FROM documents WHERE id = ?", (document_id,))
                removed.append(relative_path)
        return sorted(removed)

    def stats(self) -> dict[str, Any]:
        with self.connect() as connection:
            document_count = int(
                connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            )
            page_count = int(
                connection.execute("SELECT COUNT(*) FROM page_chunks").fetchone()[0]
            )
            level_rows = connection.execute(
                "SELECT evidence_level, COUNT(*) AS count FROM documents GROUP BY evidence_level"
            ).fetchall()
            return {
                "documents": document_count,
                "pages": page_count,
                "evidence_levels": {
                    str(row["evidence_level"]): int(row["count"]) for row in level_rows
                },
                "fts_mode": self._meta(connection, "fts_mode") or "none",
            }

    def list_documents(self, group_path: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM documents"
        params: tuple[Any, ...] = ()
        if group_path is not None:
            sql += " WHERE group_path = ?"
            params = (group_path,)
        sql += " ORDER BY group_path, relative_path"
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(sql, params).fetchall()]

    def get_document(
        self, *, document_id: int | None = None, relative_path: str | None = None
    ) -> dict[str, Any] | None:
        if (document_id is None) == (relative_path is None):
            raise ValueError("Provide exactly one of document_id or relative_path")
        column, value = (
            ("id", document_id) if document_id is not None else ("relative_path", relative_path)
        )
        with self.connect() as connection:
            row = connection.execute(
                f"SELECT * FROM documents WHERE {column} = ?", (value,)
            ).fetchone()
            return dict(row) if row else None

    def get_pages(
        self,
        document_id: int,
        *,
        page_start: int | None = None,
        page_end: int | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["document_id = ?"]
        params: list[Any] = [document_id]
        if page_start is not None:
            clauses.append("page_number >= ?")
            params.append(page_start)
        if page_end is not None:
            clauses.append("page_number <= ?")
            params.append(page_end)
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT id, document_id, page_number, text, char_count FROM page_chunks "
                f"WHERE {' AND '.join(clauses)} ORDER BY page_number",
                tuple(params),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_groups(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT group_path, COUNT(*) AS document_count,
                       SUM(page_count) AS page_count,
                       SUM(extracted_chars) AS extracted_chars,
                       SUM(CASE WHEN evidence_level = 'needs_ocr' THEN 1 ELSE 0 END) AS needs_ocr
                FROM documents
                GROUP BY group_path
                ORDER BY group_path
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def search(
        self,
        query: str,
        *,
        group_path: str | None = None,
        evidence_levels: Sequence[str] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        query = query.strip()
        if not query:
            return []
        levels = [level for level in (evidence_levels or []) if level in EVIDENCE_LEVELS]
        results: list[dict[str, Any]] = []
        seen: set[tuple[int, int | None]] = set()

        with self.connect() as connection:
            metadata_clauses = [
                "(inferred_title LIKE ? OR filename LIKE ? OR group_path LIKE ? OR doi LIKE ?)"
            ]
            like = f"%{query}%"
            metadata_params: list[Any] = [like, like, like, like]
            if group_path is not None:
                metadata_clauses.append("group_path = ?")
                metadata_params.append(group_path)
            if levels:
                metadata_clauses.append(
                    "evidence_level IN (" + ",".join("?" for _ in levels) + ")"
                )
                metadata_params.extend(levels)
            metadata_rows = connection.execute(
                "SELECT * FROM documents WHERE "
                + " AND ".join(metadata_clauses)
                + " ORDER BY year DESC, relative_path LIMIT ?",
                tuple(metadata_params + [limit]),
            ).fetchall()
            for row in metadata_rows:
                key = (int(row["id"]), None)
                seen.add(key)
                results.append(
                    {
                        "document": dict(row),
                        "page": None,
                        "locator": None,
                        "snippet": None,
                        "match_scope": "metadata",
                        "score": 0.0,
                    }
                )

            remaining = max(0, limit - len(results))
            if remaining == 0:
                return results

            content_rows: list[sqlite3.Row]
            fts_mode = self._meta(connection, "fts_mode") or "none"
            if fts_mode != "none" and (fts_mode != "trigram" or len(query) >= 3):
                fts_clauses = ["page_chunks_fts MATCH ?"]
                fts_params: list[Any] = ['"' + query.replace('"', '""') + '"']
                if group_path is not None:
                    fts_clauses.append("d.group_path = ?")
                    fts_params.append(group_path)
                if levels:
                    fts_clauses.append(
                        "d.evidence_level IN (" + ",".join("?" for _ in levels) + ")"
                    )
                    fts_params.extend(levels)
                try:
                    content_rows = connection.execute(
                        """
                        SELECT d.*, f.page_number AS hit_page,
                               snippet(page_chunks_fts, 0, '[', ']', '...', 24) AS hit_snippet,
                               bm25(page_chunks_fts) AS hit_score
                        FROM page_chunks_fts AS f
                        JOIN documents AS d ON d.id = f.document_id
                        WHERE """
                        + " AND ".join(fts_clauses)
                        + " ORDER BY hit_score LIMIT ?",
                        tuple(fts_params + [remaining * 3]),
                    ).fetchall()
                except sqlite3.OperationalError:
                    content_rows = self._like_page_search(
                        connection, query, group_path, levels, remaining * 3
                    )
            else:
                content_rows = self._like_page_search(
                    connection, query, group_path, levels, remaining * 3
                )

            for row in content_rows:
                page = int(row["hit_page"])
                key = (int(row["id"]), page)
                if key in seen:
                    continue
                seen.add(key)
                document = {key: row[key] for key in row.keys() if not key.startswith("hit_")}
                results.append(
                    {
                        "document": document,
                        "page": page,
                        "locator": f"p. {page}",
                        "snippet": row["hit_snippet"],
                        "match_scope": "fulltext",
                        "score": float(row["hit_score"] or 0.0),
                    }
                )
                if len(results) >= limit:
                    break
        return results

    @staticmethod
    def _like_page_search(
        connection: sqlite3.Connection,
        query: str,
        group_path: str | None,
        levels: Sequence[str],
        limit: int,
    ) -> list[sqlite3.Row]:
        clauses = ["p.text LIKE ?"]
        params: list[Any] = [f"%{query}%"]
        if group_path is not None:
            clauses.append("d.group_path = ?")
            params.append(group_path)
        if levels:
            clauses.append("d.evidence_level IN (" + ",".join("?" for _ in levels) + ")")
            params.extend(levels)
        return connection.execute(
            """
            SELECT d.*, p.page_number AS hit_page,
                   substr(p.text, max(1, instr(lower(p.text), lower(?)) - 120), 360) AS hit_snippet,
                   0.0 AS hit_score
            FROM page_chunks AS p
            JOIN documents AS d ON d.id = p.document_id
            WHERE """
            + " AND ".join(clauses)
            + " ORDER BY d.year DESC, d.relative_path, p.page_number LIMIT ?",
            tuple([query] + params + [limit]),
        ).fetchall()

    def sample_group_text(self, group_path: str, max_chars: int = 20_000) -> str:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT d.inferred_title, p.text
                FROM documents AS d
                LEFT JOIN page_chunks AS p ON p.document_id = d.id
                WHERE d.group_path = ?
                ORDER BY d.relative_path, p.page_number
                """,
                (group_path,),
            ).fetchall()
        pieces: list[str] = [group_path]
        used = len(group_path)
        seen_titles: set[str] = set()
        for row in rows:
            title = str(row["inferred_title"])
            if title not in seen_titles:
                pieces.append(title)
                seen_titles.add(title)
                used += len(title)
            text = str(row["text"] or "")
            if used >= max_chars:
                break
            take = text[: max_chars - used]
            pieces.append(take)
            used += len(take)
        return "\n".join(pieces)
