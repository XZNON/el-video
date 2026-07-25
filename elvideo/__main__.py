"""Makes ``python -m elvideo index in.mp4`` work — the DoD's entrypoint.

Not listed in the bootstrap tree; added because ``python -m <pkg>`` requires it. See
``state/decisions-log.md`` D-006.
"""

from __future__ import annotations

from elvideo.cli import main

if __name__ == "__main__":
    main()
