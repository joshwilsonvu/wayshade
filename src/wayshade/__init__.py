"""Wayshade: a Python-controlled shader wallpaper renderer for Wayland."""

from .wallpaper import WallpaperSurface, WallpaperSurfaceError, create_wallpaper
from .wayland import WaylandUnavailableError, connect
from .wayland_session import (
    MissingWaylandGlobalError,
    WaylandGlobals,
    discover_globals,
)

__all__ = [
    "MissingWaylandGlobalError",
    "WallpaperSurface",
    "WallpaperSurfaceError",
    "WaylandGlobals",
    "WaylandUnavailableError",
    "connect",
    "create_wallpaper",
    "discover_globals",
]
