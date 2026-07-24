from PIL import Image, ImageDraw

def make_ico():
    size = (128, 128)
    image = Image.new('RGBA', size, (37, 99, 235, 255))
    
    # Mask to rounded rectangle
    mask = Image.new('L', size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, 128, 128), radius=24, fill=255)
    
    output = Image.new('RGBA', size, (0, 0, 0, 0))
    output.paste(image, (0, 0), mask)

    draw_out = ImageDraw.Draw(output)
    draw_out.rounded_rectangle((24, 28, 104, 84), radius=16, fill=(255, 255, 255, 255))
    draw_out.polygon([(36, 80), (28, 98), (56, 84)], fill=(255, 255, 255, 255))
    draw_out.polygon([(64, 40), (52, 58), (62, 58), (58, 74), (72, 54), (62, 54)], fill=(37, 99, 235, 255))

    output.save("D:/tool_facebook_chat_page/app_logo.ico", format="ICO", sizes=[(64, 64), (32, 32), (16, 16)])
    print("Created app_logo.ico successfully!")

if __name__ == "__main__":
    make_ico()
