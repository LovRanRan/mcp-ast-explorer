import asyncio
from pathlib import Path

from fastmcp import Client

from mcp_ast_explorer.server import find_definition, function_signature, health, mcp


def test_health_returns_ok() -> None:
    assert health() == "ok"


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
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )

    async def run_client() -> None:
        async with Client(mcp) as client:
            tools = await client.list_tools()
            tool_names = {tool.name for tool in tools}

            assert "health" in tool_names
            assert "find_definition" in tool_names
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

    asyncio.run(run_client())
