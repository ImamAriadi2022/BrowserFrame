from __future__ import annotations

from pathlib import Path

from PIL import Image

from .config import load_settings, validate_template_path
from .image_utils import composite_template, load_image, load_logo_image, validate_region
from .models import FitMode


def create_preview(template_path: Path, screenshot_path: Path, url: str, fit_mode: FitMode = "cover") -> Image.Image:
    settings = load_settings()
    if settings.viewport is None:
        raise ValueError("Viewport has not been selected")
    if settings.address_bar is None:
        raise ValueError("Address bar has not been selected")
    validate_template_path(template_path)
    template = load_image(template_path)
    validate_region(settings.viewport, template.size, "Viewport")
    validate_region(settings.address_bar, template.size, "Address bar")
    profile = settings.profile()
    if profile.website_title_region is None:
        raise ValueError("Website title region has not been selected")
    if profile.website_logo_region is None:
        raise ValueError("Website logo region has not been selected")
    validate_region(profile.website_title_region, template.size, "Website title")
    validate_region(profile.website_logo_region, template.size, "Website logo")
    if not screenshot_path.exists():
        raise FileNotFoundError(f"Screenshot not found: {screenshot_path}")
    screenshot = load_image(screenshot_path)
    if not profile.website_logo_image_path:
        raise ValueError("Website logo image has not been selected")
    logo_path = Path(profile.website_logo_image_path)
    if not logo_path.exists():
        raise FileNotFoundError(f"Logo image not found: {logo_path}")
    logo_image = load_logo_image(logo_path, (profile.website_logo_region.width, profile.website_logo_region.height))
    return composite_template(
        template=template,
        viewport=settings.viewport,
        address_bar=settings.address_bar,
        screenshot=screenshot,
        url=url,
        website_title=settings.website_title,
        website_logo_text=settings.website_logo_text,
        title_region=profile.website_title_region,
        logo_region=profile.website_logo_region,
        website_logo_image=logo_image,
        text_settings=settings.url_text,
        contain_background=settings.contain_background,
        fit_mode=fit_mode,
    )
