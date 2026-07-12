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


def _sample_address_bar_background(image: Image.Image, address_bar: Region) -> str:
    crop = image.crop((address_bar.x, address_bar.y, address_bar.x + address_bar.width, address_bar.y + address_bar.height)).convert("RGBA")
    pixels = list(crop.getdata())
    if not pixels:
        return "#FFFFFF"
    red = sum(pixel[0] for pixel in pixels) // len(pixels)
    green = sum(pixel[1] for pixel in pixels) // len(pixels)
    blue = sum(pixel[2] for pixel in pixels) // len(pixels)
    return f"#{red:02x}{green:02x}{blue:02x}"


def _contrast_text_color(background_hex: str) -> str:
    background = background_hex.lstrip("#")
    if len(background) != 6:
        return "#000000"
    red = int(background[0:2], 16)
    green = int(background[2:4], 16)
    blue = int(background[4:6], 16)
    luminance = (0.299 * red) + (0.587 * green) + (0.114 * blue)
    return "#000000" if luminance >= 160 else "#ffffff"


def render_website_title_on_base(base: Image.Image, title: str) -> Image.Image:
    if not title.strip():
        return base.copy()
    canvas = base.copy()
    draw = ImageDraw.Draw(canvas)
    title_region = Region(58, 2, 360, 32)
    font = load_font(14)
    text = title.strip()
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    max_width = max(1, title_region.width - 16)
    text = truncate_text(text, font, max_width)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    fill_color = _sample_address_bar_background(base, title_region)
    draw.rectangle((title_region.x, title_region.y, title_region.x + title_region.width, title_region.y + title_region.height), fill=fill_color)
    text_x = title_region.x + 6
    text_y = title_region.y + max(0, (title_region.height - text_height) // 2 - 1)
    draw.text((text_x, text_y), text, font=font, fill=_contrast_text_color(fill_color))
    return canvas


def render_url_on_base(base: Image.Image, address_bar: Region, url: str, text_settings: TextSettings) -> Image.Image:
    canvas = base.copy()
    draw = ImageDraw.Draw(canvas)
    font = load_font(text_settings.font_size)
    available_width = address_bar.width - text_settings.padding_left * 2
    text = truncate_text(url, font, available_width)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_height = bbox[3] - bbox[1]
    text_width = bbox[2] - bbox[0]
    text_x = address_bar.x + text_settings.padding_left
    text_y = address_bar.y + max(0, (address_bar.height - text_height) // 2 - 1)
    left = max(address_bar.x + 4, text_x - 4)
    top = max(address_bar.y + 2, text_y - 2)
    right = min(address_bar.x + address_bar.width - 4, text_x + text_width + 6)
    bottom = min(address_bar.y + address_bar.height - 2, text_y + text_height + 4)
    fill_color = _sample_address_bar_background(base, address_bar)
    draw.rectangle((left, top, right, bottom), fill=fill_color)
    draw.text((text_x, text_y), text, font=font, fill=_contrast_text_color(fill_color))
    return canvas


def composite_template(
    template: Image.Image,
    viewport: Region,
    address_bar: Region,
    screenshot: Image.Image,
    url: str,
    website_title: str,
    text_settings: TextSettings,
    contain_background: str,
    fit_mode: FitMode,
) -> Image.Image:
    base = template.copy().convert("RGBA")
    base = render_website_title_on_base(base, website_title)
    fitted = fit_image(screenshot.convert("RGBA"), (viewport.width, viewport.height), fit_mode, contain_background)
    base.alpha_composite(fitted, (viewport.x, viewport.y))
    return render_url_on_base(base, address_bar, url, text_settings)


def validate_region(region: Region, template_size: tuple[int, int], name: str) -> None:
    if not region.is_valid():
        raise ValueError(f"{name} width and height must be greater than zero")
    width, height = template_size
    if region.x < 0 or region.y < 0 or region.x + region.width > width or region.y + region.height > height:
        raise ValueError(f"{name} is outside template bounds")
