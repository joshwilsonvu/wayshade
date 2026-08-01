"""Wayshade: a Python-controlled shader wallpaper renderer for Wayland."""

from .wayland import WaylandUnavailableError, connect

__all__ = ["WaylandUnavailableError", "connect"]
