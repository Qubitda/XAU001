"""Build high-quality 1920/2560 hero JPEGs for full-bleed storefront banners."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

SRC_ROOT = Path(__file__).resolve().parents[1] / "packages" / "shared" / "src" / "assets" / "images"
OUT_ROOT = SRC_ROOT / "hero"

JOBS = (
    ("kl022_necklace_model_1795533194072.jpg", "timeless-elegance"),
    ("se009_white_hand_1795533193888.jpg", "new-arrivals"),
    ("hero_diamond_atelier_1795551170432.jpg", "atelier-craft"),
)
WIDTHS = (1920, 2560)


def main() -> None:
    OUT_ROOT.mkdir(exist_ok=True)
    for src_name, slug in JOBS:
        src = Image.open(SRC_ROOT / src_name).convert("RGB")
        print(f"Source {src_name}: {src.size}")
        for width in WIDTHS:
            ratio = width / src.width
            height = max(1, round(src.height * ratio))
            up = src.resize((width, height), Image.Resampling.LANCZOS)
            up = up.filter(ImageFilter.UnsharpMask(radius=1.2, percent=110, threshold=2))
            up = ImageEnhance.Contrast(up).enhance(1.03)
            up = ImageEnhance.Sharpness(up).enhance(1.08)
            out = OUT_ROOT / f"hero-{slug}-{width}.jpg"
            # quality=92 + no chroma subsample keeps gold/diamond edges cleaner on large screens
            up.save(
                out,
                format="JPEG",
                quality=92,
                optimize=True,
                progressive=True,
                subsampling=0,
            )
            print(f"  wrote {out.name}: {up.size} bytes={out.stat().st_size}")
    print("DONE")


if __name__ == "__main__":
    main()
