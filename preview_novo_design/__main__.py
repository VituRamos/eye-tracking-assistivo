"""Permite ``python -m preview_novo_design``."""
from __future__ import annotations

import sys

from .renderizar import main

if __name__ == "__main__":
    sys.exit(main())
