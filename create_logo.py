from PIL import Image, ImageDraw, ImageFont

def make_logo():
    size = (128, 128)
    image = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Draw rounded rectangle with Messenger blue gradient style
    # Draw dark blue rounded background
    for i in range(128):
        # radial/linear color mix
        r = int(37 + (59 - 37) * (i / 128))
        g = int(99 + (130 - 99) * (i / 128))
        b = int(235 + (246 - 235) * (i / 128))
        draw.line([(0, i), (128, i)], fill=(r, g, b, 255))

    # Mask to rounded rectangle
    mask = Image.new('L', size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, 128, 128), radius=28, fill=255)
    
    output = Image.new('RGBA', size, (0, 0, 0, 0))
    output.paste(image, (0, 0), mask)

    # Draw sleek chat bubble icon inside
    draw_out = ImageDraw.Draw(output)
    # Chat bubble body
    draw_out.rounded_rectangle((24, 28, 104, 84), radius=16, fill=(255, 255, 255, 255))
    # Chat bubble tail
    draw_out.polygon([(36, 80), (28, 98), (56, 84)], fill=(255, 255, 255, 255))
    
    # Draw lightning bolt / chat icon lines inside bubble
    draw_out.polygon([(64, 40), (52, 58), (62, 58), (58, 74), (72, 54), (62, 54)], fill=(37, 99, 235, 255))

    output.save("D:/tool_facebook_chat_page/app_logo.png")
    print("Created app_logo.png successfully!")

if __name__ == "__main__":
    make_logo()
