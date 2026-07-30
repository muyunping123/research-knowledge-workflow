from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys
import tempfile
import unittest

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


def write_minimal_text_pdf(path: Path, text: str) -> None:
    """Write a small standards-compliant PDF without a test-only dependency."""

    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(stream)).encode("ascii")
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
    ]
    payload = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(payload))
        payload.extend(f"{number} 0 obj\n".encode("ascii"))
        payload.extend(body)
        payload.extend(b"\nendobj\n")
    xref = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    payload.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    payload.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(payload)


@unittest.skipUnless(MCP_AVAILABLE, "official MCP SDK is not installed")
class McpStdioSmokeTest(unittest.TestCase):
    def test_stdio_lists_and_calls_tools(self):
        asyncio.run(self._exercise_server())

    async def _exercise_server(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / "vault"
            cache = root / "cache"
            vault.mkdir()
            group = "机器学习/多视图/渐进融合"
            pdf = vault / group / "2025_Progressive Fusion Test.pdf"
            pdf.parent.mkdir(parents=True)
            write_minimal_text_pdf(
                pdf,
                "Progressive multiview fusion provides page-addressable evidence for testing.",
            )
            config = root / "config.toml"
            config.write_text(
                f'vault_path = "{vault.as_posix()}"\n'
                f'cache_dir = "{cache.as_posix()}"\n',
                encoding="utf-8",
            )

            source = Path(__file__).resolve().parents[1] / "src"
            test_site = os.environ.get("MRKB_TEST_SITE_DIR")
            if test_site:
                bootstrap = (
                    "import site,sys;"
                    f"site.addsitedir({test_site!r});"
                    f"sys.path.insert(0,{str(source)!r});"
                    "from management_research_kb.server import main;main()"
                )
                arguments = ["-c", bootstrap, "--config", str(config)]
            else:
                arguments = ["-m", "management_research_kb", "--config", str(config)]

            parameters = StdioServerParameters(command=sys.executable, args=arguments)
            async with stdio_client(parameters) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    initialized = await session.initialize()
                    self.assertEqual(
                        initialized.serverInfo.name, "research-knowledge-workflow"
                    )
                    listed = await session.list_tools()
                    names = {tool.name for tool in listed.tools}
                    self.assertEqual(
                        names,
                        {
                            "kb_status",
                            "kb_sync",
                            "kb_list_groups",
                            "kb_prepare_topic",
                            "kb_get_knowledge_note",
                            "kb_search_notes",
                            "kb_search",
                            "kb_get_document",
                            "kb_get_group_context",
                            "kb_related_groups",
                            "kb_write_knowledge_note",
                            "kb_zotero_search",
                            "kb_build_evidence_pack",
                            "kb_project_context",
                        },
                    )
                    result = await session.call_tool(
                        "kb_status", {"check_zotero": False}
                    )
                    self.assertFalse(result.isError)
                    synced = await session.call_tool("kb_sync", {"group_path": group})
                    self.assertFalse(synced.isError)
                    prepared = await session.call_tool(
                        "kb_prepare_topic",
                        {
                            "query": "progressive fusion",
                            "max_groups": 1,
                            "max_chars_per_group": 500,
                        },
                    )
                    self.assertFalse(prepared.isError)
                    searched = await session.call_tool(
                        "kb_search", {"query": "page-addressable", "group_path": group}
                    )
                    self.assertFalse(searched.isError)
                    rendered = "\n".join(
                        getattr(block, "text", "") for block in searched.content
                    )
                    self.assertIn("Progressive", rendered)

                    preview = await session.call_tool(
                        "kb_write_knowledge_note",
                        {
                            "group_path": group,
                            "analytical_body": "Synthetic end-to-end synthesis.",
                        },
                    )
                    self.assertFalse(preview.isError)
                    note = vault / "知识笔记" / "机器学习_多视图_渐进融合.md"
                    self.assertFalse(note.exists())

                    applied = await session.call_tool(
                        "kb_write_knowledge_note",
                        {
                            "group_path": group,
                            "analytical_body": "Synthetic end-to-end synthesis.",
                            "apply": True,
                        },
                    )
                    self.assertFalse(applied.isError)
                    self.assertTrue(note.is_file())
                    self.assertIn("2025_Progressive Fusion Test.pdf", note.read_text("utf-8"))

    @unittest.skipUnless(os.name == "nt", "PowerShell plugin launcher is Windows-specific")
    def test_plugin_powershell_launcher(self):
        asyncio.run(self._exercise_plugin_launcher())

    async def _exercise_plugin_launcher(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            vault = root / "vault"
            vault.mkdir()
            config = root / "config.toml"
            config.write_text(
                f'vault_path = "{vault.as_posix()}"\n'
                f'cache_dir = "{(root / "cache").as_posix()}"\n',
                encoding="utf-8",
            )
            plugin_root = Path(__file__).resolve().parents[2]
            environment = dict(os.environ)
            environment["RESEARCH_KNOWLEDGE_WORKFLOW_CONFIG"] = str(config)
            parameters = StdioServerParameters(
                command="powershell",
                args=[
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(plugin_root / "scripts" / "run-mcp.ps1"),
                ],
                env=environment,
            )
            async with stdio_client(parameters) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        "kb_status", {"check_zotero": False}
                    )
                    self.assertFalse(result.isError)


if __name__ == "__main__":
    unittest.main()
