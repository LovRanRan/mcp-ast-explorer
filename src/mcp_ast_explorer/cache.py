import threading
from pathlib import Path

from mcp_ast_explorer.indexer import build_cst_index, iter_python_files
from mcp_ast_explorer.models import PythonCstIndex

# One entry per indexed .py file: (relative path, size in bytes, mtime in ns).
# Stat-ing every file is cheap compared to re-parsing it, and any edit, add,
# or delete changes the fingerprint.
DirectoryFingerprint = tuple[tuple[str, int, int], ...]


def directory_fingerprint(root_path: Path) -> DirectoryFingerprint:
    entries: list[tuple[str, int, int]] = []
    for path in iter_python_files(root_path):
        stat = path.stat()
        entries.append(
            (path.relative_to(root_path).as_posix(), stat.st_size, stat.st_mtime_ns)
        )
    return tuple(entries)


class CstIndexCache:
    """In-process cache of CST indexes keyed by resolved root path.

    A cached index is reused only while the root's directory fingerprint is
    unchanged; any file edit, addition, or removal triggers a rebuild.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[Path, tuple[DirectoryFingerprint, PythonCstIndex]] = {}

    def get_index(self, root: str | Path) -> PythonCstIndex:
        root_path = Path(root).resolve()
        fingerprint = directory_fingerprint(root_path)
        with self._lock:
            entry = self._entries.get(root_path)
            if entry is not None and entry[0] == fingerprint:
                return entry[1]
            index = build_cst_index(root_path)
            self._entries[root_path] = (fingerprint, index)
            return index

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_default_cache = CstIndexCache()


def get_cst_index(root: str | Path) -> PythonCstIndex:
    return _default_cache.get_index(root)
