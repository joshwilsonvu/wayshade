"""Renders the moon with real surface, lighting, libration, and opposition surge"""

# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "wayshade @ git+https://github.com/joshwilsonvu/wayshade",
# ]
# ///

import wayshade

with wayshade.create() as renderer:
    moon = renderer.load_image("moon.jpg")
    moon_shader = renderer.load_shader_file("./moon.glsl")
    moon_shader.set("moon", moon)

    def update(frame: wayshade.Frame) -> None:
        moon_shader.set("iResolution", (frame.width, frame.height))
        moon_shader.set("iTime", frame.time)
        renderer.draw(moon_shader, to=renderer.wallpaper)

    renderer.run(update=update)
