"""Fragment shader state used by the rendering API."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .image import Image


class ShaderError(RuntimeError):
    """Raised for invalid shader source or uniform state."""


UniformValue = float | int | bool | tuple[float | int, ...] | Image | None


@dataclass
class Shader:
    """A fragment shader and its persistent uniform values.

    Compilation is performed when the shader is first drawn, while uniform
    values can be changed before or between draws.
    """

    source: str
    uniforms: dict[str, UniformValue] = field(default_factory=dict)
    source_path: Path | None = None

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ShaderError("Fragment shader source must not be empty")

    def set(
        self, name: str | Mapping[str, UniformValue], value: UniformValue | None = None
    ) -> Shader:
        """Set one uniform or update several uniforms, then return ``self``."""
        if isinstance(name, Mapping):
            if value is not None:
                raise TypeError("value must be omitted when setting a mapping")
            updates = name
        else:
            if value is None:
                raise TypeError("a uniform value is required")
            updates = {name: value}
        for uniform_name, uniform_value in updates.items():
            if not uniform_name or not isinstance(uniform_name, str):
                raise ShaderError("Uniform names must be non-empty strings")
            if not _is_uniform_value(uniform_value):
                raise ShaderError(
                    f"Unsupported value for uniform {uniform_name!r}; "
                    "expected a scalar or numeric tuple"
                )
            self.uniforms[uniform_name] = uniform_value
        return self

    # alias
    uniform = set

    @classmethod
    def from_file(cls, path: str | Path) -> Shader:
        """Load fragment shader source from a UTF-8 file."""
        source_path = Path(path)
        try:
            return cls(source_path.read_text(encoding="utf-8"), source_path=source_path)
        except OSError as error:
            raise ShaderError(
                f"Could not read shader file {source_path}: {error}"
            ) from error


def _is_uniform_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (bool, int, float, Image)):
        return True
    return (
        isinstance(value, tuple)
        and 1 <= len(value) <= 4
        and all(isinstance(item, (bool, int, float)) for item in value)
    )


__all__ = ["Shader", "ShaderError", "UniformValue"]
