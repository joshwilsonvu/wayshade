1. **wgpu-py** is actively maintained (last release June 2026), uses wgpu-native (Rust-based), supports WebGPU spec
2. **python-wayland** (not pywayland) is a pure Python implementation with no external dependencies, includes Hyprland and wlroots protocols - this is better than pywayland which wraps libwayland
3. **PEP 723** inline script metadata is well-supported by uv, allowing single-file scripts with embedded dependencies

Now I need to write a comprehensive implementation plan that includes:

- User-facing API design
- Library recommendations
- Packaging strategy (single file with PEP 723)
- Technical implementation details
- Instructions for the coding agent

Key decisions:

- Use `python-wayland` (pure Python, no C deps) over `pywayland` (wraps libwayland)
- Use `wgpu-py` for graphics (WebGPU API, actively maintained)
- Use PEP 723 inline metadata for single-file distribution
- Design a WebGL-like API that's simple but flexible
- Include examples showing ambient data access (the killer feature)

# Implementation Plan: Wayland Shader Wallpaper Library

## Overview

A Python library for rendering user-provided GLSL shaders as Wayland desktop wallpapers with WebGL-like API. Users can access ambient system data (CPU load, time, etc.) and pass it to shaders.

The difference between this and other existing projects like Neowall is that instead of a single parent program defining the rendering pipeline and accepting a shader + some config, this project will invert control and allow a user-provided script to define the rendering pipeline (i.e. so you can load images as textures, run multiple passes, etc.) and pass in any information they want as uniforms. As a library, we'll offer a high-level API (a little higher than WebGL) to make it super easy to render images or shaders.

It should also be easy to use--don't want to make people go "oh man, I have to use the Python ecosystem?". `uv` helps with that.

## Recommended Libraries

**Core dependencies:**

- `wgpu` (wgpu-py) - WebGPU for Python, wraps wgpu-native [^3]
- `python-wayland` - Pure Python Wayland protocol implementation, no C dependencies, includes wlroots/Hyprland protocols [^1]
- `Pillow` - Image loading for textures
- `numpy` - Uniform data handling

**Development:**

- `uv` - Package manager with PEP 723 support for single-file scripts [^2]

## Packaging Strategy

**Single-file distribution using PEP 723 inline metadata:**

```python
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "wgpu>=0.18.0",
#     "python-wayland>=0.1.0",
#     "Pillow>=10.0.0",
#     "numpy>=1.24.0",
# ]
# ///
```

This allows users to run the library with `uv run wallpaper.py` without needing a separate project setup.

## User-Facing API Design

### Core API (WebGL-like)

```python
#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = ["waypaper-wallpaper>=0.1.0"]
# ///

from waypaper_wallpaper import Wallpaper
import psutil
import time

# Initialize wallpaper engine
wallpaper = Wallpaper()

# Load shader from file or string
shader = wallpaper.load_shader("""
    layout(location=0) out vec4 fragColor;

    uniform float u_time;
    uniform vec2 u_resolution;
    uniform float u_cpu_load;
    uniform sampler2D u_texture;

    void main() {
        vec2 uv = gl_FragCoord.xy / u_resolution;
        vec4 tex = texture(u_texture, uv);
        fragColor = mix(tex, vec4(u_cpu_load, 0.0, 0.0, 1.0), 0.3);
    }
""")

# Load texture from image
texture = wallpaper.load_texture("background.png")

# Main render loop - TODO: use an asyncio event loop if that's better
while True:
    # Access ambient data
    cpu_load = psutil.cpu_percent() / 100.0
    current_time = time.time()

    # Set uniforms
    wallpaper.set_uniform("u_time", current_time)
    wallpaper.set_uniform("u_cpu_load", cpu_load)
    wallpaper.set_uniform("u_resolution", [1920, 1080])

    # Bind texture to slot 0
    wallpaper.bind_texture(0, texture)

    # Render frame
    wallpaper.render()
```

## Implementation Requirements

### 1. Wayland Integration

- Use `wlr-layer-shell-unstable-v1` protocol to create background layer surface
- Handle multiple outputs (monitors) with independent rendering
- Implement output hotplug detection
- Handle compositor frame callbacks for VRR
- Graceful fallback if layer shell unavailable

### 2. Graphics Pipeline (wgpu)

- Compile WGSL shaders (convert from GLSL using `naga` or require WGSL input)
- **Decision needed**: Accept GLSL (user-friendly) or WGSL (native to WebGPU)?
  - Recommendation: Accept GLSL, convert to WGSL internally using a shader translator
- Create render pipeline with vertex/fragment stages
- Manage uniform buffers (dynamic updates per frame)
- Texture loading and sampling
- Full-screen quad rendering

### 3. Uniform System

- Type detection (float, vec2, vec3, vec4, mat4, sampler2D)
- Batch updates to minimize GPU transfers
- Support for:
  - Scalar values: `set_uniform("u_time", 1.5)`
  - Vectors: `set_uniform("u_color", [1.0, 0.5, 0.0])`
  - Matrices: `set_uniform("u_matrix", numpy_array)`
  - Textures: `bind_texture(slot, texture_obj)`

### 4. Texture Management

- Load PNG, JPEG, WebP via Pillow
- Convert to RGBA8 format
- Upload to GPU as wgpu textures
- Support texture reloading (for animated textures)
- Proper cleanup on destruction

### 5. Render Loop

- Sync with compositor frame callbacks
- Calculate delta time for animations
- Handle resize events
- Minimize Python overhead in hot path

### 6. Error Handling

- Shader compilation errors with line numbers
- Missing protocol warnings
- Texture load failures
- Graceful degradation

## Project Structure

```
waypaper-wallpaper/
├── waypaper_wallpaper.py  # Main library (single file with PEP 723 metadata)
├── examples/
│   ├── basic.py           # Minimal example
│   ├── ambient_data.py    # CPU/time-based shader
│   ├── multi_monitor.py   # Per-monitor shaders
│   └── shaders/
│       ├── gradient.frag
│       └── plasma.frag
├── README.md
└── pyproject.toml         # For PyPI distribution (optional)
```

## Implementation Phases

### Phase 1: Minimal Proof of Concept

1. Create layer shell surface on single output
2. Render solid color using wgpu
3. Basic render loop with frame callbacks

### Phase 2: Shader Support

1. Implement shader compilation (GLSL → WGSL or native WGSL)
2. Full-screen quad rendering
3. Uniform buffer management
4. Basic uniforms: `u_time`, `u_resolution`

### Phase 3: Textures

1. Image loading via Pillow
2. Texture upload to GPU
3. Sampler configuration
4. Texture binding API

### Phase 4: Multi-Monitor

1. Output enumeration
2. Per-output surfaces
3. Independent rendering per output
4. Hotplug handling

### Phase 5: Polish

1. Auto-uniform system (CPU, time, etc.)
2. Hot reload for shader files
3. Error reporting
4. Documentation and examples

## Key Technical Decisions

**Shader language**:

- Option A: Accept GLSL, convert to WGSL (user-friendly, requires translator)
- Option B: Accept WGSL only (simpler, but less familiar to users)
- **Recommendation**: Start with WGSL, add GLSL support later via `naga` or `shaderc`

**Wayland library**:

- Use `python-wayland` (pure Python) over `pywayland` (C wrapper)
- Benefits: No system dependencies, easier packaging, includes modern protocols

**Graphics API**:

- Use `wgpu-py` (WebGPU) over PyOpenGL
- Benefits: Modern API, better performance, cross-platform potential

**Single file vs package**:

- Start as single file with PEP 723 metadata
- Can refactor to package later if needed
- Easier distribution and testing

## Testing Strategy

1. **Manual testing** on different compositors:
   - sway
   - hyprland
   - other wlroots-based compositors

2. **Test scenarios**:
   - Single monitor
   - Multiple monitors
   - Monitor hotplug
   - Shader compilation errors
   - Missing textures
   - High CPU load

3. **Performance testing**:
   - Frame time profiling
   - Memory leak detection
   - GPU memory usage

## Documentation Requirements

- Quick start guide
- API reference
- Shader uniform conventions
- Example gallery
- Troubleshooting guide (compositor compatibility)

## Success Criteria

1. User can write a 10-line script to render a shader wallpaper
2. User can access system data (CPU, time, etc.) in their script
3. Works on sway and hyprland
4. Handles multiple monitors
5. Stable for 24+ hour runs
6. < 50MB memory footprint
7. < 1% CPU usage for simple shaders

## Notes for Implementation

- Start with sway as the primary test compositor
- The `python-wayland` library is newer but has no C dependencies - test thoroughly
- wgpu-py's API closely follows the WebGPU spec - reference MDN WebGPU docs
- Consider using `wgpu.gui.auto` for development/debugging (opens a window)
- Layer shell protocol XML files are in `wayland-protocols` package

## Example Shaders to Include

1. **Gradient** - Simple color gradient (tests basic rendering)
2. **Plasma** - Classic plasma effect (tests time uniform)
3. **CPU Visualizer** - Color based on CPU load (tests ambient data)
4. **Texture Blend** - Blend between two textures (tests texture support)

**References**

[^1]: [python-wayland · PyPI](https://pypi.org/project/python-wayland/) (49%)

[^2]: [Running scripts | uv](https://docs.astral.sh/uv/guides/scripts/) (28%)

[^3]: [pygfx/wgpu-py: WebGPU for Python](https://github.com/pygfx/wgpu-py) (23%)
