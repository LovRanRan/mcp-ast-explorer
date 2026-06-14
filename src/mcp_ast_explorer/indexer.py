from pathlib import Path

import libcst as cst
from libcst.metadata import CodeRange, MetadataWrapper, PositionProvider

from mcp_ast_explorer.models import (
    CallChain,
    CallChainCaller,
    ClassHierarchy,
    ClassHierarchySubclass,
    ParsedPythonFile,
    PythonCstIndex,
    PythonParseError,
    PythonReference,
    PythonSymbol,
    SourceLocation,
    SymbolKind,
)

IGNORED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}


def _module_name_for_path(relative_path: str) -> str:
    module_path = relative_path.removesuffix(".py")
    if module_path.endswith("/__init__"):
        module_path = module_path.removesuffix("/__init__")
    return module_path.replace("/", ".")


def _function_signature(node: cst.FunctionDef) -> str:
    params = [param.name.value for param in node.params.params]
    return f"{node.name.value}({', '.join(params)})"


class SymbolCollector(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, path: Path, relative_path: str, module_name: str) -> None:
        self.path = path
        self.relative_path = relative_path
        self.module_name = module_name
        self.class_stack: list[str] = []
        self.symbols: list[PythonSymbol] = []

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        position = _position_for(self, node)
        class_name = node.name.value
        qualified_name = ".".join([self.module_name, *self.class_stack, class_name])
        base_classes = [
            base.value.value
            for base in node.bases
            if isinstance(base.value, cst.Name)
        ]
        self.symbols.append(
            PythonSymbol(
                name=class_name,
                qualified_name=qualified_name,
                kind="class",
                location=SourceLocation(
                    path=self.path,
                    relative_path=self.relative_path,
                    line=position.start.line,
                    column=position.start.column,
                ),
                signature=None,
                source_code=_code_for_node(node),
                base_classes=base_classes,
            )
        )
        self.class_stack.append(class_name)
        return True

    def leave_ClassDef(self, original_node: cst.ClassDef) -> None:
        self.class_stack.pop()

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        position = _position_for(self, node)
        function_name = node.name.value
        kind: SymbolKind = "method" if self.class_stack else "function"
        qualified_name = ".".join([self.module_name, *self.class_stack, function_name])
        self.symbols.append(
            PythonSymbol(
                name=function_name,
                qualified_name=qualified_name,
                kind=kind,
                location=SourceLocation(
                    path=self.path,
                    relative_path=self.relative_path,
                    line=position.start.line,
                    column=position.start.column,
                ),
                signature=_function_signature(node),
                source_code=_code_for_node(node),
                base_classes=[],
            )
        )
        return True


class ReferenceCollector(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(
        self,
        path: Path,
        relative_path: str,
        module_name: str,
        symbols: list[PythonSymbol],
        source: str,
    ) -> None:
        self.path = path
        self.relative_path = relative_path
        self.module_name = module_name
        self.symbols = symbols
        self.source = source
        self.references: list[PythonReference] = []
        self.function_stack: list[str] = []
        self.symbols_by_qualified_name: dict[str, PythonSymbol] = {
            symbol.qualified_name: symbol for symbol in symbols
        }

    def visit_Name(self, node: cst.Name) -> None:
        qualified_name = f"{self.module_name}.{node.value}"
        symbol = self.symbols_by_qualified_name.get(qualified_name)
        if not symbol:
            return None
        position = _position_for(self, node)
        if position.start.line == symbol.location.line:
            return None
        lines = self.source.splitlines()
        context_code = lines[position.start.line - 1].strip()
        location = SourceLocation(
            path=self.path,
            relative_path=self.relative_path,
            line=position.start.line,
            column=position.start.column,
        )
        self.references.append(
            PythonReference(
                name=node.value,
                qualified_name=qualified_name,
                kind=symbol.kind,
                location=location,
                context_code=context_code,
                container_symbol=self.function_stack[-1] if self.function_stack else None,
            )
        )


    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        function_name = node.name.value
        qualified_name = f"{self.module_name}.{function_name}"
        self.function_stack.append(qualified_name)
        return True

    def leave_FunctionDef(self, original_node: cst.FunctionDef) -> None:
        self.function_stack.pop()


def build_call_chain_in_index(
    index: PythonCstIndex,
    symbol: str,
    depth: int = 2,
) -> CallChain:
    definition = find_definition_in_index(index, symbol)
    callers: list[CallChainCaller] = []
    if not definition:
        return CallChain(symbol=symbol, callers=[])
    references = find_references_in_index(index, symbol)
    for reference in references:
        if reference.container_symbol is None:
            continue
        callers.append(
            CallChainCaller(
                symbol=reference.container_symbol,
                context_code=reference.context_code,
            )
        )

    return CallChain(symbol=symbol, callers=callers)


def _position_for(visitor: cst.CSTVisitor, node: cst.CSTNode) -> CodeRange:
    position: CodeRange = visitor.get_metadata(PositionProvider, node)  # pyright: ignore[reportAssignmentType]
    return position


def find_definition_in_index(index: PythonCstIndex, symbol: str) -> PythonSymbol | None:
    # 1. Exact qualified-name match keeps precedence (unchanged behaviour).
    for candidate in index.symbols:
        if candidate.qualified_name == symbol:
            return candidate

    # 2. Fall back to a bare or partially-qualified name so callers don't need to
    #    know the full module path. On a src-layout repo a symbol's qualified_name
    #    is e.g. "src.wayfinder.graph.state.merge_summaries"; this lets
    #    "merge_summaries" or "graph.state.merge_summaries" resolve to it. Match on
    #    a dotted-boundary suffix or the leaf name, and resolve only when the match
    #    is unambiguous (one distinct symbol) — otherwise report not-found rather
    #    than guess between collisions.
    suffix = f".{symbol}"
    matches = {
        candidate.qualified_name: candidate
        for candidate in index.symbols
        if candidate.qualified_name.endswith(suffix) or candidate.name == symbol
    }
    if len(matches) == 1:
        return next(iter(matches.values()))
    return None


def find_references_in_index(index: PythonCstIndex, symbol: str) -> list[PythonReference]:
    definition = find_definition_in_index(index, symbol)
    if not definition:
        return []
    return [
        reference
        for reference in index.references
        if reference.qualified_name == definition.qualified_name
    ]


def _code_for_node(node: cst.CSTNode) -> str:
    return cst.Module([]).code_for_node(node).lstrip("\n")


def _is_ignored(path: Path, root: Path) -> bool:
    relative_parts = path.relative_to(root).parts
    return any(part in IGNORED_DIRS for part in relative_parts)


def build_cst_index(root: str | Path) -> PythonCstIndex:
    root_path = Path(root).resolve()
    files: list[ParsedPythonFile] = []
    symbols: list[PythonSymbol] = []
    parse_errors: list[PythonParseError] = []
    references: list[PythonReference] = []

    for path in sorted(root_path.rglob("*.py")):
        if _is_ignored(path, root_path):
            continue

        source = path.read_text(encoding="utf-8")
        relative_path = path.relative_to(root_path).as_posix()
        try:
            module = cst.parse_module(source)
        except cst.ParserSyntaxError as exc:
            parse_errors.append(
                PythonParseError(
                    path=path,
                    relative_path=relative_path,
                    message=exc.message,
                    line=exc.raw_line,
                    column=exc.raw_column,
                )
            )
            continue

        module_name = _module_name_for_path(relative_path)

        symbols.append(
            PythonSymbol(
                name=module_name.rsplit(".", maxsplit=1)[-1],
                qualified_name=module_name,
                kind="module",
                location=SourceLocation(
                    path=path,
                    relative_path=relative_path,
                    line=1,
                    column=0,
                ),
                signature=None,
                source_code=None,
                base_classes=[],
            )
        )

        wrapper = MetadataWrapper(module)
        symbol_collector = SymbolCollector(
            path=path,
            relative_path=relative_path,
            module_name=module_name
        )
        wrapper.visit(symbol_collector)
        symbols.extend(symbol_collector.symbols)
        reference_collector = ReferenceCollector(
            path=path,
            relative_path=relative_path,
            module_name=module_name,
            symbols=symbols,
            source=source,
        )
        wrapper.visit(reference_collector)
        references.extend(reference_collector.references)
        files.append(
            ParsedPythonFile(
                path=path,
                relative_path=relative_path,
                source=source,
                module=module,
            )
        )

    return PythonCstIndex(
        root=root_path,
        files=files,
        symbols=symbols,
        parse_errors=parse_errors,
        references=references,
    )


def build_class_hierarchy_in_index(
    index: PythonCstIndex,
    class_name: str,
) -> ClassHierarchy:
    target = find_definition_in_index(index, class_name)
    if target is None or target.kind != "class":
        return ClassHierarchy(class_name=class_name, subclasses=[])

    subclasses = [
        ClassHierarchySubclass(
            class_name=candidate.qualified_name,
            location=candidate.location,
        )
        for candidate in index.symbols
        if candidate.kind == "class" and target.name in candidate.base_classes
    ]

    return ClassHierarchy(class_name=class_name, subclasses=subclasses)
