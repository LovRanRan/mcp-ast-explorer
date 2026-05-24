from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import libcst as cst
from libcst.metadata import CodeRange, MetadataWrapper, PositionProvider

IGNORED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}


SymbolKind = Literal["module", "class", "function", "method"]


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
            )
        )
        return True


def _position_for(visitor: cst.CSTVisitor, node: cst.CSTNode) -> CodeRange:
    position: CodeRange = visitor.get_metadata(PositionProvider, node)  # pyright: ignore[reportAssignmentType]
    return position


@dataclass(frozen=True)
class SourceLocation:
    path: Path
    relative_path: str
    line: int
    column: int


@dataclass(frozen=True)
class PythonSymbol:
    name: str
    qualified_name: str
    kind: SymbolKind
    location: SourceLocation
    signature: str | None
    source_code: str | None


@dataclass(frozen=True)
class ParsedPythonFile:
    path: Path
    relative_path: str
    source: str
    module: cst.Module


@dataclass(frozen=True)
class PythonParseError:
    path: Path
    relative_path: str
    message: str
    line: int
    column: int


@dataclass(frozen=True)
class PythonCstIndex:
    root: Path
    files: list[ParsedPythonFile]
    symbols: list[PythonSymbol]
    parse_errors: list[PythonParseError]


def find_definition_in_index(index: PythonCstIndex, symbol: str) -> PythonSymbol | None:
    for candidate in index.symbols:
        if candidate.qualified_name == symbol:
            return candidate
    return None


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
            )
        )

        wrapper = MetadataWrapper(module)
        collector = SymbolCollector(path=path, relative_path=relative_path, module_name=module_name)
        wrapper.visit(collector)
        symbols.extend(collector.symbols)
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
    )
