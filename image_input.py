"""Shared image-input helpers for camera and uploaded files."""

from __future__ import annotations

import io
from typing import Any, Iterable


def collect_image_inputs(values: Iterable[Any] | None, *, limit: int) -> list[Any]:
    """Return the same non-empty objects for either Streamlit input widget."""
    if limit < 1:
        return []
    return [value for value in (values or ()) if value is not None][:limit]


def image_bytes(image_file: Any) -> bytes:
    """Read camera/upload/bytes input without depending on its concrete class."""
    if isinstance(image_file, (bytes, bytearray, memoryview)):
        data = bytes(image_file)
    elif hasattr(image_file, "getvalue"):
        data = bytes(image_file.getvalue())
    elif hasattr(image_file, "read"):
        position = image_file.tell() if hasattr(image_file, "tell") else None
        data = bytes(image_file.read())
        if position is not None and hasattr(image_file, "seek"):
            image_file.seek(position)
    else:
        raise TypeError("unsupported image input")
    if not data:
        raise ValueError("empty image input")
    return data


def load_rgb_image(image_file: Any) -> Any:
    """Decode every accepted input through the same Pillow RGB path."""
    from PIL import Image

    with Image.open(io.BytesIO(image_bytes(image_file))) as image:
        return image.convert("RGB")
