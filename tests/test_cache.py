import os
from pathlib import Path

from mcp_ast_explorer.cache import CstIndexCache, directory_fingerprint
from mcp_ast_explorer.indexer import find_definition_in_index


def _write(path: Path, source: str) -> None:
    path.write_text(source, encoding="utf-8")


def _bump_mtime(path: Path, seconds: int = 10) -> None:
    # Filesystems with coarse mtime resolution could otherwise miss a
    # write that lands in the same tick as the previous one.
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + seconds * 1_000_000_000))


def test_cache_returns_same_index_on_hit(tmp_path: Path) -> None:
    _write(tmp_path / "main.py", "def add(a, b):\n    return a + b\n")
    cache = CstIndexCache()

    first = cache.get_index(tmp_path)
    second = cache.get_index(tmp_path)

    assert second is first


def test_cache_hit_for_equivalent_root_spellings(tmp_path: Path) -> None:
    _write(tmp_path / "main.py", "def add(a, b):\n    return a + b\n")
    cache = CstIndexCache()

    first = cache.get_index(tmp_path)
    second = cache.get_index(str(tmp_path / "." / "."))

    assert second is first


def test_cache_invalidates_when_file_content_changes(tmp_path: Path) -> None:
    target = tmp_path / "main.py"
    _write(target, "def add(a, b):\n    return a + b\n")
    cache = CstIndexCache()

    stale = cache.get_index(tmp_path)
    assert find_definition_in_index(stale, "main.subtract") is None

    _write(target, "def subtract(a, b):\n    return a - b\n")
    _bump_mtime(target)
    fresh = cache.get_index(tmp_path)

    assert fresh is not stale
    assert find_definition_in_index(fresh, "main.subtract") is not None
    assert find_definition_in_index(fresh, "main.add") is None


def test_cache_invalidates_when_file_is_added(tmp_path: Path) -> None:
    _write(tmp_path / "main.py", "def add(a, b):\n    return a + b\n")
    cache = CstIndexCache()

    stale = cache.get_index(tmp_path)
    _write(tmp_path / "extra.py", "def extra():\n    return 1\n")
    fresh = cache.get_index(tmp_path)

    assert fresh is not stale
    assert find_definition_in_index(fresh, "extra.extra") is not None


def test_cache_invalidates_when_file_is_removed(tmp_path: Path) -> None:
    _write(tmp_path / "main.py", "def add(a, b):\n    return a + b\n")
    doomed = tmp_path / "doomed.py"
    _write(doomed, "def doomed():\n    return 0\n")
    cache = CstIndexCache()

    stale = cache.get_index(tmp_path)
    doomed.unlink()
    fresh = cache.get_index(tmp_path)

    assert fresh is not stale
    assert find_definition_in_index(fresh, "doomed.doomed") is None


def test_distinct_roots_do_not_collide(tmp_path: Path) -> None:
    root_a = tmp_path / "project_a"
    root_b = tmp_path / "project_b"
    root_a.mkdir()
    root_b.mkdir()
    _write(root_a / "main.py", "def only_in_a():\n    return 'a'\n")
    _write(root_b / "main.py", "def only_in_b():\n    return 'b'\n")
    cache = CstIndexCache()

    index_a = cache.get_index(root_a)
    index_b = cache.get_index(root_b)

    assert index_a is not index_b
    assert find_definition_in_index(index_a, "main.only_in_a") is not None
    assert find_definition_in_index(index_a, "main.only_in_b") is None
    assert find_definition_in_index(index_b, "main.only_in_b") is not None
    # Both stay cached independently.
    assert cache.get_index(root_a) is index_a
    assert cache.get_index(root_b) is index_b


def test_clear_forces_rebuild(tmp_path: Path) -> None:
    _write(tmp_path / "main.py", "def add(a, b):\n    return a + b\n")
    cache = CstIndexCache()

    first = cache.get_index(tmp_path)
    cache.clear()

    assert cache.get_index(tmp_path) is not first


def test_directory_fingerprint_ignores_venv_and_cache_dirs(tmp_path: Path) -> None:
    _write(tmp_path / "main.py", "print('ok')\n")
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    _write(venv_dir / "ignored.py", "print('ignored')\n")
    cache = CstIndexCache()

    index = cache.get_index(tmp_path)
    # Churn inside an ignored directory must not invalidate the cache.
    _write(venv_dir / "more.py", "print('more')\n")

    assert directory_fingerprint(tmp_path.resolve()) == directory_fingerprint(tmp_path.resolve())
    assert [entry[0] for entry in directory_fingerprint(tmp_path.resolve())] == ["main.py"]
    assert cache.get_index(tmp_path) is index
