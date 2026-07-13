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


def load_logo_image(path: Path, size: tuple[int, int]) -> Image.Image:
    image = load_image(path)
    return fit_image(image, size, "contain", "#00000000")


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


def _sample_border_background(image: Image.Image, region: Region) -> str:
    pixels = []
    img_width, img_height = image.size
    for x in range(region.x, region.x + region.width):
        if region.y > 0:
            px = image.getpixel((x, region.y - 1))
            pixels.append(px[:3])
        if region.y + region.height < img_height:
            px = image.getpixel((x, region.y + region.height))
            pixels.append(px[:3])
    for y in range(region.y, region.y + region.height):
        if region.x > 0:
            px = image.getpixel((region.x - 1, y))
            pixels.append(px[:3])
        if region.x + region.width < img_width:
            px = image.getpixel((region.x + region.width, y))
            pixels.append(px[:3])
    if not pixels:
        return "#FFFFFF"
    red = sum(p[0] for p in pixels) // len(pixels)
    green = sum(p[1] for p in pixels) // len(pixels)
    blue = sum(p[2] for p in pixels) // len(pixels)
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


def _badge_fill_color(source: Image.Image) -> str:
    pixels = list(source.convert("RGBA").getdata())
    if not pixels:
        return "#3b82f6"
    red = sum(pixel[0] for pixel in pixels) // len(pixels)
    green = sum(pixel[1] for pixel in pixels) // len(pixels)
    blue = sum(pixel[2] for pixel in pixels) // len(pixels)
    return f"#{max(0, red - 20):02x}{max(0, green - 20):02x}{min(255, blue + 30):02x}"


def render_website_title_on_base(
    base: Image.Image,
    title: str,
    title_region: Region,
    logo_region: Region,
    logo_text: str = "",
    logo_image: Image.Image | None = None,
) -> Image.Image:
    if not title.strip() and logo_image is None and not logo_text.strip():
        return base.copy()
    canvas = base.copy()
    draw = ImageDraw.Draw(canvas)
    font = load_font(14)
    logo_font = load_font(12)
    text = title.strip()
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    max_width = max(1, title_region.width - 16)
    text = truncate_text(text, font, max_width)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    if logo_image is not None:
        logo_bg = _sample_border_background(base, logo_region)
        draw.rectangle((logo_region.x, logo_region.y, logo_region.x + logo_region.width, logo_region.y + logo_region.height), fill=logo_bg)
        image = logo_image.copy().resize((logo_region.width, logo_region.height), Resampling.LANCZOS)
        canvas.alpha_composite(image, (logo_region.x, logo_region.y))
    else:
        badge_fill = _badge_fill_color(base.crop((logo_region.x, logo_region.y, logo_region.x + logo_region.width, logo_region.y + logo_region.height)))
        badge_text = (logo_text.strip() or title.strip()[:2] or "BF").upper()[:3]
        badge_bbox = draw.textbbox((0, 0), badge_text, font=logo_font)
        badge_text_width = badge_bbox[2] - badge_bbox[0]
        badge_text_height = badge_bbox[3] - badge_bbox[1]
        draw.rounded_rectangle((logo_region.x, logo_region.y, logo_region.x + logo_region.width, logo_region.y + logo_region.height), radius=6, fill=badge_fill)
        badge_text_x = logo_region.x + max(0, (logo_region.width - badge_text_width) // 2)
        badge_text_y = logo_region.y + max(0, (logo_region.height - badge_text_height) // 2 - 1)
        draw.text((badge_text_x, badge_text_y), badge_text, font=logo_font, fill=_contrast_text_color(badge_fill))
    text_x = title_region.x + 6
    text_y = title_region.y + max(0, (title_region.height - text_height) // 2 - 1)
    text_bg = _sample_border_background(base, title_region)
    draw.rectangle((text_x, text_y, text_x + text_width, text_y + text_height), fill=text_bg)
    draw.text((text_x, text_y), text, font=font, fill=_contrast_text_color(text_bg))
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
    website_logo_text: str,
    title_region: Region,
    logo_region: Region,
    website_logo_image: Image.Image | None,
    text_settings: TextSettings,
    contain_background: str,
    fit_mode: FitMode,
) -> Image.Image:
    base = template.copy().convert("RGBA")
    base = render_website_title_on_base(base, website_title, title_region, logo_region, website_logo_text, website_logo_image)
    fitted = fit_image(screenshot.convert("RGBA"), (viewport.width, viewport.height), fit_mode, contain_background)
    base.alpha_composite(fitted, (viewport.x, viewport.y))
    return render_url_on_base(base, address_bar, url, text_settings)


def validate_region(region: Region, template_size: tuple[int, int], name: str) -> None:
    if not region.is_valid():
        raise ValueError(f"{name} width and height must be greater than zero")
    width, height = template_size
    if region.x < 0 or region.y < 0 or region.x + region.width > width or region.y + region.height > height:
        raise ValueError(f"{name} is outside template bounds")
