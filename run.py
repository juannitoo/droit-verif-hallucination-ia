"""Entry point for the executable (PyInstaller cannot start a package's __main__)."""
import sys

from citecheck.__main__ import main

sys.exit(main())
