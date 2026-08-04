# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "wayshade @ git+https://github.com/joshwilsonvu/wayshade",
# ]
# ///

import wayshade

renderer = wayshade.create()
image = renderer.load_image("moon.jpg")

renderer.draw(image, to=renderer.wallpaper)
input("Press Enter to quit")
