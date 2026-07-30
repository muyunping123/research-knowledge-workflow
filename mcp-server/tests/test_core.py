from __future__ import annotations

import copy
import os
from pathlib import Path
import tempfile
import unittest

from management_research_kb.config import Config, ConfigError, load_config
from management_research_kb.errors import PathSafetyError
from management_research_kb.indexer import ExtractedPdf
from management_research_kb.service import KnowledgeBaseService
from management_research_kb.utils import knowledge_note_filename
from management_research_kb.zotero import ZoteroClient


class MockTransport:
    def get_json(self, url: str, headers: dict[str, str]):
        if url.endswith("/api/"):
            return {"version": 3}
        if "/items/top?" in url:
            return [
                {
                    "key": "ITEM0001",
                    "library": {"id": 1},
                    "data": {
                        "itemType": "journalArticle",
                        "title": "Progressive Multiview Fusion",
                        "date": "2024",
                        "DOI": "10.1000/test.1",
                        "abstractNote": "A verified abstract.",
                        "creators": [{"firstName": "A", "lastName": "Author"}],
                    },
                },
                {
                    "key": "ITEM0002",
                    "library": {"id": 1},
                    "data": {
                        "itemType": "conferencePaper",
                        "title": "Metadata Only Study",
                        "date": "2022",
                        "abstractNote": "",
                        "creators": [],
                    },
                },
            ]
        if "ITEM0001/children" in url:
            return [
                {
                    "key": "PDF00001",
                    "data": {
                        "itemType": "attachment",
                        "filename": "paper.pdf",
                        "contentType": "application/pdf",
                        "linkMode": "imported_file",
                    },
                }
            ]
        if "ITEM0002/children" in url:
            return []
        raise AssertionError(f"Unexpected mock GET: {url}")

    def post_json(self, url: str, payload: dict, headers: dict[str, str]):
        self.last_post = (url, payload)
        return {"jsonrpc": "2.0", "id": 1, "result": {"ITEM0001": "author2024"}}


class StaticZotero:
    def status(self):
        return {"available": True, "api": {"version": 3}}

    def search(self, query: str, **kwargs):
        return {
            "status": "ok",
            "query": query,
            "count": 1,
            "better_bibtex": "available",
            "items": [
                {
                    "item_key": "ZOTERO01",
                    "item_type": "journalArticle",
                    "title": "Progressive Multiview Fusion",
                    "abstract": "",
                    "doi": "10.1000/test.1",
                    "year": 2024,
                    "citekey": "author2024",
                    "zotero_uri": "zotero://select/library/items/ZOTERO01",
                    "evidence_level": "metadata_only",
                    "summary_needed": True,
                    "attachment_status": {"has_pdf": False, "pdf_count": 0},
                }
            ],
        }


class KnowledgeBaseTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.vault = root / "vault"
        self.cache = root / "cache"
        self.manuscripts = root / "manuscripts"
        self.vault.mkdir()
        self.manuscripts.mkdir()
        self.extract_calls: list[str] = []

        def extractor(path: Path):
            self.extract_calls.append(path.name)
            if "扫描" in path.name:
                return ExtractedPdf(["", ""])
            text = (
                "Progressive multiview fusion supports management prediction. "
                "DOI 10.1000/test.1. "
            ) * 8
            return ExtractedPdf([text, "Second page discusses robust evidence. " * 8])

        self.config = Config(
            vault_path=self.vault,
            cache_dir=self.cache,
            manuscripts_root=self.manuscripts,
            max_group_documents=2,
            max_chars=500,
        )
        self.service = KnowledgeBaseService(
            self.config, extractor=extractor, zotero_client=StaticZotero()
        )

    def tearDown(self):
        self.temporary.cleanup()

    def add_pdf(self, relative: str, payload: bytes = b"synthetic pdf") -> Path:
        path = self.vault / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    def test_sync_is_incremental_and_ignores_internal_directories(self):
        first = self.add_pdf("机器学习/多视图/渐进融合/2024_Progressive Multiview Fusion.pdf")
        self.add_pdf("机器学习/多视图/渐进融合/2023_扫描版.pdf")
        self.add_pdf(".obsidian/private.pdf")
        self.add_pdf("知识笔记/generated.pdf")

        result = self.service.kb_sync()
        self.assertEqual(result["counts"]["discovered"], 2)
        self.assertEqual(result["counts"]["indexed"], 2)
        self.assertEqual(len(self.extract_calls), 2)
        levels = self.service.kb_status(check_zotero=False)["cache"]["evidence_levels"]
        self.assertEqual(levels["fulltext"], 1)
        self.assertEqual(levels["needs_ocr"], 1)

        again = self.service.kb_sync()
        self.assertEqual(again["counts"]["skipped"], 2)
        self.assertEqual(len(self.extract_calls), 2)

        first.write_bytes(b"synthetic pdf changed")
        os.utime(first, None)
        changed = self.service.kb_sync()
        self.assertEqual(changed["counts"]["indexed"], 1)

        first.unlink()
        removed = self.service.kb_sync()
        self.assertEqual(removed["counts"]["removed"], 1)

    def test_sync_can_be_scoped_to_one_group_subtree(self):
        target = "机器学习/多视图/渐进融合"
        self.add_pdf(f"{target}/2024_Target Paper.pdf")
        self.add_pdf("决策科学/选址/2023_Outside Paper.pdf")

        scoped = self.service.kb_sync(group_path=target)
        self.assertEqual(scoped["scope"], target)
        self.assertEqual(scoped["counts"]["discovered"], 1)
        self.assertEqual(
            [group["group_path"] for group in self.service.kb_list_groups()["groups"]],
            [target],
        )

        full = self.service.kb_sync()
        self.assertEqual(full["counts"]["discovered"], 2)

    def test_sync_uses_one_resolved_vault_root_for_relative_paths(self):
        self.add_pdf("机器学习/多视图/2024_Aliased Root.pdf")
        alias_directory = self.vault.parent / "path-alias"
        alias_directory.mkdir()
        aliased_config = Config(
            vault_path=alias_directory / ".." / "vault",
            cache_dir=self.vault.parent / "aliased-cache",
        )
        service = KnowledgeBaseService(
            aliased_config,
            extractor=lambda path: ExtractedPdf(["Aliased root evidence. " * 20]),
            zotero_client=StaticZotero(),
        )

        result = service.kb_sync()
        self.assertEqual(result["counts"]["indexed"], 1)
        self.assertEqual(
            service.kb_list_groups()["groups"][0]["group_path"],
            "机器学习/多视图",
        )

    def test_search_group_batching_and_note_write_contract(self):
        self.add_pdf("机器学习/多视图/渐进融合/2024_Progressive Multiview Fusion.pdf")
        self.add_pdf("机器学习/因果/2023_Causal Learning.pdf")
        self.service.kb_sync()

        search = self.service.kb_search("management prediction")
        self.assertGreaterEqual(search["count"], 1)
        fulltext_hits = [hit for hit in search["hits"] if hit["page"]]
        self.assertEqual(fulltext_hits[0]["locator"], "p. 1")

        group = "机器学习/多视图/渐进融合"
        batch = self.service.kb_get_group_context(group, max_chars=60)
        self.assertFalse(batch["done"])
        self.assertIsNotNone(batch["next_cursor"])
        next_batch = self.service.kb_get_group_context(
            group, cursor=batch["next_cursor"], max_chars=60
        )
        self.assertNotEqual(batch["pages"][0]["char_start"], next_batch["pages"][0]["char_start"])

        preview = self.service.kb_write_knowledge_note(
            group,
            "该组聚焦渐进融合机制。",
            related_groups=["机器学习/因果"],
        )
        self.assertEqual(preview["status"], "preview")
        self.assertFalse(Path(preview["note_path"]).exists())
        self.assertIn("[[机器学习_因果]]", preview["content"])
        self.assertIn("2024_Progressive Multiview Fusion.pdf", preview["content"])

        written = self.service.kb_write_knowledge_note(
            group,
            "该组聚焦渐进融合机制。",
            apply=True,
            source_annotations={
                "机器学习/多视图/渐进融合/2024_Progressive Multiview Fusion.pdf": {
                    "literature_type": "method_model_algorithm_or_optimization",
                    "citekey": "author2024",
                }
            },
        )
        self.assertTrue(written["written"])
        self.assertEqual(Path(written["note_path"]).name, "机器学习_多视图_渐进融合.md")
        note_path = Path(written["note_path"])
        note_text = note_path.read_text(encoding="utf-8")
        self.assertIn("type: category-knowledge", note_text)
        self.assertIn("<!-- MRKB:BEGIN GENERATED -->", note_text)
        self.assertIn("## My Notes", note_text)
        self.assertIn("`method_model_algorithm_or_optimization`", note_text)
        self.assertIn("`@author2024`", note_text)
        conflict = self.service.kb_write_knowledge_note(
            group, "新内容", apply=True
        )
        self.assertEqual(conflict["status"], "conflict")

        note_path.write_text(note_text + "\n我的手工备注。\n", encoding="utf-8")
        current = self.service.kb_get_knowledge_note(group)
        self.assertEqual(current["status"], "ok")
        search_notes = self.service.kb_search_notes("聚焦渐进融合")
        self.assertEqual(search_notes["count"], 1)

        missing_digest = self.service.kb_write_knowledge_note(
            group, "更新内容", apply=True, overwrite=True
        )
        self.assertEqual(missing_digest["status"], "conflict")
        updated = self.service.kb_write_knowledge_note(
            group,
            "更新内容",
            apply=True,
            overwrite=True,
            expected_existing_digest=current["digest"],
        )
        self.assertTrue(updated["written"])
        self.assertIn("我的手工备注。", note_path.read_text(encoding="utf-8"))

    def test_zotero_matching_and_evidence_pack_summary_policy(self):
        self.add_pdf("机器学习/多视图/2024_Progressive Multiview Fusion.pdf")
        self.service.kb_sync()
        result = self.service.kb_zotero_search("fusion")
        item = result["items"][0]
        self.assertEqual(item["local_match"]["status"], "exact")
        self.assertEqual(item["effective_evidence_level"], "fulltext")
        self.assertEqual(result["summary_needed"], [])

        pack = self.service.kb_build_evidence_pack("fusion", include_zotero=True)
        self.assertTrue(pack["pack_id"].startswith("ep_"))
        self.assertTrue(any(entry["scope"] == "local_pdf" for entry in pack["evidence"]))
        self.assertFalse(pack["rules"]["gs_skill_called_inside_mcp"])

    def test_project_context_is_bounded_and_path_safe(self):
        project = self.manuscripts / "paper-a"
        project.mkdir()
        (project / "main.tex").write_text("\\section{Introduction}\nEvidence.", encoding="utf-8")
        context = self.service.kb_project_context("paper-a")
        self.assertEqual(context["status"], "ok")
        self.assertIn("Introduction", context["files"][0]["text"])
        with self.assertRaises(PathSafetyError):
            self.service.kb_project_context("../outside")


class StandaloneHelpersTestCase(unittest.TestCase):
    def test_config_defaults_and_external_cache_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "vault").mkdir()
            config_path = root / "config.toml"
            config_path.write_text(
                'vault_path = "vault"\ncache_dir = "cache"\n', encoding="utf-8"
            )
            config = load_config(config_path)
            self.assertEqual(config.notes_dir, "知识笔记")
            self.assertEqual(config.max_group_documents, 20)

            unsafe = Config(vault_path=root / "vault", cache_dir=root / "vault" / "cache")
            with self.assertRaises(ConfigError):
                unsafe.validate()

    def test_group_note_filename_has_no_literal_kno_suffix(self):
        self.assertEqual(
            knowledge_note_filename("机器学习/多视图/渐进融合"),
            "机器学习_多视图_渐进融合.md",
        )

    def test_zotero_client_is_read_only_and_marks_metadata_summary_needed(self):
        transport = MockTransport()
        client = ZoteroClient("http://127.0.0.1:23119", transport=transport)
        result = client.search("study")
        self.assertEqual(result["items"][0]["citekey"], "author2024")
        self.assertTrue(result["items"][0]["attachment_status"]["has_pdf"])
        self.assertEqual(result["items"][0]["evidence_level"], "abstract_only")
        self.assertTrue(result["items"][0]["fulltext_attachment_available"])
        self.assertTrue(result["items"][1]["summary_needed"])
        self.assertEqual(transport.last_post[1]["method"], "item.citationkey")


if __name__ == "__main__":
    unittest.main()
