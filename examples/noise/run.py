"""Renders TV static/snow/noise."""

# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "wayshade @ git+https://github.com/joshwilsonvu/wayshade",
# ]
# ///

from random import uniform

import wayshade

# This is the looping AnimationPlayer track from Node2D.tscn. The original uses
# cubic interpolation (interp=2) and a 10-second loop.
INTERFERENCE_KEYS = (
    (0.0, (-30.0, -500.0)),
    (0.2, (20.0, 40.0)),
    (2.0, (80.0, 120.0)),
    (2.2, (500.0, 800.0)),
    (4.0, (1000.0, 200.0)),
    (6.1, (-99.0, 33.0)),
    (7.9, (10.0, 967.0)),
    (10.0, (30.0, 20.0)),
)
VSYNC_KEYS = (
    (0.0, 0.0),
    (0.4, 50.0),
    (1.5, 0.0),
    (4.7, 322.0),
    (5.2, 1.0),
    (7.8, -200.0),
    (9.1, 1.0),
)
ANIMATION_LENGTH = 10.0


def cubic_value(keys, time: float):
    """Evaluate a looping Godot-style cubic value track."""
    for index in range(len(keys) - 1):
        start_time, start = keys[index]
        end_time, end = keys[index + 1]
        if time <= end_time:
            previous = keys[index - 1][1] if index else start
            following = keys[index + 2][1] if index + 2 < len(keys) else end
            # All key transitions are 1.0, so Godot's easing leaves t unchanged.
            amount = (time - start_time) / (end_time - start_time)
            amount2 = amount * amount
            amount3 = amount2 * amount
            # Catmull-Rom is the cubic interpolation used for this value track.
            return tuple(
                0.5
                * (
                    (2.0 * current)
                    + (-previous + next_value) * amount
                    + (2.0 * previous - 5.0 * current + 4.0 * next_value - following)
                    * amount2
                    + (-previous + 3.0 * current - 3.0 * next_value + following)
                    * amount3
                )
                for previous, current, next_value, following in zip(
                    previous, start, end, following, strict=True
                )
            )

    return keys[-1][1]


def cubic_scalar(keys, time: float) -> float:
    return cubic_value(tuple((key_time, (value,)) for key_time, value in keys), time)[0]


with wayshade.create() as renderer:
    noise_shader = renderer.load_shader_file("./noise.glsl")

    def update(frame: wayshade.Frame) -> None:
        interference = cubic_value(INTERFERENCE_KEYS, frame.time % ANIMATION_LENGTH)
        vsync_issues = cubic_scalar(VSYNC_KEYS, frame.time % ANIMATION_LENGTH)

        print("interference", interference)
        print("vsync_issues", vsync_issues)
        print("iTime", frame.time)
        print("iResolution", (frame.width, frame.height))

        mouse_pos = (
            interference[0] * uniform(1.045, 2.23),
            interference[1] * uniform(-1.01, 4.3),
        )
        effective_vsync = vsync_issues * uniform(-1.01, 2.37)
        noise_shader.set(
            {
                "iResolution": (frame.width, frame.height),
                "iTime": frame.time,
                # These ranges match rand_range() in Node2D.gd.
                "mouse_pos": mouse_pos,
                "vsync_issues": effective_vsync,
            }
        )
        renderer.draw(noise_shader, to=renderer.wallpaper, max_fps=12)

    renderer.run(update=update)
