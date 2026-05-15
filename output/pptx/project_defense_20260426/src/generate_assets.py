from pathlib import Path
from random import Random

from PIL import Image, ImageDraw, ImageFilter


OUT = Path("/Users/xizhuxizhu/Desktop/IndProj04/output/pptx/project_defense_20260426/scratch/assets")
W, H = 1280, 720


def hex_to_rgb(value):
    value = value.strip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def lerp(a, b, t):
    return int(a + (b - a) * t)


def gradient_bg(top="#062766", bottom="#031032"):
    top_rgb = hex_to_rgb(top)
    bot_rgb = hex_to_rgb(bottom)
    img = Image.new("RGB", (W, H), top_rgb)
    px = img.load()
    for y in range(H):
        t = y / (H - 1)
        for x in range(W):
            side = 0.10 * (x / W)
            tt = min(1, max(0, t + side))
            px[x, y] = tuple(lerp(top_rgb[i], bot_rgb[i], tt) for i in range(3))
    return img.convert("RGBA")


def add_glow(img, center, radius, color, strength=0.35):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for r in range(radius, 0, -8):
        t = r / radius
        alpha = int(255 * strength * (1 - t) ** 1.8)
        draw.ellipse(
            (center[0] - r, center[1] - r, center[0] + r, center[1] + r),
            fill=(*hex_to_rgb(color), alpha),
        )
    return Image.alpha_composite(img, overlay)


def add_grid(img, alpha=26):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for x in range(0, W, 40):
        draw.line((x, 0, x, H), fill=(92, 160, 255, alpha), width=1)
    for y in range(0, H, 40):
        draw.line((0, y, W, y), fill=(92, 160, 255, alpha), width=1)
    return Image.alpha_composite(img, overlay)


def add_network(img, seed=7):
    rng = Random(seed)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    nodes = []
    for _ in range(72):
        x = rng.randint(470, 1230)
        y = rng.randint(80, 620)
        nodes.append((x, y))
    for i, a in enumerate(nodes):
        near = sorted(nodes[i + 1 :], key=lambda b: (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)[:3]
        for b in near:
            dist = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
            if dist < 190:
                draw.line((a, b), fill=(73, 179, 255, 46), width=1)
    for x, y in nodes:
        r = rng.choice([2, 2, 3, 4])
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(96, 201, 255, 130))
    for x in range(560, 1240, 110):
        draw.arc((x - 520, 80, x + 520, 700), start=195, end=345, fill=(77, 173, 255, 42), width=2)
    return Image.alpha_composite(img, overlay.filter(ImageFilter.GaussianBlur(0.1)))


def add_wave(img):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for i in range(18):
        y0 = 510 + i * 8
        pts = []
        for x in range(-80, W + 120, 24):
            y = y0 + 28 * __import__("math").sin((x + i * 25) / 112)
            pts.append((x, y))
        draw.line(pts, fill=(116, 196, 255, 38 + i * 3), width=1)
    return Image.alpha_composite(img, overlay)


def make_cover():
    img = gradient_bg()
    img = add_grid(img, 18)
    img = add_glow(img, (930, 330), 310, "#15A7FF", 0.26)
    img = add_glow(img, (1160, 120), 220, "#2F6CFF", 0.22)
    img = add_network(img, 12)
    img = add_wave(img)
    vignette = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(vignette)
    draw.rectangle((0, 0, 470, H), fill=(0, 11, 39, 86))
    return Image.alpha_composite(img, vignette)


def make_section():
    img = gradient_bg("#082D72", "#061536")
    img = add_grid(img, 14)
    img = add_glow(img, (1030, 510), 360, "#21A9FF", 0.22)
    img = add_network(img, 21)
    img = add_wave(img)
    return img


def make_light_texture():
    img = Image.new("RGBA", (W, H), (247, 251, 255, 255))
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for x in range(0, W, 40):
        draw.line((x, 0, x, H), fill=(70, 130, 200, 10), width=1)
    for y in range(0, H, 40):
        draw.line((0, y, W, y), fill=(70, 130, 200, 10), width=1)
    draw.polygon([(0, 0), (520, 0), (420, 720), (0, 720)], fill=(233, 243, 255, 130))
    draw.polygon([(960, 0), (1280, 0), (1280, 720), (1050, 720)], fill=(236, 246, 255, 115))
    return Image.alpha_composite(img, overlay)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    make_cover().save(OUT / "cover_bg.png")
    make_section().save(OUT / "section_bg.png")
    make_light_texture().save(OUT / "light_texture.png")
    print(OUT)


if __name__ == "__main__":
    main()
