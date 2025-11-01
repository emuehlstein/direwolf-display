"""Utility helpers for loading packaged HTML templates."""

from __future__ import annotations

from functools import lru_cache
from importlib import resources


@lru_cache(maxsize=None)
def load_template(name: str) -> str:
    """Return the contents of a packaged template."""

    package = __name__
    with resources.files(package).joinpath(name).open("r", encoding="utf-8") as handle:
        return handle.read()
