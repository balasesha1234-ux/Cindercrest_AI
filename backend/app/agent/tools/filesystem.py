"""Safe, read-only filesystem intelligence bounded to approved directories."""

from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from backend.app.agent.schema import ToolSafetyTier
from backend.app.agent.tools.registry import ToolDefinition, tool_registry
from backend.app.core.config import get_settings
from backend.app.core.exceptions import NotFoundError, ValidationError

# Allowed file extensions for read-only inspection
ALLOWED_EXTENSIONS: set[str] = {
    ".txt",
    ".md",
    ".json",
    ".csv",
    ".log",
    ".py",
    ".yaml",
    ".yml",
    ".toml",
    ".rst",
}

# Maximum allowed file size for reading: 500 KB
MAX_FILE_SIZE_BYTES: int = 500 * 1024

# Default and maximum read character limits
DEFAULT_MAX_CHARS: int = 20_000
HARD_MAX_CHARS: int = 100_000


class FilesystemGuard:
    """Enforces strict path canonicalization, approved directory whitelisting, and symlink escape prevention."""

    def __init__(self, approved_directories: list[str | Path] | None = None) -> None:
        settings = get_settings()
        raw_roots = (
            approved_directories
            if approved_directories is not None
            else settings.APPROVED_DIRECTORIES
        )
        if isinstance(raw_roots, str):
            raw_roots = [raw_roots]

        # Resolve all approved roots to canonical absolute paths
        self.approved_roots: list[Path] = []
        project_root = Path.cwd().resolve()

        for d in raw_roots:
            p = Path(d)
            if not p.is_absolute():
                p = (project_root / p).resolve()
            else:
                p = p.resolve()
            if p.exists() and p.is_dir():
                self.approved_roots.append(p)
            elif not p.exists():
                # Allow configured roots that may exist at runtime
                self.approved_roots.append(p)

    def validate_path(
        self, path_input: str | Path, allow_dir: bool = False
    ) -> tuple[bool, Path | None, str]:
        """Validate whether a path strictly resides within the approved directory whitelist."""
        raw_str = str(path_input).strip()
        if not raw_str:
            return False, None, "Path cannot be empty"

        if "\0" in raw_str:
            return False, None, "Null bytes are forbidden in paths"

        project_root = Path.cwd().resolve()
        candidate = Path(raw_str)
        if not candidate.is_absolute():
            # If path starts with an approved directory name (e.g. 'docs/VISION.md')
            candidate = (project_root / candidate).resolve()
        else:
            candidate = candidate.resolve()

        # Handle symlinks: resolve() follows symlinks to real physical destination
        try:
            real_path = candidate.resolve()
        except Exception as exc:
            return False, None, f"Failed to resolve path: {exc}"

        # Strict containment check against approved roots
        is_approved = any(self._is_subpath(real_path, root) for root in self.approved_roots)
        if not is_approved:
            return False, None, f"Access denied: Path '{raw_str}' is outside approved directories."

        if not real_path.exists():
            return False, None, f"File or directory does not exist: '{raw_str}'"

        if real_path.is_dir():
            if not allow_dir:
                return False, None, f"Target '{raw_str}' is a directory, expected a file."
            return True, real_path, "Approved directory"

        if real_path.is_file():
            # Extension check
            suffix = real_path.suffix.lower()
            if suffix not in ALLOWED_EXTENSIONS:
                return (
                    False,
                    None,
                    f"File extension '{suffix}' is not permitted for read-only inspection.",
                )

            # File size check
            try:
                size = real_path.stat().st_size
                if size > MAX_FILE_SIZE_BYTES:
                    return (
                        False,
                        None,
                        f"File size ({size} bytes) exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES} bytes (500 KB).",
                    )
            except OSError as exc:
                return False, None, f"Could not inspect file attributes: {exc}"

            return True, real_path, "Approved file"

        return False, None, f"Path '{raw_str}' is neither a regular file nor a directory."

    def _is_subpath(self, target: Path, parent: Path) -> bool:
        """Check if target path is identical to or within parent directory."""
        try:
            target.relative_to(parent)
            return True
        except ValueError:
            return False


# Singleton guard instance
fs_guard = FilesystemGuard()


# Tool Handlers
async def fs_search_handler(
    parameters: dict[str, Any], guard: FilesystemGuard | None = None
) -> dict[str, Any]:
    """Search for relevant documents inside approved directories by filename or content."""
    active_guard = guard or fs_guard
    query = parameters.get("query", "").strip()
    if not query:
        raise ValidationError("Search query cannot be empty")

    max_results = min(int(parameters.get("max_results", 20)), 50)
    lowered_query = query.lower()

    matched_results: list[dict[str, Any]] = []

    for root in active_guard.approved_roots:
        if not root.exists() or not root.is_dir():
            continue

        for path in root.rglob("*"):
            if not path.is_file():
                continue

            # Skip hidden files or common ignored dirs
            parts = path.parts
            if any(
                p.startswith(".") or p in ("node_modules", "__pycache__", "venv") for p in parts
            ):
                continue

            # Validate extension
            if path.suffix.lower() not in ALLOWED_EXTENSIONS:
                continue

            filename = path.name
            is_match = False
            match_reason = ""

            # 1. Match by glob pattern or filename substring
            if fnmatch(filename.lower(), f"*{lowered_query}*") or lowered_query in filename.lower():
                is_match = True
                match_reason = "filename"

            # 2. Match by content if not matched by filename
            if not is_match:
                try:
                    # Quick size check before reading
                    if path.stat().st_size <= MAX_FILE_SIZE_BYTES:
                        text_sample = path.read_text(encoding="utf-8", errors="replace")[:10_000]
                        if lowered_query in text_sample.lower():
                            is_match = True
                            match_reason = "content"
                except Exception:
                    pass

            if is_match:
                try:
                    rel_path = str(path.relative_to(Path.cwd().resolve()))
                except ValueError:
                    rel_path = str(path)

                matched_results.append(
                    {
                        "filename": filename,
                        "path": rel_path.replace("\\", "/"),
                        "size_bytes": path.stat().st_size,
                        "extension": path.suffix.lower(),
                        "match_type": match_reason,
                    }
                )

                if len(matched_results) >= max_results:
                    break

        if len(matched_results) >= max_results:
            break

    # Prioritize exact and filename matches above content matches
    matched_results.sort(key=lambda r: 0 if r.get("match_type") == "filename" else 1)
    final_results = matched_results[:max_results]

    return {
        "results": final_results,
        "total_found": len(final_results),
        "query": query,
    }


async def fs_read_text_handler(
    parameters: dict[str, Any], guard: FilesystemGuard | None = None
) -> dict[str, Any]:
    """Read text from an approved document file up to safety bounds."""
    active_guard = guard or fs_guard
    path_param = parameters.get("path", "").strip()
    if not path_param:
        raise ValidationError("File path parameter is required")

    is_ok, resolved_path, reason = active_guard.validate_path(path_param)
    if not is_ok or resolved_path is None:
        raise ValidationError(f"Filesystem access denied: {reason}")

    if not resolved_path.exists():
        raise NotFoundError(message=f"File not found: '{path_param}'")

    max_chars = min(int(parameters.get("max_chars", DEFAULT_MAX_CHARS)), HARD_MAX_CHARS)

    try:
        raw_text = resolved_path.read_text(encoding="utf-8", errors="replace")
        truncated = len(raw_text) > max_chars
        content = raw_text[:max_chars]

        try:
            display_path = str(resolved_path.relative_to(Path.cwd().resolve())).replace("\\", "/")
        except ValueError:
            display_path = resolved_path.name

        return {
            "path": display_path,
            "filename": resolved_path.name,
            "content": content,
            "char_count": len(content),
            "truncated": truncated,
            "size_bytes": resolved_path.stat().st_size,
        }
    except Exception as exc:
        raise ValidationError(f"Failed to read file contents: {exc}") from exc


# Register fs.search
tool_registry.register(
    ToolDefinition(
        name="fs.search",
        description="Search for project documents inside approved directories by keyword or filename pattern.",
        safety_tier=ToolSafetyTier.READ,
        parameters_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keyword or pattern to search for in filenames and contents",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of search results to return (default 20, max 50)",
                },
            },
            "required": ["query"],
        },
        handler=fs_search_handler,
    )
)

# Register fs.read_text
tool_registry.register(
    ToolDefinition(
        name="fs.read_text",
        description="Safely read the text content of an approved project document file within approved directories.",
        safety_tier=ToolSafetyTier.READ,
        parameters_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the document file within approved directories",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters to read (default 20000, max 100000)",
                },
            },
            "required": ["path"],
        },
        handler=fs_read_text_handler,
    )
)
