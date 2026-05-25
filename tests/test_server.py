import asyncio
from pathlib import Path

from fastmcp import Client

from mcp_ast_explorer.server import (
    call_chain,
    class_hierarchy,
    find_definition,
    find_references,
    function_signature,
    health,
    main,
    mcp,
)


def test_health_returns_ok() -> None:
    assert health() == "ok"


def test_main_runs_stdio_transport(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_run(**kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(mcp, "run", fake_run)

    main()

    assert calls == [{"transport": "stdio"}]


def test_find_definition_returns_definition_for_existing_symbol(tmp_path: Path) -> None:
    package_dir = tmp_path / "app"
    package_dir.mkdir()
    (package_dir / "service.py").write_text(
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )

    result = find_definition(str(tmp_path), "app.service.add")

    assert result.found is True
    assert result.qualified_name == "app.service.add"
    assert result.kind == "function"
    assert result.location is not None
    assert result.location.relative_path == "app/service.py"
    assert result.location.line == 1
    assert result.signature == "add(a, b)"
    assert result.source_code == "def add(a, b):\n    return a + b\n"


def test_find_definition_returns_not_found_for_missing_symbol(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print('ok')\n", encoding="utf-8")

    result = find_definition(str(tmp_path), "main.missing")

    assert result.found is False
    assert result.symbol == "main.missing"
    assert result.error == "Symbol not found: main.missing"


def test_function_signature_returns_signature_for_function(tmp_path: Path) -> None:
    package_dir = tmp_path / "app"
    package_dir.mkdir()
    (package_dir / "service.py").write_text(
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )

    result = function_signature(str(tmp_path), "app.service.add")

    assert result.found is True
    assert result.qualified_name == "app.service.add"
    assert result.kind == "function"
    assert result.signature == "add(a, b)"


def test_function_signature_rejects_non_callable_symbol(tmp_path: Path) -> None:
    package_dir = tmp_path / "app"
    package_dir.mkdir()
    (package_dir / "service.py").write_text(
        "class UserService:\n"
        "    def create(self, name):\n"
        "        return name\n",
        encoding="utf-8",
    )

    result = function_signature(str(tmp_path), "app.service.UserService")

    assert result.found is False
    assert result.qualified_name == "app.service.UserService"
    assert result.kind == "class"
    assert result.error == "Symbol is not a function or method: app.service.UserService"


def test_function_signature_returns_not_found_for_missing_symbol(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print('ok')\n", encoding="utf-8")

    result = function_signature(str(tmp_path), "main.missing")

    assert result.found is False
    assert result.error == "Symbol not found: main.missing"


def test_tools_skip_broken_python_files_and_return_valid_symbols(tmp_path: Path) -> None:
    package_dir = tmp_path / "app"
    package_dir.mkdir()
    (package_dir / "valid.py").write_text(
        "def ok():\n    return True\n",
        encoding="utf-8",
    )
    (package_dir / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    definition = find_definition(str(tmp_path), "app.valid.ok")
    signature = function_signature(str(tmp_path), "app.valid.ok")

    assert definition.found is True
    assert definition.source_code == "def ok():\n    return True\n"
    assert signature.found is True
    assert signature.signature == "ok()"


def test_mcp_client_can_call_health_definition_and_signature(tmp_path: Path) -> None:
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
    (package_dir / "models.py").write_text(
        "class User:\n"
        "    pass\n"
        "\n"
        "class AdminUser(User):\n"
        "    pass\n",
        encoding="utf-8",
    )

    async def run_client() -> None:
        async with Client(mcp) as client:
            tools = await client.list_tools()
            tool_names = {tool.name for tool in tools}

            assert "call_chain" in tool_names
            assert "class_hierarchy" in tool_names
            assert "health" in tool_names
            assert "find_definition" in tool_names
            assert "find_references" in tool_names
            assert "function_signature" in tool_names

            health_result = await client.call_tool("health", {})
            assert health_result.data == "ok"

            definition_result = await client.call_tool(
                "find_definition",
                {"path": str(tmp_path), "symbol": "app.service.add"},
            )
            assert definition_result.structured_content is not None
            assert definition_result.structured_content["found"] is True
            assert definition_result.structured_content["qualified_name"] == "app.service.add"
            assert definition_result.structured_content["location"]["relative_path"] == (
                "app/service.py"
            )
            signature_result = await client.call_tool(
                "function_signature",
                {"path": str(tmp_path), "symbol": "app.service.add"},
            )
            assert signature_result.structured_content is not None
            assert signature_result.structured_content["found"] is True
            assert signature_result.structured_content["signature"] == "add(a, b)"

            references_result = await client.call_tool(
                "find_references",
                {"path": str(tmp_path), "symbol": "app.service.add"},
            )
            assert references_result.structured_content is not None
            assert references_result.structured_content["found"] is True
            assert len(references_result.structured_content["references"]) == 1
            assert references_result.structured_content["references"][0]["context_code"] == (
                "return add(1, 2)"
            )

            call_chain_result = await client.call_tool(
                "call_chain",
                {"path": str(tmp_path), "from_symbol": "app.service.add", "depth": 2},
            )
            assert call_chain_result.structured_content is not None
            assert call_chain_result.structured_content["found"] is True
            assert len(call_chain_result.structured_content["callers"]) == 1
            assert call_chain_result.structured_content["callers"][0]["symbol"] == (
                "app.service.total"
            )

            hierarchy_result = await client.call_tool(
                "class_hierarchy",
                {"path": str(tmp_path), "class_name": "app.models.User"},
            )
            assert hierarchy_result.structured_content is not None
            assert hierarchy_result.structured_content["found"] is True
            assert len(hierarchy_result.structured_content["subclasses"]) == 1
            assert hierarchy_result.structured_content["subclasses"][0]["class_name"] == (
                "app.models.AdminUser"
            )

    asyncio.run(run_client())


def test_find_references_returns_call_site_for_existing_symbol(tmp_path: Path) -> None:
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

    result = find_references(str(tmp_path), "app.service.add")

    assert result.found is True
    assert result.symbol == "app.service.add"
    assert len(result.references) == 1

    reference = result.references[0]
    assert reference.qualified_name == "app.service.add"
    assert reference.name == "add"
    assert reference.kind == "function"
    assert reference.location.relative_path == "app/service.py"
    assert reference.location.line == 5
    assert reference.context_code == "return add(1, 2)"


def test_find_references_returns_not_found_for_missing_symbol(tmp_path: Path) -> None:
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

    result = find_references(str(tmp_path), "app.service.missing")

    assert result.found is False
    assert result.symbol == "app.service.missing"
    assert result.references == []
    assert result.error == "Symbol not found: app.service.missing"


def test_call_chain_returns_direct_caller_for_existing_symbol(tmp_path: Path) -> None:
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

    result = call_chain(str(tmp_path), "app.service.add", depth=2)

    assert result.found is True
    assert result.symbol == "app.service.add"
    assert len(result.callers) == 1

    caller = result.callers[0]
    assert caller.symbol == "app.service.total"
    assert caller.context_code == "return add(1, 2)"


def test_call_chain_returns_not_found_for_missing_symbol(tmp_path: Path) -> None:
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

    result = call_chain(str(tmp_path), "app.service.missing", depth=2)

    assert result.found is False
    assert result.symbol == "app.service.missing"
    assert result.callers == []
    assert result.error == "Symbol not found: app.service.missing"


def test_class_hierarchy_returns_direct_subclass_for_existing_class(tmp_path: Path) -> None:
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

    result = class_hierarchy(str(tmp_path), "app.models.User")

    assert result.found is True
    assert result.class_name == "app.models.User"
    assert len(result.subclasses) == 1

    subclass = result.subclasses[0]
    assert subclass.class_name == "app.models.AdminUser"
    assert subclass.location.relative_path == "app/models.py"
    assert subclass.location.line == 4


def test_class_hierarchy_returns_not_found_for_missing_class(tmp_path: Path) -> None:
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

    result = class_hierarchy(str(tmp_path), "app.models.Missing")

    assert result.found is False
    assert result.class_name == "app.models.Missing"
    assert result.subclasses == []
    assert result.error == "Class not found: app.models.Missing"
