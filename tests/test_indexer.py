from pathlib import Path

from mcp_ast_explorer.indexer import (
    build_call_chain_in_index,
    build_class_hierarchy_in_index,
    build_cst_index,
    find_definition_in_index,
    find_references_in_index,
)


def test_build_cst_index_parses_python_files(tmp_path: Path) -> None:
    source = "def add(a: int, b: int) -> int:\n    return a + b\n"
    package_dir = tmp_path / "app"
    package_dir.mkdir()
    target = package_dir / "service.py"
    target.write_text(source, encoding="utf-8")

    index = build_cst_index(tmp_path)

    assert index.root == tmp_path.resolve()
    assert len(index.files) == 1

    parsed_file = index.files[0]
    assert parsed_file.path == target
    assert parsed_file.relative_path == "app/service.py"
    assert parsed_file.source == source
    assert parsed_file.module.code == source


def test_build_cst_index_ignores_cache_and_venv_dirs(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print('ok')\n", encoding="utf-8")
    venv_dir = tmp_path / ".venv"
    venv_dir.mkdir()
    (venv_dir / "ignored.py").write_text("print('ignored')\n", encoding="utf-8")

    index = build_cst_index(tmp_path)

    assert [file.relative_path for file in index.files] == ["main.py"]


def test_build_cst_index_collects_module_class_function_and_method_symbols(
    tmp_path: Path,
) -> None:
    source = (
        "class UserService:\n"
        "    def create(self, name):\n"
        "        return name\n"
        "\n"
        "def add(a, b):\n"
        "    return a + b\n"
    )
    package_dir = tmp_path / "app"
    package_dir.mkdir()
    target = package_dir / "service.py"
    target.write_text(source, encoding="utf-8")

    index = build_cst_index(tmp_path)

    symbols = {
        symbol.qualified_name: symbol
        for symbol in index.symbols
    }

    assert set(symbols) == {
        "app.service",
        "app.service.UserService",
        "app.service.UserService.create",
        "app.service.add",
    }

    assert symbols["app.service"].kind == "module"
    assert symbols["app.service.UserService"].kind == "class"
    assert symbols["app.service.UserService.create"].kind == "method"
    assert symbols["app.service.UserService.create"].signature == "create(self, name)"
    assert symbols["app.service.UserService.create"].location.relative_path == "app/service.py"
    assert symbols["app.service.UserService.create"].location.line == 2
    assert symbols["app.service.UserService.create"].location.column == 4

    assert symbols["app.service.add"].kind == "function"
    assert symbols["app.service.add"].signature == "add(a, b)"
    assert symbols["app.service.add"].location.line == 5
    assert symbols["app.service.add"].location.column == 0


def test_find_definition_in_index_returns_exact_qualified_symbol(
    tmp_path: Path,
) -> None:
    source = (
        "class UserService:\n"
        "    def create(self, name):\n"
        "        return name\n"
        "\n"
        "def add(a, b):\n"
        "    return a + b\n"
    )
    package_dir = tmp_path / "app"
    package_dir.mkdir()
    target = package_dir / "service.py"
    target.write_text(source, encoding="utf-8")

    index = build_cst_index(tmp_path)

    definition = find_definition_in_index(index, "app.service.add")

    assert definition is not None
    assert definition.name == "add"
    assert definition.qualified_name == "app.service.add"
    assert definition.kind == "function"
    assert definition.location.relative_path == "app/service.py"
    assert definition.location.line == 5
    assert definition.signature == "add(a, b)"
    assert definition.source_code == "def add(a, b):\n    return a + b\n"


def test_find_definition_in_index_returns_none_for_missing_symbol(
    tmp_path: Path,
) -> None:
    (tmp_path / "main.py").write_text("print('ok')\n", encoding="utf-8")
    index = build_cst_index(tmp_path)

    assert find_definition_in_index(index, "main.missing") is None


def test_build_cst_index_records_parse_errors_and_continues(tmp_path: Path) -> None:
    package_dir = tmp_path / "app"
    package_dir.mkdir()
    (package_dir / "valid.py").write_text(
        "def ok():\n    return True\n",
        encoding="utf-8",
    )
    broken_file = package_dir / "broken.py"
    broken_file.write_text("def broken(:\n", encoding="utf-8")

    index = build_cst_index(tmp_path)

    assert [file.relative_path for file in index.files] == ["app/valid.py"]
    assert find_definition_in_index(index, "app.valid.ok") is not None

    assert len(index.parse_errors) == 1
    parse_error = index.parse_errors[0]
    assert parse_error.path == broken_file
    assert parse_error.relative_path == "app/broken.py"
    assert "parser error" in parse_error.message
    assert parse_error.line == 1
    assert parse_error.column == 0


def test_find_references_in_index_returns_call_site_for_existing_function(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "app"
    package_dir.mkdir()
    target = package_dir / "service.py"
    target.write_text(
        "def add(a, b):\n"
        "    return a + b\n"
        "\n"
        "def total():\n"
        "    return add(1, 2)\n",
        encoding="utf-8",
    )
    index = build_cst_index(tmp_path)
    references = find_references_in_index(index, "app.service.add")

    assert len(references) == 1
    reference = references[0]

    assert reference.qualified_name == "app.service.add"
    assert reference.name == "add"
    assert reference.kind == "function"
    assert reference.location.relative_path == "app/service.py"
    assert reference.location.line == 5
    assert reference.context_code == "return add(1, 2)"


def test_find_references_in_index_returns_empty_for_missing_symbol(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "app"
    package_dir.mkdir()
    (package_dir / "service.py").write_text(
        "def add(a, b):\n"
        "    return a + b\n"
        "\n"
        "def total():\n"
        "    return add(1, 2)\n",
        encoding="utf-8",
    )

    index = build_cst_index(tmp_path)

    assert find_references_in_index(index, "app.service.missing") == []


def test_build_call_chain_in_index_returns_direct_caller(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "app"
    package_dir.mkdir()
    (package_dir / "service.py").write_text(
        "def add(a, b):\n"
        "    return a + b\n"
        "\n"
        "def total():\n"
        "    return add(1, 2)\n",
        encoding="utf-8",
    )

    index = build_cst_index(tmp_path)
    chain = build_call_chain_in_index(index, "app.service.add", depth=2)

    assert chain.symbol == "app.service.add"
    assert len(chain.callers) == 1

    caller = chain.callers[0]
    assert caller.symbol == "app.service.total"
    assert caller.context_code == "return add(1, 2)"


def test_build_call_chain_in_index_returns_empty_for_missing_symbol(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "app"
    package_dir.mkdir()
    (package_dir / "service.py").write_text(
        "def add(a, b):\n"
        "    return a + b\n"
        "\n"
        "def total():\n"
        "    return add(1, 2)\n",
        encoding="utf-8",
    )

    index = build_cst_index(tmp_path)
    chain = build_call_chain_in_index(index, "app.service.missing", depth=2)

    assert chain.symbol == "app.service.missing"
    assert chain.callers == []


def test_build_class_hierarchy_in_index_returns_direct_subclass(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "app"
    package_dir.mkdir()
    (package_dir / "models.py").write_text(
        "class User:\n"
        "    pass\n"
        "\n"
        "class AdminUser(User):\n"
        "    pass\n",
        encoding="utf-8",
    )

    index = build_cst_index(tmp_path)
    hierarchy = build_class_hierarchy_in_index(index, "app.models.User")

    assert hierarchy.class_name == "app.models.User"
    assert len(hierarchy.subclasses) == 1

    subclass = hierarchy.subclasses[0]
    assert subclass.class_name == "app.models.AdminUser"
    assert subclass.location.relative_path == "app/models.py"
    assert subclass.location.line == 4


def test_build_class_hierarchy_in_index_returns_empty_for_missing_class(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "app"
    package_dir.mkdir()
    (package_dir / "models.py").write_text(
        "class User:\n"
        "    pass\n"
        "\n"
        "class AdminUser(User):\n"
        "    pass\n",
        encoding="utf-8",
    )

    index = build_cst_index(tmp_path)
    hierarchy = build_class_hierarchy_in_index(index, "app.models.Missing")

    assert hierarchy.class_name == "app.models.Missing"
    assert hierarchy.subclasses == []
