# AI Development Assistant Context

This file provides context for AI development assistants (Claude Code, GitHub Copilot, etc.) working on this project.

## Project Overview
<!-- Brief description of your project -->
This is a Python project using uv for package management...

## Technology Stack
- **Language:** Python 3.11+
- **Package Manager:** uv
- **Project Structure:** uv workspace with packages in `packages/` folder
- **Testing:** pytest
- **Linting/Formatting:** ruff

## Development Environment
- **Containerization:** Docker + devcontainers
- **Package Management:** uv (not pip/poetry/conda)

## Coding Standards
- Follow PEP 8 for Python code style
- Use type hints where applicable
- Use ruff for formatting and linting
- Write docstrings for all public functions and classes

## Common Development Commands (for AI assistants)
- `uv sync` - Install/update all dependencies
- `uv add <package>` - Add a dependency
- `uv run pytest` - Run tests
- `uv run ruff format` - Format code
- `uv run ruff check --fix` - Auto-fix linting issues

## Project Structure (uv workspace)
```
project-root/
├── pyproject.toml       # Workspace configuration
├── uv.lock             # Lock file
├── packages/           # Workspace members
│   ├── package-a/      # Individual package
│   └── package-b/      # Another package
├── tests/              # Test files
└── README.md           # Project documentation
```

## Guidelines for AI Assistants
- **IMPORTANT:** Always use `uv` commands, never `pip`, `poetry`, or `conda`
- Run `uv sync` after adding/removing dependencies
- Use `uv run pytest` to run tests after making changes
- Use `uv run ruff format` and `uv run ruff check --fix` for code quality
- For workspace projects, use `--package <member>` when targeting specific packages
- Follow existing code patterns and structure
- Consider security implications of changes
- Write comprehensive documentation

---
*This file can be used by any AI coding assistant to understand the project context.*
*Individual developers may have their own tool-specific context files (e.g., CLAUDE.local.md)*
