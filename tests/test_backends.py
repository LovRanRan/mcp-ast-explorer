from mcp_ast_explorer.backends import (
    get_language_backend,
    is_supported_language,
    unsupported_language_error,
)


def test_backend_registry_exposes_supported_python_backend() -> None:
    backend = get_language_backend("python")

    assert backend is not None
    assert backend.language == "python"
    assert backend.display_name == "Python"
    assert backend.is_supported is True
    assert is_supported_language("python") is True


def test_backend_registry_includes_unsupported_typescript_scaffold() -> None:
    backend = get_language_backend("typescript")

    assert backend is not None
    assert backend.language == "typescript"
    assert backend.display_name == "TypeScript"
    assert backend.is_supported is False
    assert is_supported_language("typescript") is False
    assert unsupported_language_error("typescript") == "Only Python is supported in v1."


def test_unknown_backend_is_not_supported() -> None:
    assert get_language_backend("go") is None
    assert is_supported_language("go") is False
    assert unsupported_language_error("go") == "Only Python is supported in v1."
