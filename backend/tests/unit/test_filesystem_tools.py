"""Unit tests for fs.search and fs.read_text tools."""

from pathlib import Path

import pytest

from backend.app.agent.tools.filesystem import (
    FilesystemGuard,
    fs_read_text_handler,
    fs_search_handler,
)
from backend.app.core.exceptions import ValidationError


@pytest.mark.asyncio
async def test_fs_search_finds_files_by_keyword(tmp_path: Path) -> None:
    approved_dir = tmp_path / "docs"
    approved_dir.mkdir()
    (approved_dir / "architecture.md").write_text(
        "# Monolith Architecture\nFastAPI backend with SQLite.", encoding="utf-8"
    )
    (approved_dir / "security_spec.txt").write_text(
        "Security policy default deny.", encoding="utf-8"
    )
    (approved_dir / "ignored.bin").write_text("binary data", encoding="utf-8")

    guard = FilesystemGuard(approved_directories=[approved_dir])

    # Search by keyword in filename
    res = await fs_search_handler({"query": "architecture"}, guard=guard)
    assert res["total_found"] == 1
    assert res["results"][0]["filename"] == "architecture.md"

    # Search by keyword in text content
    res_content = await fs_search_handler({"query": "monolith"}, guard=guard)
    assert res_content["total_found"] == 1
    assert res_content["results"][0]["filename"] == "architecture.md"


@pytest.mark.asyncio
async def test_fs_search_rejects_empty_query(tmp_path: Path) -> None:
    guard = FilesystemGuard(approved_directories=[tmp_path])
    with pytest.raises(ValidationError, match="query cannot be empty"):
        await fs_search_handler({"query": ""}, guard=guard)


@pytest.mark.asyncio
async def test_fs_read_text_reads_approved_file(tmp_path: Path) -> None:
    approved_dir = tmp_path / "docs"
    approved_dir.mkdir()
    doc_file = approved_dir / "notes.md"
    doc_content = "# Project Notes\nThese are important meeting notes."
    doc_file.write_text(doc_content, encoding="utf-8")

    guard = FilesystemGuard(approved_directories=[approved_dir])
    res = await fs_read_text_handler({"path": str(doc_file)}, guard=guard)

    assert res["content"] == doc_content
    assert res["char_count"] == len(doc_content)
    assert res["truncated"] is False


@pytest.mark.asyncio
async def test_fs_read_text_truncates_at_max_chars(tmp_path: Path) -> None:
    approved_dir = tmp_path / "docs"
    approved_dir.mkdir()
    doc_file = approved_dir / "long.txt"
    doc_file.write_text("0123456789" * 100, encoding="utf-8")  # 1000 chars

    guard = FilesystemGuard(approved_directories=[approved_dir])
    res = await fs_read_text_handler({"path": str(doc_file), "max_chars": 50}, guard=guard)

    assert len(res["content"]) == 50
    assert res["char_count"] == 50
    assert res["truncated"] is True


@pytest.mark.asyncio
async def test_fs_read_text_rejects_unapproved_path(tmp_path: Path) -> None:
    approved_dir = tmp_path / "docs"
    approved_dir.mkdir()

    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    forbidden_file = outside_dir / "secret.txt"
    forbidden_file.write_text("classified", encoding="utf-8")

    guard = FilesystemGuard(approved_directories=[approved_dir])
    with pytest.raises(ValidationError, match="outside approved"):
        await fs_read_text_handler({"path": str(forbidden_file)}, guard=guard)
