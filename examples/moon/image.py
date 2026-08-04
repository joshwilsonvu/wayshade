import wayshade

renderer = wayshade.create()
image = renderer.load_image("moon.jpg")

renderer.draw(image, to=renderer.wallpaper)
input("Press Enter to quit")
