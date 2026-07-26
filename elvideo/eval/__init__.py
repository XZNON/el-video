"""Measurement tools that judge the index rather than build it.

Nothing here runs inside ``build_index``. The pipeline's own gates are shape checks — the schema
validates, ``t_end > t_start`` holds — and D-027 is the case that proves a caption on the wrong
shot has the right shape. This package is where the *content* of an index gets measured.
"""
