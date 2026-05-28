from PIL import Image, ImageDraw, ImageFont
import os

SIZES = [16, 32, 48, 64, 128, 256]

BG_COLOR     = (10, 10, 10)
BORDER_COLOR = (0, 220, 180)
TEXT_COLOR   = (0, 220, 180)


def make_frame(size):
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    border = max(1, size // 16)
    radius = max(2, size // 8)

    draw.rounded_rectangle(
        [0, 0, size - 1, size - 1],
        radius=radius,
        fill=BG_COLOR,
        outline=BORDER_COLOR,
        width=border
    )

    font_size = int(size * 0.62)
    font = None

    for font_path in [
        "C:/Windows/Fonts/consolab.ttf",
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]:
        if os.path.exists(font_path):
            try:
                font = ImageFont.truetype(font_path, font_size)
                break
            except Exception:
                pass

    letter = "Z"

    if font:
        bbox   = draw.textbbox((0, 0), letter, font=font)
        tw     = bbox[2] - bbox[0]
        th     = bbox[3] - bbox[1]
        x      = (size - tw) / 2 - bbox[0]
        y      = (size - th) / 2 - bbox[1]
        draw.text((x, y), letter, fill=TEXT_COLOR, font=font)
    else:
        draw.text((size // 4, size // 8), letter, fill=TEXT_COLOR)

    return img


frames = [make_frame(s) for s in SIZES]

frames[0].save(
    "zomet.ico",
    format="ICO",
    sizes=[(s, s) for s in SIZES],
    append_images=frames[1:]
)

print("zomet.ico berhasil dibuat!")
