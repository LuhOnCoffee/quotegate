"""`python3 -m quotegate ...` - lets the Claude Code plugin run the CLI straight
from its own directory (PYTHONPATH=<plugin>/src) with nothing to install:
quotegate has no dependencies outside the standard library."""
import sys

from .cli import main

sys.exit(main())
