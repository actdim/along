"""Along Dashboard & Knowledge Base Engine."""

import sys
from pathlib import Path

_parent = Path(__file__).resolve().parent.parent
for _cand in [_parent / "scripts", _parent]:
    if (_cand / "alongkit").is_dir() and str(_cand) not in sys.path:
        sys.path.insert(0, str(_cand))

try:
    from alongkit.version import CURRENT_VERSION as __version__
except ImportError:
    __version__ = "3.9.4"


