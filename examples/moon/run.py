"""Animate a rainbow tint over an image with Renderer.run()."""

from colorsys import hsv_to_rgb

import wayshade

with wayshade.create() as renderer:
    moon = renderer.load_image("moon.jpg")
    tint_shader = renderer.load_shader(
        """
        #version 120
        uniform sampler2D source;
        uniform vec3 tint;
        varying vec2 uv;

        void main() {
            vec4 color = texture2D(source, uv);
            vec3 tinted = color.rgb * mix(vec3(1.0), tint, 0.7);
            gl_FragColor = vec4(tinted, color.a);
        }
        """
    )

    def update(frame: wayshade.Frame) -> None:
        # One full rainbow cycle takes about 30 seconds.
        hue = (frame.time / 30.0) % 1.0
        tint_shader.set("tint", hsv_to_rgb(hue, 1.0, 1.0))
        tint_shader.set("source", moon)
        renderer.draw(tint_shader, to=renderer.wallpaper)

    renderer.run(update=update)
