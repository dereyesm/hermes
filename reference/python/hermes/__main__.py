"""Allow running HERMES CLI via: python -m hermes"""

import sys

from .cli import main

sys.exit(main())
