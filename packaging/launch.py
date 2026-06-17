"""Frozen-app entry point. Imports the package properly (relative imports need a package)."""

import sys

from hssk_gui.app import main

if __name__ == "__main__":
    sys.exit(main())
