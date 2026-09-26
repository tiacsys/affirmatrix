"""``python -m affirmatrix.cli`` — the same entry point ``[project.scripts]`` installs."""

from __future__ import annotations

import sys

from affirmatrix.cli import main

if __name__ == "__main__":
    sys.exit(main())
