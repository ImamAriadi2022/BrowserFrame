from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFont

from .models import Region, TextSettings

try:
    Resampling = Image.Resampling
except AttributeError:  # pragma: no cover
    Resampling = Image

FitMode = Literal["cover", "contain"]


@dataclass(slots=True)
class RenderContext:
    template: Image.Image
    viewport: Region
    address_bar: Region
    text_settings: TextSettings
    contain_background: str


def load_image(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


def resize_cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_width, target_height = size
    source_width, source_height = image.size
    scale = max(target_width / source_width, target_height / source_height)
    resized = image.resize((max(1, round(source_width * scale)), max(1, round(source_height * scale))), Resampling.LANCZOS)
    left = max(0, (resized.width - target_width) // 2)
    top = max(0, (resized.height - target_height) // 2)
    return resized.crop((left, top, left + target_width, top + target_height))


def resize_contain(image: Image.Image, size: tuple[int, int], background_color: str) -> Image.Image:
    target_width, target_height = size
    background = Image.new("RGBA", size, background_color)
    source_width, source_height = image.size
    scale = min(target_width / source_width, target_height / source_height)
    resized = image.resize((max(1, round(source_width * scale)), max(1, round(source_height * scale))), Resampling.LANCZOS)
    left = (target_width - resized.width) // 2
    top = (target_height - resized.height) // 2
    background.alpha_composite(resized, (left, top))
    return background


def fit_image(image: Image.Image, size: tuple[int, int], mode: FitMode, background_color: str = "#FFFFFF") -> Image.Image:
    if mode == "cover":
        return resize_cover(image, size)
    if mode == "contain":
        return resize_contain(image, size, background_color)
    raise ValueError(f"Invalid fit mode: {mode}")


def load_font(font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/Roboto-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            try:
                return ImageFont.truetype(str(path), font_size)
            except OSError:
                continue
    return ImageFont.load_default()


def truncate_text(text: str, font: ImageFont.ImageFont, max_width: int) -> str:
    if max_width <= 0:
        return ""
    dummy = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy)
    if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
        return text
    ellipsis = "..."
    if draw.textbbox((0, 0), ellipsis, font=font)[2] > max_width:
        return ""
    left = 0
    right = len(text)
    best = ellipsis
    while left <= right:
        middle = (left + right) // 2
        candidate = text[:middle].rstrip() + ellipsis
        width = draw.textbbox((0, 0), candidate, font=font)[2]
        if width <= max_width:
            best = candidate
            left = middle + 1
        else:
            right = middle - 1
    return best


def render_url_on_base(base: Image.Image, address_bar: Region, url: str, text_settings: TextSettings) -> Image.Image:
    canvas = base.copy()
    draw = ImageDraw.Draw(canvas)
    fill_color = text_settings.background_color
    draw.rectangle(
        (address_bar.x, address_bar.y, address_bar.x + address_bar.width, address_bar.y + address_bar.height),
        fill=fill_color,
    )
    font = load_font(text_settings.font_size)
    available_width = address_bar.width - text_settings.padding_left * 2
    text = truncate_text(url, font, available_width)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_height = bbox[3] - bbox[1]
    text_y = address_bar.y + max(0, (address_bar.height - text_height) // 2 - 1)
    draw.text((address_bar.x + text_settings.padding_left, text_y), text, font=font, fill=text_settings.text_color)
    return canvas


def composite_template(
    template: Image.Image,
    viewport: Region,
    address_bar: Region,
    screenshot: Image.Image,
    url: str,
    text_settings: TextSettings,
    contain_background: str,
    fit_mode: FitMode,
) -> Image.Image:
    base = template.copy().convert("RGBA")
    fitted = fit_image(screenshot.convert("RGBA"), (viewport.width, viewport.height), fit_mode, contain_background)
    base.alpha_composite(fitted, (viewport.x, viewport.y))
    return render_url_on_base(base, address_bar, url, text_settings)


def validate_region(region: Region, template_size: tuple[int, int], name: str) -> None:
    if not region.is_valid():
        raise ValueError(f"{name} width and height must be greater than zero")
    width, height = template_size
    if region.x < 0 or region.y < 0 or region.x + region.width > width or region.y + region.height > height:
        raise ValueError(f"{name} is outside template bounds")
