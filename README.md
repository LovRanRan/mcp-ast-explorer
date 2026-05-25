# mcp-ast-explorer

<!-- mcp-name: io.github.LovRanRan/mcp-ast-explorer -->

MCP server for deterministic Python codebase symbol exploration.

`mcp-ast-explorer` indexes Python source files with LibCST and exposes focused MCP tools for codebase onboarding: definition lookup, function signatures, local references, direct call chains, and simple class hierarchy queries.

## Codebase Onboarding Stack

`mcp-ast-explorer` is the semantic symbol layer in a three-server MCP tool stack for Project 6 `wayfinder`, a codebase onboarding agent.

- [`mcp-repo-mapper`](https://github.com/LovRanRan/mcp-repo-mapper) maps repository structure, languages, entry points, framework evidence, and Python dependency edges.
- [`mcp-ast-explorer`](https://github.com/LovRanRan/mcp-ast-explorer) provides symbol-grounded Python definition, signature, reference, call-chain, and class-hierarchy lookups.
- [`mcp-test-runner`](https://github.com/LovRanRan/mcp-test-runner) runs local pytest/Jest checks and coverage summaries so agent claims can be verified against execution.

In `wayfinder`, this server feeds entry-point and symbol explanation while refusing to invent missing symbols.

## Status

This is a Python-only v1. TypeScript is registered as an unsupported backend placeholder so the server has an explicit extension point, but TypeScript analysis is not implemented yet.

The server does not use an LLM for symbol lookup. If a requested symbol or class is not present in the parsed index, tools return a structured not-found result instead of inventing an answer.

## Tools

| Tool | Purpose |
| --- | --- |
| `health()` | Returns `ok` for smoke checks. |
| `find_definition(path, symbol, language="python")` | Finds a module, class, function, or method definition. |
| `function_signature(path, symbol, language="python")` | Returns the signature for a function or method symbol. |
| `find_references(path, symbol, language="python")` | Returns same-module CST name references for an existing symbol. |
| `call_chain(path, from_symbol, depth=2, language="python")` | Returns direct callers detected from local references. |
| `class_hierarchy(path, class_name, language="python")` | Returns direct subclasses detected from simple base-class names. |

## Supported Scope

- Python files parsed by LibCST.
- Symbol kinds: modules, classes, functions, and methods.
- Same-module reference lookup for simple names.
- Direct caller detection from function or method containers.
- Direct subclass detection for simple `class Child(Base):` inheritance.
- Structured error responses for unsupported languages and missing symbols.

## Current Limitations

- Cross-file imports and package-wide resolution are out of scope for v1.
- Aliases, star imports, dynamic attribute access, and qualified references are not resolved.
- `call_chain` currently returns direct callers only; recursive multi-hop expansion is not implemented.
- `class_hierarchy` currently returns direct subclasses only and handles simple base names.
- TypeScript is intentionally unsupported in v1.

## Local Development

Install dependencies:

```bash
uv sync --extra dev
```

Run the MCP server:

```bash
uv run mcp-ast-explorer
```

Run verification:

```bash
uv run ruff check .
uv run mypy
uv run pytest
```

## License

MIT
