# Wayshade

A Python-controlled shader wallpaper renderer for Linux/Wayland.

The project is currently implementing the Phase 0 graphics feasibility spike
from [`plan.md`](plan.md). The initial native path is:

- PyWayland for the Wayland client connection;
- generated PyWayland bindings for `wlr-layer-shell-unstable-v1`;
- EGL/OpenGL for GPU-backed presentation;
- Pillow for PNG, JPEG, and WebP image loading.

## Development

This project uses [uv](https://docs.astral.sh/uv/) and a project-local
`.venv` created by `uv sync`. The repository also includes a Nix development
flake and direnv integration. With Nix and direnv installed, entering the
repository activates the development shell automatically; otherwise run
`nix develop` explicitly:

```sh
nix develop
uv sync
uv run pytest
uv run ruff check .
```

The development shell supplies Python, uv, Wayland libraries, protocol XML,
and the protocol scanner. It scopes the Wayland library path to this project
only. It deliberately does not provide or select an OpenGL driver: GPU driver
selection belongs to the host distribution, just as it does on Arch and other
non-NixOS systems. Wayshade does not require a `nixGL` wrapper.

A compositor session is required for the connection check:

```sh
uv run python -c 'from wayshade.wayland import connect; print(connect())'
```

The generated layer-shell bindings are included in the package, so end users
do not need the `wlr-protocols` XML package installed. They do need a Wayland
client runtime, EGL/OpenGL runtime and driver, and a compositor implementing
layer shell.

## Status

Only the dependency and protocol foundation is complete. The next Phase 0
step is creating the layer-shell surface, EGL window/context, and a frame-paced
solid-color draw before building the public rendering API.
