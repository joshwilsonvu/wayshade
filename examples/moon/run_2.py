"""Pulse the image's brightness with Renderer.run()."""

import wayshade

with wayshade.create() as renderer:
    moon = renderer.load_image("moon.jpg")
    tint_shader = renderer.load_shader(
        """
        #version 120
        varying vec2 uv;

        uniform sampler2D source;
        uniform float time;

        void main() {
            vec4 color = texture2D(source, uv);
            float pulse = (1.0 + sin(time)) * 0.5;
            vec3 pulsed = color.rgb * pulse;
            gl_FragColor = vec4(pulsed, color.a);
        }
        """
    )

    def update(frame: wayshade.Frame) -> None:
        tint_shader.set(frame.uniforms())
        renderer.draw(tint_shader, textures={"source": moon}, to=renderer.wallpaper)

    renderer.run(update=update)
