from typing import Protocol

PYTHON_ONLY_ERROR = "Only Python is supported in v1."


class LanguageBackend(Protocol):
    @property
    def language(self) -> str: ...

    @property
    def display_name(self) -> str: ...

    @property
    def is_supported(self) -> bool: ...

    def unsupported_error(self) -> str | None: ...


class PythonLanguageBackend:
    @property
    def language(self) -> str:
        return "python"

    @property
    def display_name(self) -> str:
        return "Python"

    @property
    def is_supported(self) -> bool:
        return True

    def unsupported_error(self) -> str | None:
        return None


class TypeScriptLanguageBackend:
    @property
    def language(self) -> str:
        return "typescript"

    @property
    def display_name(self) -> str:
        return "TypeScript"

    @property
    def is_supported(self) -> bool:
        return False

    def unsupported_error(self) -> str | None:
        return PYTHON_ONLY_ERROR


_BACKENDS: dict[str, LanguageBackend] = {
    "python": PythonLanguageBackend(),
    "typescript": TypeScriptLanguageBackend(),
}


def get_language_backend(language: str) -> LanguageBackend | None:
    return _BACKENDS.get(language.lower())


def is_supported_language(language: str) -> bool:
    backend = get_language_backend(language)
    return backend is not None and backend.is_supported


def unsupported_language_error(language: str) -> str:
    backend = get_language_backend(language)
    if backend is None:
        return PYTHON_ONLY_ERROR
    return backend.unsupported_error() or PYTHON_ONLY_ERROR
