from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from PIL import Image

from .config import ensure_output_dir, load_config, load_settings, validate_template_path
from .image_utils import composite_template, load_image, load_logo_image, validate_region
from .models import BatchItem, DeviceKind, Region, Settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BatchResult:
    success: int
    failed: int
    errors: list[str]


class BatchGenerator:
    def __init__(self, template_path: Path, config_path: Path, settings_path: Path, output_dir: Path) -> None:
        self.template_path = template_path
        self.config_path = config_path
        self.settings_path = settings_path
        self.output_dir = output_dir

    def _load_template(self) -> Image.Image:
        validate_template_path(self.template_path)
        return load_image(self.template_path)

    def _load_regions(self, settings: Settings, template_size: tuple[int, int]) -> tuple[Region, Region]:
        if settings.viewport is None:
            raise ValueError("Viewport has not been selected")
        if settings.address_bar is None:
            raise ValueError("Address bar has not been selected")
        validate_region(settings.viewport, template_size, "Viewport")
        validate_region(settings.address_bar, template_size, "Address bar")
        return settings.viewport, settings.address_bar

    def generate(self) -> BatchResult:
        logger.info("Loading template: %s", self.template_path)
        template = self._load_template()
        settings = load_settings(self.settings_path)
        device_profile = settings.profile(settings.active_device)
        if not device_profile.regions_confirmed:
            raise ValueError("Regions have not been confirmed. Run: python main.py --edit")
        viewport, address_bar = self._load_regions(settings, template.size)
        items = load_config(self.config_path, cast(DeviceKind, settings.active_device))
        profile = settings.profile()
        if profile.website_title_region is None:
            raise ValueError("Website title region has not been selected")
        if profile.website_logo_region is None:
            raise ValueError("Website logo region has not been selected")
        validate_region(profile.website_title_region, template.size, "Website title")
        validate_region(profile.website_logo_region, template.size, "Website logo")
        if not profile.website_logo_image_path:
            raise ValueError("Website logo image has not been selected")
        logo_path = Path(profile.website_logo_image_path)
        if not logo_path.exists():
            raise FileNotFoundError(f"Logo image not found: {logo_path}")
        logo_image = load_logo_image(logo_path, (profile.website_logo_region.width, profile.website_logo_region.height))
        output_dir = ensure_output_dir(self.output_dir)
        preserve_device_folder = output_dir.resolve() == Path("output").resolve()
        success = 0
        failed = 0
        errors: list[str] = []
        for index, item in enumerate(items, start=1):
            logger.info("Processing %s/%s: %s", index, len(items), item.output)
            try:
                result = self._process_item(template, viewport, address_bar, settings, profile, logo_image, item)
                output_path = self._resolve_output_path(output_dir, item.output, preserve_device_folder)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                result.save(output_path, format="PNG")
                logger.info("Saved: %s", output_path)
                success += 1
            except Exception as exc:  # noqa: BLE001
                failed += 1
                message = f"{item.output}: {exc}"
                errors.append(message)
                logger.error("%s", message)
        logger.info("Completed.")
        logger.info("Success: %s", success)
        logger.info("Failed: %s", failed)
        return BatchResult(success=success, failed=failed, errors=errors)

    def _process_item(
        self,
        template: Image.Image,
        viewport: Region,
        address_bar: Region,
        settings: Settings,
        profile,
        logo_image: Image.Image,
        item: BatchItem,
    ) -> Image.Image:
        if not item.screenshot.exists():
            raise FileNotFoundError(f"Screenshot not found: {item.screenshot}")
        screenshot = load_image(item.screenshot)
        if item.fit not in {"cover", "contain"}:
            raise ValueError(f"Format fit is not valid: {item.fit}")
        website_title = item.title if item.title is not None else settings.website_title
        return composite_template(
            template=template,
            viewport=viewport,
            address_bar=address_bar,
            screenshot=screenshot,
            url=item.url,
            website_title=website_title,
            website_logo_text=settings.website_logo_text,
            title_region=profile.website_title_region,
            logo_region=profile.website_logo_region,
            website_logo_image=logo_image,
            text_settings=settings.url_text,
            contain_background=settings.contain_background,
            fit_mode=item.fit,
        )

    def _resolve_output_path(self, output_dir: Path, item_output: str, preserve_device_folder: bool) -> Path:
        item_path = Path(item_output)
        if preserve_device_folder:
            return output_dir / item_path
        parts = item_path.parts
        if parts and parts[0] in {"desktop", "mobile"}:
            item_path = Path(*parts[1:]) if len(parts) > 1 else Path(parts[0])
        return output_dir / item_path
