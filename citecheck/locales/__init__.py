"""User-facing text. One module per language, same names in each. French only for now.

Usage: `from .locales import t`, then `t.TITLE`.
"""
from . import fr as t

__all__ = ["t"]
