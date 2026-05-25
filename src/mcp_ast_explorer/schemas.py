from pydantic import BaseModel, Field


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


class ReferenceLocation(BaseModel):
    path: str
    relative_path: str
    line: int
    column: int


class ReferenceResult(BaseModel):
    name: str
    qualified_name: str
    kind: str
    location: ReferenceLocation
    context_code: str


def _empty_references() -> list[ReferenceResult]:
    return []


class FindReferencesResult(BaseModel):
    found: bool
    symbol: str
    references: list[ReferenceResult] = Field(default_factory=_empty_references)
    error: str | None = None


class CallChainCallerResult(BaseModel):
    symbol: str
    context_code: str


def _empty_call_chain_callers() -> list[CallChainCallerResult]:
    return []


class CallChainResult(BaseModel):
    found: bool
    symbol: str
    callers: list[CallChainCallerResult] = Field(default_factory=_empty_call_chain_callers)
    error: str | None = None


class ClassHierarchyLocation(BaseModel):
    path: str
    relative_path: str
    line: int
    column: int


class ClassHierarchySubclassResult(BaseModel):
    class_name: str
    location: ClassHierarchyLocation


def _empty_class_hierarchy_subclasses() -> list[ClassHierarchySubclassResult]:
    return []


class ClassHierarchyResult(BaseModel):
    found: bool
    class_name: str
    subclasses: list[ClassHierarchySubclassResult] = Field(
        default_factory=_empty_class_hierarchy_subclasses
    )
    error: str | None = None