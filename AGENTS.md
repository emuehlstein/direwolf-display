# Repository Guidelines

Direwolf Display is evolving toward a modular embedded display stack. These guidelines keep contributions consistent while the codebase grows.

## Project Structure & Module Organization
Keep a flat top level. Place firmware and rendering code in `src/`, grouped by feature (`src/render/`, `src/drivers/`). Store integration tests under `tests/` mirrored to their `src` modules. Hardware definitions, board profiles, and calibration data belong in `hardware/`. Assets such as bitmaps or fonts go in `assets/`. Documentation drafts live in `docs/`, and automation scripts (build, flashing, data pulls) live in `scripts/`. If a directory is missing, create it before committing related files.

## Build, Test, and Development Commands
Use the provided `Makefile` targets as the single entry point: `make setup` installs toolchains and Python deps, `make lint` runs formatting checks, `make test` executes the automated suite, and `make flash BOARD=<id>` pushes firmware to a target board. For quick module checks, run `python -m src.<module>` inside the activated virtualenv.

## Coding Style & Naming Conventions
Default to 4-space indentation for Python and follow Black-compatible wrapping. C/C++ sources should format with clang-format using the repository `.clang-format` profile. Module directories use snake_case; classes use PascalCase; hardware profile files use `board_<name>.yml`. Keep in-line comments concise and prefer docstrings for module-level summaries.

## Testing Guidelines
All new logic requires unit coverage via pytest; mirror the module under test (`tests/render/test_framebuffer.py`). Integration tests should run with `make test-hardware` and mock hardware when possible. Record hardware dependencies in the test docstring and guard them with `@pytest.mark.hardware`. Maintain >85% line coverage, and update `tests/README.md` when adding new fixtures.

## Commit & Pull Request Guidelines
Write Conventional Commit messages (`feat: add framebuffer double-buffering`). Reference linked issues in the body and document risky changes under a `Testing` bullet. Pull requests must include a concise summary, screenshots or oscilloscope captures when visual output changes, and a checklist of passing `make lint` and `make test`. Request at least one reviewer before merging.
