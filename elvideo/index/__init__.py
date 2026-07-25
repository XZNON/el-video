"""Indexing pipeline: one video in, one validated ``footage_index.json`` out.

Module layout mirrors ``docs/IDEA.md`` § *Module layout* exactly, so Path A and Path B stay
swappable at the seam. ``gemini.py`` is the only Path-B-specific module; the rest is shared,
classical, and deterministic.
"""
