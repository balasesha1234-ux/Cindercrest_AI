"""Unit tests for the FilesystemGuard security engine."""

from pathlib import Path

from backend.app.agent.tools.filesystem import FilesystemGuard


def test_guard_approves_file_inside_approved_root(tmp_path: Path) -> None:
    approved_dir = tmp_path / "approved_docs"
    approved_dir.mkdir()
    sample_file = approved_dir / "report.md"
    sample_file.write_text("# Sample Report\nContent goes here.", encoding="utf-8")

    guard = FilesystemGuard(approved_directories=[approved_dir])
    is_ok, resolved, reason = guard.validate_path(sample_file)
    assert is_ok is True
    assert resolved == sample_file.resolve()
    assert "Approved" in reason


def test_guard_rejects_path_outside_approved_root(tmp_path: Path) -> None:
    approved_dir = tmp_path / "approved_docs"
    approved_dir.mkdir()

    outside_dir = tmp_path / "forbidden_system"
    outside_dir.mkdir()
    secret_file = outside_dir / "secret.txt"
    secret_file.write_text("super secret", encoding="utf-8")

    guard = FilesystemGuard(approved_directories=[approved_dir])
    is_ok, resolved, reason = guard.validate_path(secret_file)
    assert is_ok is False
    assert resolved is None
    assert "outside approved" in reason.lower()


def test_guard_rejects_path_traversal(tmp_path: Path) -> None:
    approved_dir = tmp_path / "approved_docs"
    approved_dir.mkdir()

    traversal_path = approved_dir / ".." / "outside.txt"
    guard = FilesystemGuard(approved_directories=[approved_dir])
    is_ok, resolved, reason = guard.validate_path(str(traversal_path))
    assert is_ok is False
    assert resolved is None
    assert "outside approved" in reason.lower() or "traversal" in reason.lower()


def test_guard_rejects_symlink_escape(tmp_path: Path) -> None:
    approved_dir = tmp_path / "approved_docs"
    approved_dir.mkdir()

    outside_dir = tmp_path / "private_data"
    outside_dir.mkdir()
    outside_file = outside_dir / "private.txt"
    outside_file.write_text("private", encoding="utf-8")

    symlink_file = approved_dir / "escape_link.txt"
    try:
        symlink_file.symlink_to(outside_file)
    except OSError:
        # On Windows, creating symlinks without Developer Mode / Admin can fail
        return

    guard = FilesystemGuard(approved_directories=[approved_dir])
    is_ok, resolved, reason = guard.validate_path(symlink_file)
    assert is_ok is False
    assert resolved is None
    assert "outside approved" in reason.lower()


def test_guard_rejects_disallowed_extension(tmp_path: Path) -> None:
    approved_dir = tmp_path / "approved_docs"
    approved_dir.mkdir()
    bad_file = approved_dir / "script.exe"
    bad_file.write_text("malicious payload", encoding="utf-8")

    guard = FilesystemGuard(approved_directories=[approved_dir])
    is_ok, resolved, reason = guard.validate_path(bad_file)
    assert is_ok is False
    assert "extension" in reason.lower()


def test_guard_rejects_oversized_file(tmp_path: Path) -> None:
    approved_dir = tmp_path / "approved_docs"
    approved_dir.mkdir()
    big_file = approved_dir / "huge.txt"
    # Write 600 KB (limit is 500 KB)
    big_file.write_text("A" * (600 * 1024), encoding="utf-8")

    guard = FilesystemGuard(approved_directories=[approved_dir])
    is_ok, resolved, reason = guard.validate_path(big_file)
    assert is_ok is False
    assert "exceeds maximum allowed size" in reason.lower()
