from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import libcst as cst

SymbolKind = Literal["module", "class", "function", "method"]


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
    base_classes: list[str]


@dataclass(frozen=True)
class ParsedPythonFile:
    path: Path
    relative_path: str
    source: str
    module: cst.Module


@dataclass(frozen=True)
class PythonReference:
    name: str
    qualified_name: str
    kind: SymbolKind
    location: SourceLocation
    context_code: str
    container_symbol: str | None


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
    references: list[PythonReference]


@dataclass(frozen=True)
class CallChainCaller:
    symbol: str
    context_code: str


@dataclass(frozen=True)
class CallChain:
    symbol: str
    callers: list[CallChainCaller]


@dataclass(frozen=True)
class ClassHierarchySubclass:
    class_name: str
    location: SourceLocation


@dataclass(frozen=True)
class ClassHierarchy:
    class_name: str
    subclasses: list[ClassHierarchySubclass]
