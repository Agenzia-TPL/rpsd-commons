# Contributing to rpsd-commons

Thank you for your interest in contributing. This project is part of the
Rapsodia project and is published as open source under the
[BSD 3-Clause License](LICENSE), following the Italian Public Administration
open-source guidelines (CAD Art. 69 and Developers Italia).

## Reporting bugs

Please open an issue on the GitHub issue tracker:

<https://github.com/Agenzia-TPL/rpsd-commons/issues>

When reporting a bug, include:

- The package affected (`rpsd-storage`, `rpsd-transport`, or `rpsd-flow`).
- The version (all packages share a single synchronized version).
- Steps to reproduce, the expected behaviour, and the actual behaviour.
- Relevant logs or tracebacks.

## Submitting changes

1. **Fork** the repository.
2. Create a **feature branch** from `main`
   (e.g. `git checkout -b fix/storage-retry`).
3. Make your changes, keeping commits focused and well described.
4. Ensure the code is formatted, linted, and tested (see below).
5. Open a **pull request** against `main`, describing what changed and why.

## Coding standards

This project targets **Python 3.13+** and uses [uv](https://docs.astral.sh/uv/)
for all dependency and execution tasks (never `pip`, `poetry`, or `conda`).

- Follow **PEP 8** and use **`ruff`** for formatting and linting.
- Keep lines **under 88 characters** (the project's line-length limit).
- Use **type hints**, with modern syntax (`list`, `dict`, `str | None`).
- Write **docstrings** for all public functions and classes.
- Prefer **absolute imports** over relative ones.
- Do not introduce workarounds such as `# type: ignore[...]` or `cast()`.

Format and check before pushing:

```bash
uv run ruff format
uv run ruff check --fix
```

## Running tests

Run the full suite with:

```bash
uv run pytest
```

Useful variations:

```bash
uv run pytest packages/rpsd-storage/tests/   # one package
uv run pytest -m "not integration"           # skip integration tests
uv run pytest -m integration                 # integration tests only
```

## SPDX headers (required for new files)

Every source file must carry an SPDX licence header. New `.py` files must begin
with the following block (after the shebang line, if any):

```python
# SPDX-License-Identifier: BSD-3-Clause
# SPDX-FileCopyrightText: 2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO,
# MONZA E BRIANZA, LODI, PAVIA
```

You can add and verify headers with the bundled helper:

```bash
# Add headers to any files that are missing them:
bash ai-skills/open-source-it-pa/scripts/check_headers.sh \
  --fix --ext py \
  --license BSD-3-Clause \
  --copyright "2026 AGENZIA TPL BACINO CITTA' METROPOLITANA MILANO, MONZA E BRIANZA, LODI, PAVIA" \
  packages examples src

# Verify every file is covered (this is enforced in CI):
bash ai-skills/open-source-it-pa/scripts/check_headers.sh \
  --check --ext py packages examples src
```

The CI pipeline runs the `--check` command and will fail if any source file is
missing its header.

## Contributor licence terms (CLA)

By submitting a pull request to this repository, you certify that:

1. You have the right to submit the contribution under the project licence.
2. The contribution is your original work, or you otherwise have the necessary
   rights to submit it.
3. You grant the project maintainer the right to redistribute your
   contributions under any OSI-approved open source licence, including future
   versions of the project licence or a compatible copyleft licence such as
   `EUPL-1.2` or `AGPL-3.0-or-later`.

This lightweight agreement is accepted implicitly when you open a pull request;
no signature is required. It preserves the maintainer's ability to relicense
future versions of the project — for example to adopt a stronger copyleft
licence to protect against unattributed reuse by third parties — without having
to obtain retroactive consent from every contributor.
