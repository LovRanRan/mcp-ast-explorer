from fastmcp import FastMCP

from mcp_ast_explorer.backends import is_supported_language, unsupported_language_error
from mcp_ast_explorer.indexer import (
    build_call_chain_in_index,
    build_class_hierarchy_in_index,
    build_cst_index,
    find_definition_in_index,
    find_references_in_index,
)
from mcp_ast_explorer.schemas import (
    CallChainCallerResult,
    CallChainResult,
    ClassHierarchyLocation,
    ClassHierarchyResult,
    ClassHierarchySubclassResult,
    DefinitionLocation,
    DefinitionResult,
    FindReferencesResult,
    FunctionSignatureResult,
    ReferenceLocation,
    ReferenceResult,
)

mcp = FastMCP("mcp-ast-explorer")


@mcp.tool
def health() -> str:
    return "ok"


@mcp.tool
def find_definition(path: str, symbol: str, language: str = "python") -> DefinitionResult:
    if not is_supported_language(language):
        return DefinitionResult(
            found=False,
            symbol=symbol,
            error=unsupported_language_error(language),
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
def find_references(path: str, symbol: str, language: str = "python") -> FindReferencesResult:
    if not is_supported_language(language):
        return FindReferencesResult(
            found=False,
            symbol=symbol,
            references=[],
            error=unsupported_language_error(language),
        )

    index = build_cst_index(path)
    definition = find_definition_in_index(index, symbol)
    if definition is None:
        return FindReferencesResult(
            found=False,
            symbol=symbol,
            references=[],
            error=f"Symbol not found: {symbol}",
        )
    references = find_references_in_index(index, symbol)
    return FindReferencesResult(
        found=True,
        symbol=symbol,
        references=[
            ReferenceResult(
                name=reference.name,
                qualified_name=reference.qualified_name,
                kind=reference.kind,
                location=ReferenceLocation(
                    path=str(reference.location.path),
                    relative_path=reference.location.relative_path,
                    line=reference.location.line,
                    column=reference.location.column,
                ),
                context_code=reference.context_code,
            )
            for reference in references
        ],
    )


@mcp.tool
def function_signature(
    path: str,
    symbol: str,
    language: str = "python",
) -> FunctionSignatureResult:
    if not is_supported_language(language):
        return FunctionSignatureResult(
            found=False,
            symbol=symbol,
            error=unsupported_language_error(language),
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


@mcp.tool
def call_chain(
    path: str,
    from_symbol: str,
    depth: int = 2,
    language: str = "python",
) -> CallChainResult:
    if not is_supported_language(language):
        return CallChainResult(
            found=False,
            symbol=from_symbol,
            callers=[],
            error=unsupported_language_error(language),
        )

    index = build_cst_index(path)
    definition = find_definition_in_index(index, from_symbol)
    if not definition:
        return CallChainResult(
            found=False,
            symbol=from_symbol,
            callers=[],
            error=f"Symbol not found: {from_symbol}",
        )
    chain = build_call_chain_in_index(index, from_symbol, depth=depth)
    return CallChainResult(
        found=True,
        symbol=from_symbol,
        callers=[
            CallChainCallerResult(
                symbol=caller.symbol,
                context_code=caller.context_code,
            )
            for caller in chain.callers
        ],
    )


@mcp.tool
def class_hierarchy(
    path: str,
    class_name: str,
    language: str = "python",
) -> ClassHierarchyResult:
    if not is_supported_language(language):
        return ClassHierarchyResult(
            found=False,
            class_name=class_name,
            subclasses=[],
            error=unsupported_language_error(language),
        )

    index = build_cst_index(path)
    definition = find_definition_in_index(index, class_name)
    if definition is None or definition.kind != "class":
        return ClassHierarchyResult(
            found=False,
            class_name=class_name,
            subclasses=[],
            error=f"Class not found: {class_name}",
        )

    hierarchy = build_class_hierarchy_in_index(index, class_name)
    return ClassHierarchyResult(
        found=True,
        class_name=class_name,
        subclasses=[
            ClassHierarchySubclassResult(
                class_name=subclass.class_name,
                location=ClassHierarchyLocation(
                    path=str(subclass.location.path),
                    relative_path=subclass.location.relative_path,
                    line=subclass.location.line,
                    column=subclass.location.column,
                ),
            )
            for subclass in hierarchy.subclasses
        ],
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
