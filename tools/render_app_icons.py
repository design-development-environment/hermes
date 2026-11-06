"""Generate the platform icons from the supplied Hermes PNG artwork."""
from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1]
for theme in ("dark", "light"):
    name = f"icon-{theme}.png"
    source = root / "packaging/branding" / name
    with Image.open(source) as image:
        artwork = image.convert("RGBA")
    width, height = artwork.size
    mask = Image.new("L", (width * 2, height * 2))
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, mask.width - 1, mask.height - 1),
                                           radius=width * 0.40, fill=255)
    artwork.putalpha(mask.resize(artwork.size, Image.Resampling.LANCZOS))
    artwork.save(source)
    for platform in ("windows", "macos"):
        folder = root / "platforms" / platform / "source/branding"
        artwork.save(folder / name)
        if theme == "dark":
            artwork.save(folder / "hermes.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
