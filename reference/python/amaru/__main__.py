"""Allow running Amaru CLI via: python -m amaru"""

import sys

from .cli import main

sys.exit(main())
