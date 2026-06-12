# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Early-stage Python project for heat pump modelling. The scaffold is in place but no domain logic exists yet.

## Environment

The project uses a devcontainer (Python 3.12, `uv` for package management). Development happens inside that container.

## Git Usage

Even though this is an exploratory project, we should use git heavily. Exploring new directions should happen on
branches, and larger bits of work should be split into small commits which get made on the way. No approval is
needed for branch commits.

When making changes that logically belong in a previous commit, it's best to create a fixup commit and let the
user decide when to rebase.

## Commands

```bash
uv sync          # install / sync dependencies
uv run main.py   # run the entry point
uv add <pkg>     # add a dependency (updates pyproject.toml and uv.lock)
uv run pytest    # run the test suite
uv run ruff check .          # lint
uv run ruff check --fix .    # lint and auto-fix
```

## Linting & the pre-commit hook

Ruff is configured in `pyproject.toml` (lint rules `E,F,I,UP`, line length 100).
We do **not** use `ruff format` — the code uses hand-tuned alignment the
formatter would churn.

A pre-commit hook in `.githooks/pre-commit` runs `ruff check` and blocks the
commit on any lint error. It is version-controlled but must be enabled once per
clone:

```bash
git config core.hooksPath .githooks
```

Bypass for a single commit with `git commit --no-verify`.
