"""Data-only loader for the elementary competition hierarchy.

The hierarchy is stored as a literal in the legacy learning-map source. Read
that literal without importing the Streamlit/UI module, so service imports can
never execute the app entrypoint as a side effect.
"""

from __future__ import annotations

import ast
from pathlib import Path


def _load_hierarchy() -> dict:
    source_path = Path(__file__).resolve().parents[1] / "learning_map.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8-sig"), filename=str(source_path))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "ELEMENTARY_COMPETITION_HIERARCHY"
            for target in node.targets
        ):
            value = ast.literal_eval(node.value)
            if not isinstance(value, dict):
                raise TypeError("ELEMENTARY_COMPETITION_HIERARCHY must be a dict")
            return value
    raise RuntimeError("ELEMENTARY_COMPETITION_HIERARCHY literal not found")


ELEMENTARY_COMPETITION_HIERARCHY = _load_hierarchy()
