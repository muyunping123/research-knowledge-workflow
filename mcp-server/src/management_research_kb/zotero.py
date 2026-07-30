"""Read-only clients for Zotero's local API and Better BibTeX JSON-RPC."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .errors import ZoteroUnavailable
from .utils import normalize_doi, parse_year


class JsonTransport(Protocol):
    def get_json(self, url: str, headers: dict[str, str]) -> Any: ...

    def post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> Any: ...


@dataclass(slots=True)
class UrllibJsonTransport:
    timeout: float = 8.0

    def get_json(self, url: str, headers: dict[str, str]) -> Any:
        request = Request(url, headers=headers, method="GET")
        return self._open_json(request)

    def post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> Any:
        body = json.dumps(payload).encode("utf-8")
        request = Request(url, data=body, headers=headers, method="POST")
        return self._open_json(request)

    def _open_json(self, request: Request) -> Any:
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise ZoteroUnavailable(
                f"Zotero local API returned HTTP {exc.code}: {detail}"
            ) from exc
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise ZoteroUnavailable(f"Zotero local API is unavailable: {exc}") from exc


class ZoteroClient:
    """A deliberately read-only view over the loopback Zotero services."""

    def __init__(
        self,
        base_url: str,
        *,
        transport: JsonTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        if self.base_url.endswith("/api"):
            self.base_url = self.base_url[:-4]
        self.transport = transport or UrllibJsonTransport()
        self.headers = {
            "Accept": "application/json",
            "Zotero-API-Version": "3",
            "User-Agent": "research-knowledge-workflow-mcp/0.2",
        }

    def status(self) -> dict[str, Any]:
        payload = self.transport.get_json(
            f"{self.base_url}/api/users/0/items/top?limit=1&format=json",
            self.headers,
        )
        if not isinstance(payload, list):
            raise ZoteroUnavailable("Unexpected Zotero status response; expected a JSON list")
        return {
            "available": True,
            "probe": "read_only_top_items",
            "returned_items": len(payload),
        }

    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        include_children: bool = True,
        include_citekeys: bool = True,
    ) -> dict[str, Any]:
        params = urlencode(
            {
                "q": query,
                "qmode": "everything",
                "format": "json",
                "limit": max(1, min(int(limit), 100)),
            }
        )
        payload = self.transport.get_json(
            f"{self.base_url}/api/users/0/items/top?{params}", self.headers
        )
        if not isinstance(payload, list):
            raise ZoteroUnavailable("Unexpected Zotero search response; expected a JSON list")

        raw_items = [item for item in payload if isinstance(item, dict)]
        keys = [str(item.get("key", "")) for item in raw_items if item.get("key")]
        citekeys: dict[str, str] = {}
        bbt_status = "not_requested"
        if include_citekeys and keys:
            try:
                citekeys = self.citation_keys(keys)
                bbt_status = "available"
            except ZoteroUnavailable:
                bbt_status = "unavailable"

        items: list[dict[str, Any]] = []
        for raw_item in raw_items:
            item = self._parse_item(raw_item)
            if item["item_type"] in {"attachment", "note", "annotation"}:
                continue
            item["citekey"] = citekeys.get(item["item_key"])
            children: list[dict[str, Any]] = []
            children_error: str | None = None
            if include_children and item["item_key"]:
                try:
                    children = self.children(item["item_key"])
                except ZoteroUnavailable as exc:
                    children_error = str(exc)
            pdf_attachments = [
                child
                for child in children
                if child.get("item_type") == "attachment"
                and (
                    child.get("content_type") == "application/pdf"
                    or str(child.get("filename", "")).casefold().endswith(".pdf")
                )
            ]
            item["attachment_status"] = {
                "child_count": len(children),
                "pdf_count": len(pdf_attachments),
                "has_pdf": bool(pdf_attachments),
                "pdf_attachments": pdf_attachments,
                "error": children_error,
            }
            if item["abstract"]:
                item["evidence_level"] = "abstract_only"
            else:
                item["evidence_level"] = "metadata_only"
            item["fulltext_attachment_available"] = bool(pdf_attachments)
            item["summary_needed"] = item["evidence_level"] == "metadata_only"
            items.append(item)

        return {
            "status": "ok",
            "query": query,
            "count": len(items),
            "better_bibtex": bbt_status,
            "items": items,
        }

    def children(self, item_key: str) -> list[dict[str, Any]]:
        payload = self.transport.get_json(
            f"{self.base_url}/api/users/0/items/{item_key}/children?format=json",
            self.headers,
        )
        if not isinstance(payload, list):
            raise ZoteroUnavailable(f"Unexpected children response for Zotero item {item_key}")
        children: list[dict[str, Any]] = []
        for raw_child in payload:
            if not isinstance(raw_child, dict):
                continue
            data = raw_child.get("data") or {}
            children.append(
                {
                    "item_key": str(raw_child.get("key", "")),
                    "item_type": str(data.get("itemType", "")),
                    "title": str(data.get("title", "")),
                    "filename": str(data.get("filename", "")),
                    "content_type": str(data.get("contentType", "")),
                    "link_mode": str(data.get("linkMode", "")),
                }
            )
        return children

    def citation_keys(self, item_keys: list[str]) -> dict[str, str]:
        """Call the read-only Better BibTeX item.citationkey method."""

        payload = {
            "jsonrpc": "2.0",
            "method": "item.citationkey",
            "params": [item_keys],
            "id": 1,
        }
        headers = {**self.headers, "Content-Type": "application/json"}
        response = self.transport.post_json(
            f"{self.base_url}/better-bibtex/json-rpc", payload, headers
        )
        if not isinstance(response, dict) or response.get("error"):
            raise ZoteroUnavailable(f"Better BibTeX JSON-RPC error: {response}")
        result = response.get("result")
        if not isinstance(result, dict):
            raise ZoteroUnavailable("Unexpected Better BibTeX citation-key response")
        return {str(key).split(":")[-1]: str(value) for key, value in result.items()}

    @staticmethod
    def _parse_item(raw_item: dict[str, Any]) -> dict[str, Any]:
        data = raw_item.get("data") or {}
        creators: list[str] = []
        for creator in data.get("creators") or []:
            if not isinstance(creator, dict):
                continue
            name = creator.get("name") or " ".join(
                part for part in (creator.get("firstName"), creator.get("lastName")) if part
            )
            if name:
                creators.append(str(name))
        return {
            "item_key": str(raw_item.get("key", "")),
            "library_id": (raw_item.get("library") or {}).get("id"),
            "item_type": str(data.get("itemType", "")),
            "title": str(data.get("title", "")).strip(),
            "abstract": str(data.get("abstractNote", "")).strip(),
            "doi": normalize_doi(data.get("DOI")),
            "date": str(data.get("date", "")),
            "year": parse_year(data.get("date")),
            "creators": creators,
            "publication_title": str(data.get("publicationTitle", "")),
            "url": str(data.get("url", "")),
            "tags": [
                str(tag.get("tag"))
                for tag in (data.get("tags") or [])
                if isinstance(tag, dict) and tag.get("tag")
            ],
            "collections": [str(value) for value in (data.get("collections") or [])],
            "zotero_uri": f"zotero://select/library/items/{raw_item.get('key', '')}",
        }
