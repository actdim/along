# Python Coding Standards & Best Practices

Modern Python 3.11+ engineering conventions based on PEP 8, Google Python Style Guide, UV workspaces, and strict static type analysis.

---

## 1. Monorepos & Workspace Management with UV

- **UV Workspaces Standard**:
  - For multi-package or microservice repositories, use `uv` workspaces to orchestrate dependencies centrally in root `pyproject.toml`.
  - Declare workspace members under `[tool.uv.workspace]`. Sub-packages reference sibling packages using editable path dependencies (`{ workspace = true }`).

```toml
# pyproject.toml (root)
[tool.uv.workspace]
members = ["packages/*", "services/*"]
```

---

## 2. Static Type Annotations

- **Strict Typing**: Type annotate all function arguments and return types. Avoid `Any` where possible.
- **Modern Syntax**: Use Python 3.10+ union syntax (`X | Y` instead of `Union[X, Y]`, `list[str]` instead of `List[str]`).
- **Type Checking**: Ensure code passes `mypy --strict` or `pyright` without errors.

```python
# Recommended: Modern type hints and dataclass
from dataclasses import dataclass
from typing import Self

@dataclass(frozen=True, slots=True)
class Coordinate:
    x: float
    y: float

    @classmethod
    def from_tuple(cls, val: tuple[float, float]) -> Self:
        return cls(x=val[0], y=val[1])
```

---

## 3. Data Structures & Immutability

- **Dataclasses & Pydantic**: Use `@dataclass(frozen=True, slots=True)` for internal value objects and Pydantic `BaseModel` for external API validation.
- **Generators & Iterators**: Use generator expressions (`(x for x in data)`) instead of eager list comprehensions for memory-efficient iteration over large streams.
- **Context Managers**: Always manage I/O resources using `with` statements (`with open(...) as f:`).

---

## 4. Formatting & Linting Tooling

- **Ruff & Black**: Use Ruff for ultra-fast linting and Black/Ruff-format for deterministic code formatting.
- **Line Length**: Target standard 88 or 100 character line limits.
- **Naming Conventions**:
  - `snake_case`: Variables, functions, methods, modules.
  - `PascalCase`: Classes, Exceptions, Pydantic models.
  - `UPPER_SNAKE_CASE`: Constants.

---

## 5. Error Handling & Exceptions

- **Specific Exceptions**: Never catch bare `except:`. Catch specific exceptions (`except (ValueError, KeyError) as e:`).
- **Custom Exceptions**: Derive domain errors from a custom base exception class (`class DomainError(Exception): pass`).
- **Exception Chaining**: Use `raise NewException(...) from original_err` to preserve stack traces.

---

## 6. Packaging & Distributing AI Documentation (LLM-Wiki)

- **Standard PEP 621 `pyproject.toml` & Package Data**:
  - When publishing Python packages to PyPI or internal registries, configure the build backend to bundle `AGENTS.md`, `llms.txt`, and the `docs/` folder into wheels (`.whl`) and source distributions (`.tar.gz`).

```toml
# pyproject.toml (Hatchling / Standard PEP 621)
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "myorg-core"
version = "1.0.0"
readme = "README.md"
keywords = ["along", "ai-agent", "llms", "rules"]

[tool.hatch.build.targets.wheel.shared-data]
"AGENTS.md" = "myorg_core/AGENTS.md"
"llms.txt" = "myorg_core/llms.txt"
"docs" = "myorg_core/docs"
```

- **Setuptools & `MANIFEST.in` (Standard / Vanilla Tooling)**:
  - When using standard `setuptools`, ensure non-code AI files are included in source distributions and wheels:

```ini
# MANIFEST.in
include README.md
include AGENTS.md
include llms.txt
recursive-include docs *.md
```

```toml
# pyproject.toml (Setuptools)
[tool.setuptools.package-data]
"myorg_core" = ["AGENTS.md", "llms.txt", "docs/**/*.md"]
```

- **Poetry / Flit (Recommended Alternatives)**:
  - With Poetry or Flit, declare explicit inclusions in `pyproject.toml`:

```toml
# pyproject.toml (Poetry)
[tool.poetry]
name = "myorg-core"
include = [
    { path = "AGENTS.md" },
    { path = "llms.txt" },
    { path = "docs" }
]
```

- **Consumer & Upward Discovery Protocol**:
  - When downstream projects install the dependency via `pip install`, `uv add`, or `requirements.txt`, files are installed into `.venv/lib/site-packages/<package>/`.
  - The Along dependency scanner (`along-dep-scan`) inspects `pyproject.toml` / `requirements.txt`, resolves the installed package directory in the active virtual environment, detects `AGENTS.md` and `docs/`, and registers them into `docs/topic--dependencies.md`.


