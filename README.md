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

## Status and handoff

The project is partway through **Phase 0: Graphics feasibility spike** from
[`plan.md`](plan.md). The dependency setup, protocol binding, compositor
connection, global discovery, wallpaper surface, EGL context creation,
compositor-paced presentation, and offscreen texture sampling are implemented.
The project is ready to move from the feasibility spike into the rendering
core.

### Working pieces

The current stack is:

- Python 3.13 with `uv` for project dependencies;
- PyWayland for the Wayland client connection and protocol object machinery;
- two generated Python bindings for `wlr-layer-shell-unstable-v1`, packaged in
  `src/wayshade/_protocol/`;
- PyOpenGL selected for the eventual OpenGL calls;
- Pillow selected for the later RGBA8 image loader;
- EGL/Wayland native libraries supplied by the host environment.

The public code currently exposes these low-level helpers:

```python
from wayshade import create_wallpaper, discover_globals

# Binds wl_compositor, zwlr_layer_shell_v1, and the first wl_output.
globals = discover_globals()
globals.close()

# Creates a configured fullscreen background surface and waits for configure.
wallpaper = create_wallpaper()
print(wallpaper.width, wallpaper.height)
wallpaper.close()
```

`create_wallpaper()` creates and configures a wallpaper surface. Calling
`wallpaper.present_solid()` lazily creates the Wayland-EGL window, an RGBA8 EGL
context/surface, clears the framebuffer, and swaps one solid-color frame. Call
`wallpaper.wait_for_frame()` before presenting the next frame; it blocks on the
Wayland frame callback instead of busy-looping. The surface keeps the EGL
resources alive until `close()` destroys them before the Wayland objects.

The live Niri validation completed so far has confirmed:

- a Wayland connection can be established;
- the compositor advertises the required globals;
- the layer-shell surface can be assigned to the background layer;
- all four edges can be anchored;
- the compositor sends a configure event;
- the negotiated output size is currently `2048 × 1280` on the development
  machine;
- the surface can be destroyed cleanly before any buffer is attached.

### Development and validation

With direnv enabled and the repository approved, entering the directory should
activate the flake automatically:

```sh
direnv allow
cd /path/to/wayshade
```

Without direnv, enter the same environment explicitly:

```sh
nix develop
```

Then run the Python checks:

```sh
uv sync
uv run pytest
uv run ruff check .
```

To validate the current Wayland surface path against a running compositor:

```sh
uv run python -c \
  'from wayshade import create_wallpaper; w = create_wallpaper(); print(w.width, w.height); w.present_solid(); w.close()'
```

A compositor session with `wlr-layer-shell-unstable-v1` support is required.
Niri is the primary target; Sway and Hyprland are later compatibility targets.
The flake supplies development-time Wayland libraries and protocol tools but
does not provide or select an OpenGL driver. GPU driver selection remains the
host distribution's responsibility, and Wayshade does not require a `nixGL`
wrapper.

### Next implementation step: Phase 1 rendering core

The Phase 0 feasibility spike is complete. Live validation on Niri confirmed:
background layering, full-output coverage at `2048 × 1280`, EGL presentation,
frame callbacks, offscreen framebuffer rendering, texture sampling, and clean
resource release.

Begin Phase 1 with the explicit renderer/session foundation:

1. Define the renderer and wallpaper target ownership model.
2. Add output selection by default/primary output and numeric index.
3. Implement fragment shader loading from strings and files.
4. Implement fullscreen rendering and scalar/vector uniform state.
5. Move the current low-level presentation behavior behind that renderer API.

The internal `offscreen_test()` and `present_solid()` methods remain feasibility
helpers until the public `Renderer`, `Shader`, `Image`, and `Target` types are
implemented.

### Decisions already made

- The first output is used by the current surface helper. Numeric output
  selection is not implemented yet.
- The surface is background-layer, fullscreen, and non-interactive.
- Layer-shell bindings are generated during development but included in the
  package, so end users do not need `wlr-protocols` installed.
- Core Wayland and `xdg-shell` generated files are not duplicated; the packaged
  layer-shell bindings reuse PyWayland's versions.
- The project remains Wayland-specific and does not use a normal-window
  fallback.
- The public rendering API should wait until the backend passes the Phase 0
  feasibility test.

### Known limitations

- No higher-level renderer, shader, or image API yet; the low-level EGL,
  frame-callback, and offscreen texture probes are complete.
- No shader compilation or uniform handling.
- No image loading into GPU textures.
- No frame callback loop.
- No output index/name selection.
- No hotplug or layout migration.
- No multi-monitor support.
- The current generated bindings follow PyWayland's protocol runtime API;
  changes to the PyWayland major API should be treated as compatibility work.

The implementation plan remains the source of truth for the intended API and
phase boundaries. The next session should begin with the EGL bridge, not with
multipass rendering or the higher-level convenience API.
