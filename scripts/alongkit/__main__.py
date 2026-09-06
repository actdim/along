import os
import sys

if __name__ == '__main__':
    if not __package__:
        parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if parent not in sys.path:
            sys.path.insert(0, parent)
        from alongkit import cli
    else:
        from . import cli
    sys.exit(cli.main())
