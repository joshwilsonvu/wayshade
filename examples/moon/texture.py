import wayshade

renderer = wayshade.create()
image = renderer.load_image("moon.jpg")

intermediate = renderer.draw(image)
renderer.draw(intermediate, to=renderer.wallpaper)
input("Press Enter to quit")
