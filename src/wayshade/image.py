"""CPU-backed image resources that become GPU textures when drawn."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image as PillowImage


class ImageError(RuntimeError):
    """Raised when an image cannot be loaded or used."""


@dataclass
class Image:
    """An RGBA8 image, loaded from disk or allocated as an intermediate."""

    width: int
    height: int
    pixels: bytes | None = None
    source: Path | None = None
    texture: int | None = None
    framebuffer: int | None = None

    @classmethod
    def from_file(cls, path: str | Path) -> Image:
        image_path = Path(path)
        try:
            with PillowImage.open(image_path) as loaded:
                rgba = loaded.convert("RGBA")
                return cls(
                    rgba.width,
                    rgba.height,
                    rgba.tobytes(),
                    image_path,
                )
        except (OSError, ValueError) as error:
            raise ImageError(f"Could not load image {image_path}: {error}") from error

    @classmethod
    def empty(cls, width: int, height: int) -> Image:
        if width <= 0 or height <= 0:
            raise ImageError("Image dimensions must be positive")
        return cls(width, height)


__all__ = ["Image", "ImageError"]
