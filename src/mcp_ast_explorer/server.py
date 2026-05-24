from fastmcp import FastMCP
from pydantic import BaseModel

from mcp_ast_explorer.indexer import build_cst_index, find_definition_in_index

mcp = FastMCP("mcp-ast-explorer")


class DefinitionLocation(BaseModel):
    path: str
    relative_path: str
    line: int
    column: int


class DefinitionResult(BaseModel):
    found: bool
    symbol: str
    name: str | None = None
    qualified_name: str | None = None
    kind: str | None = None
    location: DefinitionLocation | None = None
    signature: str | None = None
    source_code: str | None = None
    error: str | None = None


class FunctionSignatureResult(BaseModel):
    found: bool
    symbol: str
    name: str | None = None
    qualified_name: str | None = None
    kind: str | None = None
    signature: str | None = None
    error: str | None = None


@mcp.tool
def health() -> str:
    return "ok"


@mcp.tool
def find_definition(path: str, symbol: str, language: str = "python") -> DefinitionResult:
    if language != "python":
        return DefinitionResult(
            found=False,
            symbol=symbol,
            error="Only Python is supported in v1.",
        )

    index = build_cst_index(path)
    definition = find_definition_in_index(index, symbol)
    if definition is None:
        return DefinitionResult(
            found=False,
            symbol=symbol,
            error=f"Symbol not found: {symbol}",
        )

    return DefinitionResult(
        found=True,
        symbol=symbol,
        name=definition.name,
        qualified_name=definition.qualified_name,
        kind=definition.kind,
        location=DefinitionLocation(
            path=str(definition.location.path),
            relative_path=definition.location.relative_path,
            line=definition.location.line,
            column=definition.location.column,
        ),
        signature=definition.signature,
        source_code=definition.source_code,
    )


@mcp.tool
def function_signature(
    path: str,
    symbol: str,
    language: str = "python",
) -> FunctionSignatureResult:
    if language != "python":
        return FunctionSignatureResult(
            found=False,
            symbol=symbol,
            error="Only Python is supported in v1.",
        )

    index = build_cst_index(path)
    definition = find_definition_in_index(index, symbol)
    if definition is None:
        return FunctionSignatureResult(
            found=False,
            symbol=symbol,
            error=f"Symbol not found: {symbol}",
        )

    if definition.kind not in {"function", "method"}:
        return FunctionSignatureResult(
            found=False,
            symbol=symbol,
            name=definition.name,
            qualified_name=definition.qualified_name,
            kind=definition.kind,
            error=f"Symbol is not a function or method: {symbol}",
        )

    return FunctionSignatureResult(
        found=True,
        symbol=symbol,
        name=definition.name,
        qualified_name=definition.qualified_name,
        kind=definition.kind,
        signature=definition.signature,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
